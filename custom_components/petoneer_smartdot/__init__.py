"""The Petoneer SmartDot integration."""

import logging

from homeassistant.components.bluetooth import async_ble_device_from_address, async_scanner_count
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up petoneer_smartdot from a config entry."""
    _LOGGER.debug("integration async setup entry: {entry.as_dict()}")
    hass.data.setdefault(DOMAIN, {})

    address = entry.data.get(CONF_MAC)

    ble_device = async_ble_device_from_address(hass, address.upper(), connectable=True)
    _LOGGER.debug("BLE device through HA bt: %s", ble_device)
    if ble_device is None:
        count_scanners = async_scanner_count(hass, connectable=True)
        _LOGGER.debug("Count of BLE scanners in HA bt: %s", count_scanners)
        if count_scanners < 1:
            raise ConfigEntryNotReady(
                "No bluetooth scanner detected. \
                Enable the bluetooth integration or ensure an esphome device \
                is running as a bluetooth proxy"
            )
        raise ConfigEntryNotReady(f"Could not find Petoneer SmartDot with address {address}")

    hass.data[DOMAIN][entry.entry_id] = {"id": entry.entry_id, "device": ble_device, "mac": address}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("async unload entry")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
