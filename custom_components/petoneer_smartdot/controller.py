"""One BLE controller per entry, using the correct generation's protocol."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from bleak import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_GENERATION, GENERATION_V1, GENERATION_V2, MODES, UUID_CONTROL_MODE
from .tuya_protocol import NOTIFY_UUID, WRITE_UUID, Credentials, ProtocolError
from .tuya_session import SmartDotSession

_LOGGER = logging.getLogger(__name__)
IDLE_SECONDS = 30


class SmartDotController:
    """Serialize commands and keep personal keys separate from shared protocol code."""

    def __init__(self, hass: HomeAssistant, address: str, data: dict[str, Any]) -> None:
        self.hass = hass
        self.address = address
        self.generation = data.get(CONF_GENERATION, GENERATION_V1)
        self.credentials = Credentials.from_dict(data) if self.generation == GENERATION_V2 else None
        self.preset = "small"
        self._client: BleakClientWithServiceCache | None = None
        self._session: SmartDotSession | None = None
        self._lock = asyncio.Lock()
        self._idle_cancel: asyncio.TimerHandle | None = None
        self.firmware: str | None = None

    def _ble_device(self) -> Any:
        return bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)

    def _disconnected(self, _client: Any) -> None:
        if self._session is not None:
            self._session.disconnected()

    def _event(self, event: str, **fields: Any) -> None:
        # No encrypted/auth packet bodies, device identifiers or keys in logs.
        if event == "device_info":
            self.firmware = fields.get("firmware")
        _LOGGER.debug("SmartDot %s: %s", self.generation, event)

    async def _connect(self) -> None:
        if self._client and self._client.is_connected:
            if self.generation == GENERATION_V1 or (
                self._session and self._session.authenticated and self._session.fatal is None
            ):
                return
        await self._disconnect()
        device = self._ble_device()
        if device is None:
            raise ProtocolError("SmartDot is not visible to a connectable Bluetooth adapter")
        self._client = await establish_connection(
            BleakClientWithServiceCache,
            device,
            "Petoneer SmartDot",
            disconnected_callback=self._disconnected,
            ble_device_callback=self._ble_device,
            max_attempts=2,
        )
        if self.generation == GENERATION_V2:
            write = self._client.services.get_characteristic(WRITE_UUID)
            notify = self._client.services.get_characteristic(NOTIFY_UUID)
            if write is None or notify is None:
                raise ProtocolError("SmartDot V2 FD50 characteristics are missing")
            self._session = SmartDotSession(
                self._client,
                write,
                notify,
                self.credentials,
                self._event,
                create_task=lambda coro: self.hass.async_create_background_task(
                    coro, "Petoneer SmartDot BLE notifications"
                ),
            )
            await self._session.start()

    async def async_validate(self) -> None:
        """Validate selected cloud keys against this BLE device, without playing."""
        async with self._lock:
            try:
                await self._connect()
            finally:
                await self._disconnect()

    def _cancel_idle(self) -> None:
        if self._idle_cancel:
            self._idle_cancel.cancel()
            self._idle_cancel = None

    async def _disconnect(self) -> None:
        self._cancel_idle()
        session, self._session = self._session, None
        client, self._client = self._client, None
        if session:
            await session.close()
        if client and client.is_connected:
            await client.disconnect()

    async def async_disconnect(self) -> None:
        async with self._lock:
            await self._disconnect()

    def _idle_disconnect(self) -> None:
        self._idle_cancel = None
        self.hass.async_create_task(self.async_disconnect(), "Disconnect idle SmartDot")

    async def async_command(self, command: str) -> None:
        """Send once; connection retries never re-send an actuation command."""
        if command not in MODES:
            raise HomeAssistantError("Unsupported SmartDot command")
        async with self._lock:
            self._cancel_idle()
            try:
                await self._connect()
                if self.generation == GENERATION_V1:
                    await self._client.write_gatt_char(UUID_CONTROL_MODE, bytes.fromhex(MODES[command]), response=False)
                    await asyncio.sleep(0.1)
                    await self._disconnect()
                else:
                    await self._session.command({"large": "wide", "stop": "off"}.get(command, command))
                    self._idle_cancel = self.hass.loop.call_later(IDLE_SECONDS, self._idle_disconnect)
            except asyncio.CancelledError:
                await self._disconnect()
                raise
            except (BleakError, ProtocolError, asyncio.TimeoutError, OSError):
                await self._disconnect()
                # Do not expose Bleak/native exceptions which may contain auth payloads.
                raise HomeAssistantError(
                    "SmartDot command failed; check Bluetooth connection and device credentials"
                ) from None
