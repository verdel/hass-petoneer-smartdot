"""Petoneer SmartDot V1 and V2 integration."""

from __future__ import annotations

from homeassistant.components.bluetooth import async_ble_device_from_address, async_scanner_count
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_GENERATION, GENERATION_V1, PLATFORMS
from .controller import SmartDotController


def normalize_address(address: str) -> str:
    """Preserve full CoreBluetooth UUIDs as well as ordinary BLE MAC addresses."""
    import re
    from uuid import UUID

    address = address.strip()
    compact = address.replace(":", "").replace("-", "")
    if re.fullmatch(r"[0-9A-Fa-f]{12}", compact):
        return ":".join(compact[i : i + 2] for i in range(0, 12, 2)).upper()
    try:
        return str(UUID(address)).upper()
    except ValueError:
        raise ValueError("Invalid Bluetooth address") from None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up both generations; old entries default to the original protocol."""
    address = normalize_address(entry.data[CONF_MAC])
    device = async_ble_device_from_address(hass, address, connectable=True)
    if device is None:
        if async_scanner_count(hass, connectable=True) < 1:
            raise ConfigEntryNotReady("A Bluetooth adapter or an active ESPHome Bluetooth proxy is required")
        raise ConfigEntryNotReady("SmartDot is not currently visible to Bluetooth")
    entry.runtime_data = SmartDotController(hass, address, dict(entry.data))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_disconnect()
        return True
    return False


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Preserve existing V1 unique IDs, entry IDs and entity IDs."""
    if entry.version > 2:
        return False
    if entry.version == 1:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_GENERATION: GENERATION_V1},
            version=2,
        )
    return True
