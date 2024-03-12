"""Constants for the Petoneer SmartDot integration."""

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
PLATFORMS: list[str] = ["select", "button"]
