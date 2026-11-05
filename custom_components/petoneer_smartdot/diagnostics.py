"""Diagnostics never include per-device or account credentials."""

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import SECRET_FIELDS


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    return async_redact_data(entry.as_dict(), SECRET_FIELDS)
