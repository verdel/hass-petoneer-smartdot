from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, MODES


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Setup select entity."""

    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SmartDotSelectEntity(data)])


class SmartDotSelectEntity(SelectEntity, RestoreEntity):
    """Petoneer SmartDot select entity for game mode change."""

    _attr_should_poll = False

    def __init__(self, data) -> None:
        """Initialize the game mode select entity."""

        self._attr_unique_id = f"{data.get('id')}_game_preset"
        self._attr_name = "Game preset"
        self._attr_translation_key = "preset"
        self._attr_options = [key for key in MODES if key != "stop"]
        self._attr_icon = "mdi:paw"
        self._mac = data.get("mac")
        self._attr_current_option = "small"

    async def async_added_to_hass(self) -> None:
        """Restore last state when added."""
        last_state = await self.async_get_last_state()
        if last_state:
            self._attr_current_option = last_state.state

    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        if option not in self.options:
            raise ValueError(f"Invalid option for {self.entity_id}: {option}")

        self._attr_current_option = option
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=f"Petoneer SmartDot ({self._mac})",
            manufacturer="Petoneer",
            model="SmartDot",
        )
