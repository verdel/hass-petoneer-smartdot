"""Petoneer SmartDot V2 Tuya BLE 4.2 codec. No network or Bluetooth operations."""

from __future__ import annotations

import hashlib
import secrets
import struct
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

WRITE_UUID = "00000001-0000-1001-8001-00805f9b07d0"
NOTIFY_UUID = "00000002-0000-1001-8001-00805f9b07d0"
SERVICE_UUID = "0000fd50-0000-1000-8000-00805f9b34fb"


class ProtocolError(Exception):
    pass


@dataclass(frozen=True)
class Credentials:
    device_id: str = field(repr=False)
    uuid: str = field(repr=False)
    local_key: str = field(repr=False)
    product_id: str = ""

    @classmethod
    def from_dict(cls, d):
        c = cls(
            **{k: d[k] for k in ("device_id", "uuid", "local_key")},
            product_id=d.get("product_id") or "",
        )
        try:
            lengths = tuple(len(v.encode("ascii")) for v in (c.device_id, c.uuid, c.local_key))
        except (AttributeError, UnicodeError):
            raise ProtocolError("Invalid credential format") from None
        if lengths != (16, 16, 16):
            raise ProtocolError("This model requires device_id, uuid and local_key to each contain 16 ASCII bytes")
        return c

    @property
    def login_key(self):
        return hashlib.md5(self.local_key.encode()[:6], usedforsecurity=False).digest()

    def session_key(self, random6):
        if len(random6) != 6:
            raise ProtocolError("Invalid device random length")
        return hashlib.md5(self.local_key.encode()[:6] + random6, usedforsecurity=False).digest()

    def pair_payload(self):
        # Exact 46-byte layout observed in both iPhone captures.
        return (
            self.uuid.encode()
            + self.local_key.encode()[:6]
            + self.device_id.encode()
            + bytes.fromhex("0000000000000005")
        )


def crc16(data):
    c = 0xFFFF
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ (0xA001 if c & 1 else 0)
    return c


def pack_varint(n):
    if not 0 <= n <= 0xFFFFFFFF:
        raise ProtocolError("Varint out of range")
    out = bytearray()
    while n >= 128:
        out.append((n & 127) | 128)
        n >>= 7
    out.append(n)
    return bytes(out)


def unpack_varint(data, pos=0):
    n = 0
    for shift in range(0, 35, 7):
        if pos >= len(data):
            raise ProtocolError("Incomplete header")
        b = data[pos]
        pos += 1
        n |= (b & 127) << shift
        if b < 128:
            return n, pos
    raise ProtocolError("Varint is too long")


def encode_frame(seq, reply, code, data, key, flag, transport_counter=0, iv=None):
    iv = secrets.token_bytes(16) if iv is None else iv
    raw = struct.pack(">IIHH", seq, reply, code, len(data)) + data
    raw += struct.pack(">H", crc16(raw))
    # The observed iPhone adds an entire zero block for aligned plaintext.
    raw += bytes(16 - len(raw) % 16)
    e = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    encrypted = bytes([flag]) + iv + e.update(raw) + e.finalize()
    return pack_varint(0) + pack_varint(len(encrypted)) + bytes([0x40 | (transport_counter & 15)]) + encrypted


def decode_encrypted(message, key):
    if len(message) < 33 or (len(message) - 17) % 16:
        raise ProtocolError("Invalid ciphertext length")
    d = Cipher(algorithms.AES(key), modes.CBC(message[1:17])).decryptor()
    raw = d.update(message[17:]) + d.finalize()
    seq, reply, code, n = struct.unpack(">IIHH", raw[:12])
    end = 12 + n
    if end + 2 > len(raw) or len(raw) - end - 2 > 16:
        raise ProtocolError("Decrypted payload length mismatch")
    if crc16(raw[:end]) != int.from_bytes(raw[end : end + 2], "big"):
        raise ProtocolError("CRC mismatch; incorrect key or unsupported response format")
    pad = raw[end + 2 :]
    if pad and any(pad) and pad != bytes([len(pad)]) * len(pad):
        raise ProtocolError("Invalid AES padding")
    return seq, reply, code, raw[12:end]


class Reassembler:
    def __init__(self):
        self.clear()

    def clear(self):
        self.data = bytearray()
        self.expected = 0
        self.total = None

    def feed(self, packet):
        number, pos = unpack_varint(packet)
        if number == 0:
            self.clear()
            self.total, pos = unpack_varint(packet, pos)
            if not 33 <= self.total <= 4096:
                raise ProtocolError("Invalid message length")
            if pos >= len(packet) or packet[pos] >> 4 != 4:
                raise ProtocolError("Expected Tuya protocol v4")
            pos += 1
        if self.total is None or number != self.expected:
            self.clear()
            raise ProtocolError("BLE fragments received out of order")
        self.data.extend(packet[pos:])
        self.expected += 1
        if len(self.data) > self.total:
            self.clear()
            raise ProtocolError("BLE message exceeds its declared length")
        if len(self.data) == self.total:
            result = bytes(self.data)
            self.clear()
            return result
        return None


def encode_dp(dp, kind, value):
    # Deliberately narrow command set; no resets, OTA, schedules or unknown DPs.
    if dp == 104 and kind == 2 and type(value) is int and value in (1, 2, 3):
        raw = value.to_bytes(4, "big")
    elif dp == 105 and kind == 1 and value is False:
        raw = bytes([value])
    else:
        raise ProtocolError("Command is outside the verified command set")
    return bytes([dp, kind]) + len(raw).to_bytes(2, "big") + raw


def decode_dps(data):
    result = []
    pos = 0
    while pos < len(data):
        if pos + 4 > len(data):
            raise ProtocolError("Incomplete DP header")
        dp, kind = data[pos : pos + 2]
        n = int.from_bytes(data[pos + 2 : pos + 4], "big")
        pos += 4
        value = data[pos : pos + n]
        if len(value) != n:
            raise ProtocolError("Incomplete DP value")
        pos += n
        item = {"id": dp, "type": kind, "length": n}
        if kind == 1 and n == 1:
            item["value"] = bool(value[0])
        elif kind in (2, 4, 5):
            item["value"] = int.from_bytes(value, "big")
        elif dp == 102 and kind == 0 and n == 4:
            item["raw_hex"] = value.hex()
        # Unknown raw/string reports (e.g. schedules) are not exported.
        result.append(item)
    return result
