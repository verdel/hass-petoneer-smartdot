"""Configure either generation; obtain V2 keys through an ephemeral Petoneer login."""

from __future__ import annotations

from typing import Any

# Home Assistant switched its schema engine in 2026. Keep older installs usable.
try:
    import probatio as vol
except ImportError:
    import voluptuous as vol

from bleak import BleakError
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.const import CONF_MAC, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import normalize_address
from .cloud import CloudError, PetoneerAccount, load_profile
from .const import (
    CONF_CLOUD_DEVICE,
    CONF_GENERATION,
    CONF_REGION,
    DOMAIN,
    GENERATION_V1,
    GENERATION_V2,
    REGION_ENDPOINTS,
)
from .controller import SmartDotController
from .tuya_protocol import SERVICE_UUID, ProtocolError


def generation_from_advertisement(info: bluetooth.BluetoothServiceInfoBleak) -> str | None:
    if info.name == "PetCat":
        return GENERATION_V1
    if SERVICE_UUID in info.service_uuids or SERVICE_UUID in info.service_data:
        return GENERATION_V2
    return None


class SmartDotFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Support existing entries, new devices and explicit key refresh."""

    VERSION = 2

    def __init__(self) -> None:
        self._devices: dict[str, str] = {}
        self._generations: dict[str, str] = {}
        self._data: dict[str, Any] = {}
        self._account: PetoneerAccount | None = None
        self._cloud_devices = {}
        self._account_options: dict[str, str] = {}
        self._entry = None
        self._updating = "reconfigure"

    def _close_account(self) -> None:
        if self._account:
            self._account.close()
            self._account = None
        self._cloud_devices = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.async_show_menu(step_id="user", menu_options=["scan", "manual"])

    async def async_step_bluetooth(self, discovery_info: bluetooth.BluetoothServiceInfoBleak) -> FlowResult:
        generation = generation_from_advertisement(discovery_info)
        if generation is None:
            return self.async_abort(reason="not_supported")
        address = normalize_address(discovery_info.address)
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()
        self._devices = {address: f"{discovery_info.name} ({address})"}
        self._generations = {address: generation}
        self.context["title_placeholders"] = {"name": "Petoneer SmartDot"}
        return await self.async_step_device()

    async def async_step_scan(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        # Use HA's shared manager; do not start an independent scanner or bypass proxies.
        self._devices = {}
        self._generations = {}
        for info in bluetooth.async_discovered_service_info(self.hass, connectable=True):
            if (generation := generation_from_advertisement(info)) is not None:
                address = normalize_address(info.address)
                self._devices[address] = f"{info.name} ({address})"
                self._generations[address] = generation
        if not self._devices:
            return self.async_show_form(step_id="scan", errors={"base": "no_devices_found"})
        return await self.async_step_device()

    async def _set_address(self, address: str) -> bool:
        for entry in self._async_current_entries():
            if entry.unique_id == address and (self._entry is None or entry.entry_id != self._entry.entry_id):
                return False
        if self.source == config_entries.SOURCE_USER:
            # Closing the dialog can leave the previous flow alive. An explicit
            # selection takes over setup of this address and releases its session.
            for progress in self._async_in_progress(match_context={"unique_id": address}):
                if progress["context"]["source"] in (
                    config_entries.SOURCE_USER,
                    config_entries.SOURCE_BLUETOOTH,
                ):
                    self.hass.config_entries.flow.async_abort(progress["flow_id"])
        await self.async_set_unique_id(address)
        self._data[CONF_MAC] = address
        return True

    async def async_step_device(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors = {}
        if user_input is not None:
            address = user_input[CONF_MAC]
            if address not in self._devices:
                errors["base"] = "invalid_address"
            elif not await self._set_address(address):
                return self.async_abort(reason="already_configured")
            else:
                self._data[CONF_GENERATION] = self._generations[address]
                if user_input.get(CONF_NAME):
                    self._data[CONF_NAME] = user_input[CONF_NAME]
                return await self._next_generation()
        return self.async_show_form(
            step_id="device",
            errors=errors,
            data_schema=vol.Schema({vol.Required(CONF_MAC): vol.In(self._devices), vol.Optional(CONF_NAME): str}),
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors = {}
        if user_input is not None:
            try:
                address = normalize_address(user_input[CONF_MAC])
            except ValueError:
                errors[CONF_MAC] = "invalid_address"
            else:
                if not await self._set_address(address):
                    return self.async_abort(reason="already_configured")
                self._data[CONF_GENERATION] = user_input[CONF_GENERATION]
                if user_input.get(CONF_NAME):
                    self._data[CONF_NAME] = user_input[CONF_NAME]
                return await self._next_generation()
        return self.async_show_form(
            step_id="manual",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAC, default=self._data.get(CONF_MAC, "")): str,
                    vol.Required(
                        CONF_GENERATION, default=self._data.get(CONF_GENERATION, GENERATION_V1)
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[GENERATION_V1, GENERATION_V2], translation_key="generation"
                        )
                    ),
                    vol.Optional(CONF_NAME, default=self._data.get(CONF_NAME, "")): str,
                }
            ),
        )

    async def _next_generation(self) -> FlowResult:
        if self._data[CONF_GENERATION] == GENERATION_V2:
            return await self.async_step_account()
        self._close_account()
        # A V2-to-V1 reconfigure must remove the old personal credentials.
        self._data = {k: v for k, v in self._data.items() if k in (CONF_MAC, CONF_NAME, CONF_GENERATION)}
        return await self._finish()

    async def async_step_account(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors = {}
        if user_input is not None:
            self._close_account()
            self._account_options = {CONF_REGION: user_input[CONF_REGION]}
            try:
                profile = await self.hass.async_add_executor_job(load_profile)
                self._account = PetoneerAccount(
                    profile, async_get_clientsession(self.hass), user_input[CONF_USERNAME], user_input[CONF_REGION]
                )
                await self._account.async_login(user_input[CONF_PASSWORD])
                self._cloud_devices = await self._account.async_devices()
                if not self._cloud_devices:
                    raise CloudError("no_cloud_devices")
            except CloudError as error:
                errors["base"] = error.code
                self._close_account()
            else:
                return await self.async_step_cloud_device()
            finally:
                # Do not retain a password even if login or region discovery failed.
                user_input.pop(CONF_PASSWORD, None)
        options = self._account_options or self._data
        return self.async_show_form(
            step_id="account",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                    vol.Required(CONF_REGION, default=options.get(CONF_REGION, "auto")): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=["auto", *REGION_ENDPOINTS], translation_key="region")
                    ),
                }
            ),
        )

    async def async_step_cloud_device(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._account is None:
            return await self.async_step_account()
        errors = {}
        if user_input is not None:
            device_id = user_input[CONF_CLOUD_DEVICE]
            if device_id not in self._cloud_devices:
                errors["base"] = "device_not_found"
            else:
                try:
                    keys = await self._account.async_credentials(device_id)
                    candidate = {
                        CONF_MAC: self._data[CONF_MAC],
                        CONF_GENERATION: GENERATION_V2,
                        **self._account_options,
                        **keys,
                    }
                    candidate[CONF_NAME] = self._data.get(CONF_NAME) or self._cloud_devices[device_id].name
                    controller = SmartDotController(self.hass, candidate[CONF_MAC], candidate)
                    # A correct cloud device must match the selected physical BLE device.
                    await controller.async_validate()
                except CloudError as error:
                    errors["base"] = error.code
                except (ProtocolError, BleakError, TimeoutError, OSError):
                    errors["base"] = "cannot_connect_ble"
                else:
                    self._data = candidate
                    self._close_account()
                    return await self._finish()
        labels = {
            device_id: f"{device.name} ({device.product_id + ', ' if device.product_id else ''}…{device_id[-4:]})"
            for device_id, device in self._cloud_devices.items()
        }
        return self.async_show_form(
            step_id="cloud_device",
            errors=errors,
            data_schema=vol.Schema({vol.Required(CONF_CLOUD_DEVICE): vol.In(labels)}),
        )

    async def _finish(self) -> FlowResult:
        if self._entry is not None:
            self.hass.config_entries.async_update_entry(
                self._entry,
                data=self._data,
                title=self._data.get(CONF_NAME) or self._data[CONF_MAC],
                unique_id=self._data[CONF_MAC],
            )
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            return self.async_abort(
                reason="reauth_successful" if self._updating == "reauth" else "reconfigure_successful"
            )
        return self.async_create_entry(title=self._data.get(CONF_NAME) or self._data[CONF_MAC], data=self._data)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        self._entry = self._get_reauth_entry()
        self._data = dict(self._entry.data)
        self._updating = "reauth"
        return await self.async_step_account()

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        self._entry = self._get_reconfigure_entry()
        self._data = dict(self._entry.data)
        if self._data.get(CONF_GENERATION, GENERATION_V1) == GENERATION_V2:
            return await self.async_step_account()
        return await self.async_step_manual()

    @callback
    def async_remove(self) -> None:
        """Discard ephemeral cloud sessions when the user cancels the flow."""
        self._close_account()
        super().async_remove()
