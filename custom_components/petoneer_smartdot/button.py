import asyncio
import logging

from bleak import BleakClient, BleakError
from bleak_retry_connector import establish_connection
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_entries_for_config_entry, async_get

from .const import DOMAIN, MODES, UUID_CONTROL_MODE

_LOGGER = logging.getLogger(__name__)


async def get_select_entity_value(hass, entry_id) -> str | None:
    """Get game mode from select entity value."""

    entity_registry = async_get(hass)
    entries = async_entries_for_config_entry(entity_registry, entry_id)
    select_entities = [entry for entry in entries if entry.domain == "select"]

    if select_entities:
        select_entity_id = select_entities[0].entity_id
        select_entity_state = hass.states.get(select_entity_id)
        return select_entity_state.state

    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Setup button entities."""

    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SmartDotStartButtonEntity(hass, entry.entry_id, data), SmartDotStopButtonEntity(data)])


class SmartDotStartButtonEntity(ButtonEntity):
    """Petoneer SmartDot button entity for game start."""

    _attr_should_poll = False

    def __init__(self, hass, entry_id, data) -> None:
        """Initialize the button entity."""

        self._attr_unique_id = f"{data.get('id')}_start_game"
        self._attr_name = "Start"
        self._attr_icon = "mdi:play"
        self._mac = data.get("mac")
        self._ble_device = data.get("device")
        self._hass = hass
        self._entry_id = entry_id

        _LOGGER.debug("Initializing BLE Device %s (%s)", self._ble_device.name, self._mac)
        _LOGGER.debug("BLE_device details: %s", self._ble_device.details)

    async def async_press(self) -> None:
        """Restore last state when added."""
        game_mode = await get_select_entity_value(self._hass, self._entry_id)
        if game_mode is None:
            _LOGGER.debug("Select game mode first")
            return
        _LOGGER.debug("Current game mode: %s", game_mode)
        _LOGGER.debug("Connecting")
        try:
            client = await establish_connection(
                client_class=BleakClient, device=self._ble_device, name=self._ble_device.address
            )
        except asyncio.TimeoutError:
            _LOGGER.error("Connection Timeout error")
        except BleakError as err:
            _LOGGER.error("Connection: BleakError: %s", err)

        try:
            _LOGGER.debug("Sending command")
            await client.write_gatt_char(
                UUID_CONTROL_MODE,
                bytearray.fromhex(MODES[game_mode]),
                response=False,
            )
            await asyncio.sleep(0.1)
        except asyncio.TimeoutError:
            _LOGGER.error("Connection Timeout error")
        except BleakError as err:
            _LOGGER.error("Connection: BleakError: %s", err)
        await client.disconnect()
        _LOGGER.debug("Disconnected")

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=f"Petoneer SmartDot ({self._mac})",
            manufacturer="Petoneer",
            model="SmartDot",
        )


class SmartDotStopButtonEntity(ButtonEntity):
    """Petoneer SmartDot button entity for game stop."""

    _attr_should_poll = False

    def __init__(self, data) -> None:
        """Initialize the button entity."""

        self._attr_unique_id = f"{data.get('id')}_stop_game"
        self._attr_name = "Stop"
        self._attr_icon = "mdi:stop"
        self._mac = data.get("mac")
        self._ble_device = data.get("device")
        _LOGGER.debug("Initializing BLE Device %s (%s)", self._ble_device.name, self._mac)
        _LOGGER.debug("BLE_device details: {self._ble_device.details}")

    async def async_press(self) -> None:
        """Restore last state when added."""
        _LOGGER.debug("Connecting")
        try:
            client = await establish_connection(
                client_class=BleakClient, device=self._ble_device, name=self._ble_device.address
            )
        except asyncio.TimeoutError:
            _LOGGER.error("Connection Timeout error")
        except BleakError as err:
            _LOGGER.error("Connection: BleakError: %s", err)

        try:
            _LOGGER.debug("Sending command")
            await client.write_gatt_char(
                UUID_CONTROL_MODE,
                bytearray.fromhex(MODES["stop"]),
                response=False,
            )
            await asyncio.sleep(0.1)
        except asyncio.TimeoutError:
            _LOGGER.error("Connection Timeout error")
        except BleakError as err:
            _LOGGER.error("Connection: BleakError: %s", err)
        await client.disconnect()
        _LOGGER.debug("Disconnected")

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=f"Petoneer SmartDot ({self._mac})",
            manufacturer="Petoneer",
            model="SmartDot",
        )
