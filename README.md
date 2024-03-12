# Home Assistant custom component for Petoneer SmartDot

This is a custom component for Home Assistant that allows the control of the Petoneer SmartDot via bluetooth.

![Petoneer SmartDot](assets/petoneer-smartdot.png)

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

Since version 1.0.0, this component uses the [`bleak`](https://github.com/hbldh/bleak) python library to access bluetooth (as bluepy is not supported from HA 2022.07+). In order to scan and interact with bluetooth devices, bluez utility needs to be installed and the correct permissions must be given to HA:

- for **Home Assistant Operating System**:
  It should be all setup, at least for HA 2022.7+

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

You must have the `bluetooth` integration enabled and configured (HA 2022.8+) or a connected ESPhome device running the bluetooth proxy (HA 2022.10+). The Petoneer SmartDot should be automatically discovered and you will receive a notification prompting you to add it.

The devices can also be added through the `integration menu` UI:

- In Configuration/Integrations click on the + button, select `Petoneer SmartDot` and you can either scan for the devices or configure the name and mac address manually on the form.
  The SmartDot is automatically added and a device is created.

Please ensure the following steps prior to adding a new SmartDot:

- The SmartDot must NOT be connected with the official app (or any other device), else HA will not be able to discover it, nor connect to it.
- Some HA integrations still use some bluetooth libraries that take full control of the physical bluetooth adapter, in that case, other ble integration will not have access to it. So to test this component, best to disable all other ble integrations if you are unsure what ble lib they are using.

# Debugging

Please ensure the following:

1. the petoneer_smartdot integration has been removed from HA.
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
6. Reinstall the petoneer_smartdot integration and find the SmartDot through a scan.
7. check the logs and report. Thanks

# Other info

Originally based on the work by Marco Colombo [hass-addon-petoneer-smartdot](https://github.com/marcomow/hass-addon-petoneer-smartdot).
