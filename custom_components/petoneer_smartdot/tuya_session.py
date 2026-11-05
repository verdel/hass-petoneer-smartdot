"""Async Tuya BLE application session; transport is supplied by Bleak or a test."""

from __future__ import annotations

import asyncio
from datetime import datetime

from .tuya_protocol import (
    ProtocolError,
    Reassembler,
    decode_dps,
    decode_encrypted,
    encode_dp,
    encode_frame,
)


class SmartDotSession:
    def __init__(self, client, write_char, notify_char, credentials, emit, timeout=8, create_task=None):
        self.client = client
        self.write_char = write_char
        self.notify_char = notify_char
        self.credentials = credentials
        self.emit = emit
        self.timeout = timeout
        self.session_key = None
        self.authenticated = False
        self.sequence = 0
        self.transport_counter = 0
        self.pending = {}
        self.queue = asyncio.Queue(maxsize=64)
        self.reassembler = Reassembler()
        self.send_lock = asyncio.Lock()
        self.worker = None
        self.fatal = None
        self.max_write = None
        self.create_task = create_task or asyncio.create_task

    def notify(self, _sender, data):
        try:
            self.queue.put_nowait(bytes(data))
        except asyncio.QueueFull:
            self.fail(ProtocolError("Notification queue overflow"))

    def fail(self, error):
        if self.fatal is None:
            self.fatal = error
            for _, future in list(self.pending.values()):
                if not future.done():
                    future.set_exception(error)
            self.emit("session_error", error_type=type(error).__name__)

    def disconnected(self):
        self.authenticated = False
        self.fail(ProtocolError("Bluetooth disconnected; commands are not retried automatically"))

    async def start(self):
        for _ in range(30):
            self.max_write = self.write_char.max_write_without_response_size
            if self.max_write >= 133:
                break
            await asyncio.sleep(0.1)
        if self.max_write < 133:
            raise ProtocolError(
                "BLE write size is too small. At least 133 bytes are required for the supported connection sequence"
            )
        self.worker = self.create_task(self.receive_loop())
        await self.client.start_notify(self.notify_char, self.notify)
        _, _, _, data = await self.request(0, b"\x00\xf4", login=True)
        if len(data) < 46 or data[2] != 4 or data[5] == 0:
            raise ProtocolError("Device is not bound or returned unsupported device information")
        self.emit(
            "device_info", firmware=f"{data[0]}.{data[1]}", protocol=f"{data[2]}.{data[3]}", max_write=self.max_write
        )
        _, _, _, answer = await self.request(1, self.credentials.pair_payload())
        if len(answer) != 1 or answer[0] not in (0, 2):
            raise ProtocolError("Device rejected Tuya application authentication")
        self.authenticated = True
        self.emit("authenticated", status=answer[0])

    async def close(self):
        self.authenticated = False
        if self.worker:
            self.worker.cancel()
            try:
                await self.worker
            except asyncio.CancelledError:
                pass
            self.worker = None
        for _, future in list(self.pending.values()):
            if not future.done():
                future.cancel()
        self.pending.clear()
        if self.client.is_connected:
            try:
                await self.client.stop_notify(self.notify_char)
            except Exception as error:
                self.emit("notify_cleanup_failed", error_type=type(error).__name__)

    async def send(self, code, data, reply=0, login=False, expect_reply=False):
        async with self.send_lock:
            if self.fatal:
                raise self.fatal
            key = self.credentials.login_key if login else self.session_key
            if key is None:
                raise ProtocolError("Session key is not available yet")
            self.sequence += 1
            seq = self.sequence
            if callable(data):
                data = data(seq)
            packet = encode_frame(seq, reply, code, data, key, 4 if login else 5, self.transport_counter)
            self.transport_counter = (self.transport_counter + 1) & 15
            if self.max_write is None or len(packet) > self.max_write:
                raise ProtocolError("Packet exceeds the negotiated BLE write size; sending cancelled")
            future = asyncio.get_running_loop().create_future() if expect_reply else None
            if future is not None:
                self.pending[seq] = (code, future)
            try:
                await self.client.write_gatt_char(self.write_char, packet, response=False)
            except BaseException:
                self.pending.pop(seq, None)
                if future:
                    future.cancel()
                raise
            return seq, future

    async def request(self, code, data, login=False):
        seq, future = await self.send(code, data, login=login, expect_reply=True)
        try:
            return await asyncio.wait_for(asyncio.shield(future), self.timeout)
        except asyncio.TimeoutError:
            raise ProtocolError("No Tuya response to the command. The command was not retried automatically") from None
        finally:
            self.pending.pop(seq, None)
            if not future.done():
                future.cancel()

    async def receive_loop(self):
        try:
            while True:
                packet = await self.queue.get()
                encrypted = self.reassembler.feed(packet)
                if encrypted is None:
                    continue
                flag = encrypted[0]
                key = self.credentials.login_key if flag == 4 else self.session_key if flag == 5 else None
                if key is None:
                    raise ProtocolError("Unexpected security flag or missing session key")
                seq, reply, code, data = decode_encrypted(encrypted, key)
                if code == 0 and flag == 4:
                    if len(data) < 46:
                        raise ProtocolError("Device information response is too short")
                    self.session_key = self.credentials.session_key(data[6:12])
                # Never expose auth message bodies in logs.
                if reply in self.pending:
                    expected, future = self.pending[reply]
                    if code != expected:
                        raise ProtocolError("Response contains an unexpected command code")
                    if not future.done():
                        future.set_result((seq, reply, code, data))
                if code == 0x8011 and reply == 0:
                    now = datetime.now().astimezone()
                    offset = now.utcoffset()
                    tz = round(offset.total_seconds() / 36) if offset else 0
                    payload = str(int(now.timestamp() * 1000)).encode() + tz.to_bytes(2, "big", signed=True)
                    await self.send(0x8011, payload, reply=seq)
                    self.emit("clock_response")
                elif code == 0x8006:
                    if len(data) < 7 or data[0] != 0:
                        raise ProtocolError("Invalid DP v4 report")
                    self.emit("dp_report", datapoints=decode_dps(data[7:]))
                    if not data[5] & 0x80:
                        await self.send(code, data[:7] + b"\x00", reply=seq)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.fail(error if isinstance(error, ProtocolError) else ProtocolError("Failed to process BLE response"))

    async def command(self, name):
        if not self.authenticated:
            raise ProtocolError("Successful authentication is required first")
        if name == "status":
            self.emit("command_sent", command="status")
            _, _, _, data = await self.request(3, b"")
            if len(data) != 1:
                raise ProtocolError("Invalid status response")
            status = data[0]
        else:
            if name in ("small", "medium", "wide"):
                dp, kind, value = 104, 2, {"small": 1, "medium": 2, "wide": 3}[name]
            elif name == "off":
                dp, kind, value = 105, 1, False
            else:
                raise ProtocolError("Unknown command")
            klv = encode_dp(dp, kind, value)
            # The observed app uses frame sequence minus one as the DP sequence.
            self.emit("command_sent", command=name, dp=dp, value=value)
            _, _, _, data = await self.request(0x27, lambda seq: b"\x00" + (seq - 1).to_bytes(4, "big") + klv)
            if len(data) != 6:
                raise ProtocolError("Invalid DP v4 acknowledgement")
            status = data[-1]
        self.emit("command_ack", command=name, status=status)
        if status != 0:
            raise ProtocolError("Device returned a nonzero command status")
        # ACK confirms protocol acceptance; only the user can confirm physical effect.
        return status
