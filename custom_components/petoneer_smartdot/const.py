"""Constants for both Petoneer SmartDot generations."""

from homeassistant.const import Platform

DOMAIN = "petoneer_smartdot"
UUID_CONTROL_MODE = "0000fff3-0000-1000-8000-00805f9b34fb"
MODES = {
    "stop": "0f0407000008",
    "small": "0f0405000107",
    "medium": "0f0405000208",
    "large": "0f0405000309",
}
CONF_ENTRY_METHOD = "entry_method"
CONF_ENTRY_SCAN = "Scan"
CONF_ENTRY_MANUAL = "Enter MAC manually"
CONF_GENERATION = "generation"
CONF_CLOUD_DEVICE = "cloud_device"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_UUID = "uuid"
CONF_LOCAL_KEY = "local_key"
CONF_SEC_KEY = "sec_key"
CONF_PRODUCT_ID = "product_id"
CONF_REGION = "region"
GENERATION_V1 = "v1"
GENERATION_V2 = "v2"
PLATFORMS = [Platform.SELECT, Platform.BUTTON]
SECRET_FIELDS = {
    CONF_LOCAL_KEY,
    CONF_SEC_KEY,
    CONF_DEVICE_ID,
    CONF_DEVICE_UUID,
    "password",
    "username",
    "email",
    "sid",
    "ecode",
    "token",
}
REGION_ENDPOINTS = {
    "europe": "https://a1.tuyaeu.com/api.json",
    "america": "https://a1.tuyaus.com/api.json",
    "singapore": "https://a1-sg.iotbing.com/api.json",
    "china": "https://a1.tuyacn.com/api.json",
    "india": "https://a1.tuyain.com/api.json",
}
