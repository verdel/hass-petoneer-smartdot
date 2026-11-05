"""Shared device metadata, without per-device secrets."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, GENERATION_V2
from .controller import SmartDotController


class SmartDotEntity(Entity):
    """An entity belonging to a single SmartDot controller."""

    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self.controller: SmartDotController = entry.runtime_data
        self.entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.data[CONF_MAC])},
            name=self.entry.data.get(CONF_NAME) or f"Petoneer SmartDot ({self.entry.data[CONF_MAC]})",
            manufacturer="Petoneer",
            model="SmartDot V2" if self.controller.generation == GENERATION_V2 else "SmartDot",
            sw_version=self.controller.firmware,
        )
