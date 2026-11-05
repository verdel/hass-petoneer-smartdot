# Home Assistant custom component for Petoneer SmartDot

This custom component controls both the original Petoneer SmartDot and SmartDot V2 locally via Bluetooth.

![Petoneer SmartDot](assets/petoneer-smartdot.png)

Requires Home Assistant **2026.10 or newer** and a Bluetooth adapter or an **active ESPHome Bluetooth proxy**.
Existing original SmartDot entries are migrated automatically, preserving their entities.

# Installation

This custom component can be installed in two different ways: `manually` or `using HACS`

## 1. Installation using HACS (recommended)

This repo is now in [HACS](https://hacs.xyz/).

1. Install HACS follow the instructions [here](https://hacs.xyz/docs/setup/prerequisites)
2. Search for `Petoneer SmartDot`
3. Install and enjoy automatic updates

## 2. Manual Installation

1. Download the zip file from the
   [latest release](https://github.com/verdel/hass-petoneer-smartdot/releases/latest).
2. Unpack the release and copy the `custom_components/petoneer_smartdot` directory
   into the `custom_components` directory of your Home Assistant
   installation.
3. Ensure bluez is installed and accessible from HA (refer to next section)
4. Add the `petoneer_smartdot` as described in next section.

## Ensure Host bluetooth is accessible from Home-Assistant

This component uses [`bleak`](https://github.com/hbldh/bleak) to access Bluetooth through Home Assistant.
For a local Linux adapter, BlueZ must be installed and accessible to HA:

- for **Home Assistant Operating System**:
  Bluetooth support is included; configure the Bluetooth integration in HA.

- For **Home Assistant Container** in docker:

  Ensure your host has the `bluetoothctl` binary on the system (coming from `bluez` or `bluez-util` package, depending on the distro).
  The docker-compose container (or equivalent docker command) should link _/var/run/dbus_ with host folder through a volume and _NET_ADMIN_ permission is needed. docker compose extract:

  ```yaml
  volumes:
    - /run/dbus:/run/dbus:ro
  cap_add:
    - NET_ADMIN
    - NET_RAW
  network_mode: host
  ```

- For **Home Assistant Core** installed in a Virtualenv:

  Ensure your host has the `bluetoothctl` binary on the system (coming from `bluez` or `bluez-util` package, depending on the distro).
  Make sure the user running HA belongs to the `bluetooth` group.

# Homeassistant component configuration

## Adding the device to HA

You must have the `bluetooth` integration enabled and configured or an ESPHome device running an active Bluetooth proxy.
A proxy that only forwards advertisements cannot control the toy. A nearby SmartDot may also be offered through automatic discovery.

The devices can also be added through the `integration menu` UI:

- Go to **Settings → Devices & services → Add integration → Petoneer SmartDot**.
- Choose a nearby device, or enter its Bluetooth address and select the device generation manually.
  On macOS, use the complete CoreBluetooth UUID instead of a MAC address.
- The original SmartDot requires no Petoneer account or keys. For V2, complete the account setup below.

### Connecting SmartDot V2

1. Add the toy to the official **Petoneer** app, then close the app to release its Bluetooth connection.
2. Select the toy in Home Assistant, or enter its Bluetooth address and choose **SmartDot V2**.
3. Enter your Petoneer email and password.
   Leave the cloud region on **Automatic**, or select the account's region explicitly if needed.
4. Select your SmartDot V2 from the account's device list. All account devices are shown without filtering by product ID;
   choose the toy matching the Bluetooth device selected earlier. Other Petoneer products are not supported by this integration.
5. The integration retrieves the selected device's keys and checks BLE authentication without starting a game.

The password and cloud session are not saved. Only the selected device's keys and configuration are stored in HA;
normal control uses local Bluetooth. To refresh keys, open the integration entry's **Reconfigure** menu and log in again.

Please ensure the following steps prior to adding a new SmartDot:

- The SmartDot must NOT be connected with the official app (or any other device), else HA will not be able to discover it, nor connect to it.
- Some HA integrations still use some bluetooth libraries that take full control of the physical bluetooth adapter, in that case, other ble integration will not have access to it. So to test this component, best to disable all other ble integrations if you are unsure what ble lib they are using.

# Additional information

The integration does not expose a reliable current playing/on/off state. V2 acknowledges commands and reports datapoints,
but the last selected game area alone does not indicate whether a game is still running.

After installing the integration, you will be able to choose the size of the area within which the dot will move, and there will be two buttons for starting and stopping the dot's movement.
Choosing a game area does not start a game; press **Start** to launch it.
For V2, **Stop** stops any of the three automatic games.

# Supported firmware versions

The two generations use different Bluetooth protocols:

| Generation | Verified firmware | Protocol |
| --- | --- | --- |
| Original SmartDot | `1.09` | Original FFF3 commands |
| SmartDot V2 | `1.2` | Encrypted Tuya BLE FD50, protocol 4.2 |

When setting up V2, select your SmartDot from the Petoneer account's device list. Other Petoneer products are not supported.
The integration checks the device's keys and Bluetooth authentication before completing setup.

# Debugging

Please ensure the following:

1. The official Petoneer app is closed and no other client is connected to the toy.
2. HA has access to the bluetooth adapter (follow the section above in not on HAOS).
3. No other bluetooth integration are using something else than bleak library for bluetooth. If unsure, disable them.
4. The logging has been changed in HA to allow debugging of this component and bleak:
   In order to get more information on what is going on, the debugging flag can be enabled by placing in the `configuration.yaml` of Home assistant:

   ```yaml
   logger:
     default: warning
     logs:
       custom_components.petoneer_smartdot: debug
       bleak_retry_connector: debug
       bleak: debug
       # homeassistant.components.bluetooth: debug  # this can help if needed
       # homeassistant.components.esphome.bluetooth: debug  # this can help if needed
   ```

   NOTE: this will generate A LOT of debugging messages in the logs, so it is not recommended to use for a long time

5. Restart HA
6. Reload the integration and reproduce the problem. If V2 keys need updating, use **Reconfigure**.
7. Check the logs and report. Do not share device keys, passwords or HA configuration backups.

# Other info

Originally based on the work by Marco Colombo [hass-addon-petoneer-smartdot](https://github.com/marcomow/hass-addon-petoneer-smartdot).
