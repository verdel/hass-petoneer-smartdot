"""Choose the game preset without starting a game."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import MODES
from .entity import SmartDotEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([SmartDotSelectEntity(entry)])


class SmartDotSelectEntity(SmartDotEntity, SelectEntity, RestoreEntity):
    """Select the game preset for either SmartDot generation."""

    _attr_name = "Game preset"
    _attr_translation_key = "preset"
    _attr_options = [key for key in MODES if key != "stop"]
    _attr_icon = "mdi:paw"

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_game_preset"
        self._attr_current_option = "small"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) and last_state.state in self.options:
            self._attr_current_option = last_state.state
        self.controller.preset = self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            raise ValueError("Invalid SmartDot preset")
        self.controller.preset = option
        self._attr_current_option = option
        self.async_write_ha_state()
