"""Ephemeral Petoneer mobile login and per-device BLE credential retrieval."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp
from cryptography.exceptions import InvalidTag
from tuya_mobile import TuyaMobileAppProfile, TuyaPasswordClient
from tuya_mobile.errors import (
    TuyaMobileAccountLocked,
    TuyaMobileCaptchaRequired,
    TuyaMobileError,
    TuyaMobileInvalidAuth,
    TuyaMobileMFARequired,
    TuyaMobileProfileExpired,
    TuyaMobileTransportError,
)

from .const import REGION_ENDPOINTS


class CloudError(Exception):
    """An error code safe to display in a config flow."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class UnsupportedServerError(Exception):
    """A server not in the vendor allowlist was advertised after login."""


class ApiError(Exception):
    """A server error, retaining its code but never its response body."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("Petoneer API request rejected")


def trusted_endpoint(url: str) -> bool:
    """Allow vendor HTTPS only, without following HTTP redirects."""
    try:
        parsed = urlparse(url)
        return bool(
            parsed.scheme == "https"
            and parsed.port in (None, 443)
            and not parsed.username
            and not parsed.password
            and parsed.hostname
            and (
                parsed.hostname == "a1.iot334.com"
                or any(
                    parsed.hostname == domain or parsed.hostname.endswith("." + domain)
                    for domain in ("tuyaeu.com", "tuyaus.com", "tuyacn.com", "tuyain.com", "iotbing.com")
                )
            )
        )
    except (ValueError, TypeError):
        return False


class VendorSession:
    """Use HA's HTTP session, restricting where credentials can be sent."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session

    def post(self, url: str, **kwargs: Any) -> Any:
        if not trusted_endpoint(url):
            raise UnsupportedServerError
        return self.session.post(url, allow_redirects=False, **kwargs)


class PetoneerMobileClient(TuyaPasswordClient):
    """Limit the mobile API to authentication and read-only setup queries."""

    _ACTIONS = frozenset(
        {
            "thing.m.user.username.token.get",
            "thing.m.user.email.password.login",
            "m.life.home.space.list",
            "m.life.my.group.device.list",
            "thing.m.device.get",
        }
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.login_endpoint = self.mobile_url

    @staticmethod
    def _endpoint_from_login(result: dict[str, Any]) -> str | None:
        """Accept either a regional base URL or an already complete API URL."""
        domain = result.get("domain")
        url = domain.get("mobileApiUrl") if isinstance(domain, dict) else None
        url = url or result.get("mobileApiUrl")
        if not isinstance(url, str) or not url:
            return None
        url = url.rstrip("/")
        return url if url.endswith("/api.json") else url + "/api.json"

    async def _submit_login(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        # Record the actual token/login server before the SDK applies the returned URL.
        self.login_endpoint = self.mobile_url
        return await super()._submit_login(*args, **kwargs)

    async def _call(self, action: str, payload: dict[str, Any], *, version: str = "1.0") -> Any:
        if action not in self._ACTIONS:
            raise CloudError("unsupported_api")
        try:
            return await super()._call(action, payload, version=version)
        except RuntimeError as error:
            match = re.search(r"failed: ([A-Za-z0-9_.-]{1,80})", str(error))
            raise ApiError(match.group(1) if match else "UNKNOWN") from None


@lru_cache(maxsize=1)
def load_profile() -> TuyaMobileAppProfile:
    """Read the public application identity; call from an executor."""
    data = json.loads(Path(__file__).with_name("petoneer_profile.json").read_text())
    data["endpoints"] = tuple(data["endpoints"])
    return TuyaMobileAppProfile(**data)


def walk(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def check_business_error(value: Any) -> None:
    for item in walk(value):
        if item.get("success") is False or item.get("errorCode"):
            raise ApiError(str(item.get("errorCode") or item.get("code") or "UNKNOWN"))


def safe_cloud_error(error: Exception) -> CloudError:
    """Translate expected failures without logging exception bodies."""
    if isinstance(error, CloudError):
        return error
    if isinstance(error, (aiohttp.ClientError, asyncio.TimeoutError, TuyaMobileTransportError, UnsupportedServerError)):
        return CloudError("cannot_connect")
    if isinstance(error, TuyaMobileCaptchaRequired):
        return CloudError("captcha_required")
    if isinstance(error, TuyaMobileMFARequired):
        return CloudError("mfa_required")
    if isinstance(error, TuyaMobileAccountLocked):
        return CloudError("account_locked")
    if isinstance(error, TuyaMobileInvalidAuth):
        return CloudError("invalid_auth")
    if isinstance(error, TuyaMobileProfileExpired):
        return CloudError("profile_expired")
    if isinstance(error, ApiError):
        code = error.code.upper()
        if "CAPTCHA" in code:
            return CloudError("captcha_required")
        if "MFA" in code or "VERIFY_CODE" in code:
            return CloudError("mfa_required")
        if "LOCK" in code or "FROZEN" in code:
            return CloudError("account_locked")
        if any(word in code for word in ("PASSWD", "PASSWORD", "USER_NOT_EXIST", "USER_NOT_FOUND")):
            return CloudError("invalid_auth")
        if "SIGN" in code or "APPKEY" in code or "ILLEGAL_APP" in code:
            return CloudError("profile_expired")
        return CloudError("cloud_error")
    return CloudError("cloud_error")


@dataclass(frozen=True)
class CloudDevice:
    """Only identifiers/labels are exposed in the device picker."""

    device_id: str = field(repr=False)
    name: str
    product_id: str
    uuid: str | None = field(default=None, repr=False)


class PetoneerAccount:
    """Keep password/session state in memory only during a single config flow."""

    def __init__(
        self, profile: TuyaMobileAppProfile, session: aiohttp.ClientSession, username: str, region: str = "auto"
    ) -> None:
        if "@" not in username.strip():
            raise CloudError("invalid_auth")
        if region != "auto" and region not in REGION_ENDPOINTS:
            raise CloudError("invalid_region")
        self.client = PetoneerMobileClient(
            profile,
            VendorSession(session),
            username=username.strip(),
            endpoint=REGION_ENDPOINTS.get(region),
            max_login_attempts=1,
            request_timeout=10,
        )
        self._devices: dict[str, CloudDevice] = {}

    async def async_login(self, password: str) -> None:
        try:
            # The SDK requires countryCode even for email login. Use its conventional
            # default; this does not select the cloud endpoint or an account country.
            await self.client.login_with_password(password, "1")
        except (
            TuyaMobileError,
            aiohttp.ClientError,
            asyncio.TimeoutError,
            ApiError,
            UnsupportedServerError,
            CloudError,
            ValueError,
            TypeError,
            KeyError,
            InvalidTag,
        ) as error:
            raise safe_cloud_error(error) from None

    async def _read(self, action: str, payload: dict[str, Any], version: str = "1.0") -> Any:
        """Retry only read-only requests on the server which issued this session."""
        if not self.client.mobile_session:
            raise CloudError("invalid_auth")
        try:
            try:
                response = await self.client._call(action, payload, version=version)
            except (aiohttp.ClientError, asyncio.TimeoutError, UnsupportedServerError):
                if self.client.mobile_url == self.client.login_endpoint:
                    raise
                # Some accounts advertise an unreachable alternate domain (iot334).
                # Never re-submit the password or forward sid to a different region.
                self.client.mobile_url = self.client.login_endpoint
                response = await self.client._call(action, payload, version=version)
            check_business_error(response)
            return response
        except (
            TuyaMobileError,
            aiohttp.ClientError,
            asyncio.TimeoutError,
            ApiError,
            UnsupportedServerError,
            CloudError,
            ValueError,
            TypeError,
            KeyError,
            InvalidTag,
        ) as error:
            raise safe_cloud_error(error) from None

    async def async_devices(self) -> dict[str, CloudDevice]:
        homes = await self._read("m.life.home.space.list", {})
        gids = {
            str(item.get("gid") or item.get("groupId") or item.get("homeId"))
            for item in walk(homes)
            if item.get("gid") or item.get("groupId") or item.get("homeId")
        }
        devices: dict[str, CloudDevice] = {}
        for gid in sorted(gids):
            response = await self._read("m.life.my.group.device.list", {"gid": gid}, "2.2")
            for item in walk(response):
                device_id = item.get("devId") or item.get("deviceId")
                if not device_id and any(
                    key in item for key in ("productId", "product_id", "uuid", "localKey", "local_key", "category")
                ):
                    device_id = item.get("id")
                if not device_id:
                    continue
                pid = str(item.get("productId") or item.get("product_id") or "")
                name = str(item.get("name") or item.get("devName") or "Unnamed device")
                devices[str(device_id)] = CloudDevice(str(device_id), name, pid, item.get("uuid"))
        self._devices = devices
        return devices

    async def async_credentials(self, device_id: str) -> dict[str, str]:
        if device_id not in self._devices:
            raise CloudError("device_not_found")
        selected = self._devices[device_id]
        response = await self._read("thing.m.device.get", {"devId": device_id}, "4.1")
        device = next(
            (
                item
                for item in walk(response)
                if str(item.get("devId") or item.get("deviceId") or item.get("id") or "") == device_id
                and (item.get("localKey") or item.get("local_key"))
            ),
            None,
        )
        if device is None:
            raise CloudError("missing_keys")
        pid = device.get("productId") or device.get("product_id") or selected.product_id
        data = {
            "device_id": device_id,
            "product_id": pid,
            "uuid": device.get("uuid") or selected.uuid,
            "local_key": device.get("localKey") or device.get("local_key"),
        }
        if any(
            not isinstance(data[key], str) or len(data[key]) != 16 or not data[key].isascii()
            for key in ("device_id", "uuid", "local_key")
        ):
            raise CloudError("missing_keys")
        if sec_key := device.get("secKey") or device.get("sec_key"):
            if not isinstance(sec_key, str) or len(sec_key) != 16 or not sec_key.isascii():
                raise CloudError("missing_keys")
            data["sec_key"] = sec_key
        return data

    def close(self) -> None:
        """Release account/session secrets; HA owns the HTTP session."""
        self.client.sid = self.client.ecode = self.client.uid = None
        self.client.mobile_session = None
        self.client.username = ""
        self.client.device_id = ""
        self._devices.clear()
