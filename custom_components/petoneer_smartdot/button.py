"""Start/stop buttons for both generations."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import SmartDotEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([SmartDotStartButtonEntity(entry), SmartDotStopButtonEntity(entry)])


class SmartDotStartButtonEntity(SmartDotEntity, ButtonEntity):
    _attr_name = "Start"
    _attr_icon = "mdi:play"

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_start_game"

    async def async_press(self) -> None:
        await self.controller.async_command(self.controller.preset)


class SmartDotStopButtonEntity(SmartDotEntity, ButtonEntity):
    _attr_name = "Stop"
    _attr_icon = "mdi:stop"

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_stop_game"

    async def async_press(self) -> None:
        await self.controller.async_command("stop")
