# Third-party notices

This document records third-party dependencies, acknowledgements, and the origin
of application-specific parameters used by this integration. It does not grant
rights to third-party materials or determine whether a particular use is lawful.

The project's own code is licensed under the MIT License in [LICENSE](LICENSE).
Third-party components retain their respective licenses and notices. The project
license does not grant rights that their respective owners have not granted.

## Runtime dependencies

The following packages are declared in
`custom_components/petoneer_smartdot/manifest.json` and installed separately by
Home Assistant. Their source distributions are not bundled in this repository.

| Component | Declared requirement | Purpose | License |
| --- | --- | --- | --- |
| [tuya-mobile](https://github.com/abovecolin/tuya-mobile) | `==1.2.0` | Tuya mobile API request signing and Petoneer account authentication | MIT |
| [bleak-retry-connector](https://github.com/Bluetooth-Devices/bleak-retry-connector) | `>=4.7.1` | Bluetooth connection establishment | MIT |

The notices below were checked against the license files distributed with
`tuya-mobile` 1.2.0 and `bleak-retry-connector` 4.7.1. Later dependency releases
must be checked against their own license files.

### tuya-mobile

```text
MIT License

Copyright (c) 2026 tuya-mobile contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### bleak-retry-connector

```text
MIT License

Copyright (c) 2022 J. Nick Koston

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Home Assistant and other runtime libraries

The integration also imports Home Assistant, Bleak, aiohttp, cryptography, and
Probatio (or Voluptuous on older environments). These are provided by the runtime
environment or installed through its dependency system. They are not bundled
source code in this repository. Their installed distributions contain their own
licenses and any additional notices for included components.

This document is not an exhaustive license inventory for a complete Home
Assistant installation or its transitive dependencies. Anyone distributing such
an installation must retain the notices required by the versions they distribute.

## Original SmartDot protocol acknowledgement

Support for the original SmartDot was based on the earlier work of Marco Colombo:
[hass-addon-petoneer-smartdot](https://github.com/marcomow/hass-addon-petoneer-smartdot).

This acknowledgement records the project's origin; it does not assert that the
upstream project grants any particular license or relicense upstream materials.

## Petoneer application profile

`custom_components/petoneer_smartdot/petoneer_profile.json` contains parameters
for the Petoneer Android application, package `com.petoneer.pet`, version 3.5.8.
The APK was obtained through the manufacturer's
[Petoneer download page](https://www.petoneer.com/qrcode/?key=petoneer-app), which
linked to the [SkyRC download server](https://soft.skyrc.com/download/?id=22&key=petoneer-app).

The profile was assembled for interoperability with the Petoneer account service:

- Application identifiers and signing parameters were extracted from APK metadata
  and resources, including `AndroidManifest.xml` and `t_s.bmp`.
- The certificate fingerprint was computed from the APK signing certificate.
- Application and SDK versions were read from the APK; client request fields and
  API endpoints were supplied as configuration for the Tuya mobile API client.

These are application-level parameters, not a user's password or individual
device keys. The profile is not an officially published API configuration or an
open-source SDK supplied by Petoneer.

The project's MIT License does not purport to grant rights in third-party
application materials or authorize access to Petoneer/Tuya services. No express
permission from Petoneer to redistribute the extracted parameters is documented
in this repository. Their inclusion here does not establish such permission.

Petoneer publishes a
[Software License and Service Agreement](https://www.petoneer.com/pact/ua/en/),
including restrictions concerning reverse engineering and unauthorized clients.
Whether those terms apply or are enforceable, and whether applicable law permits
particular interoperability activities, requires a separate legal assessment.
This notice does not resolve those questions or cure any lack of permission.

The APK, decompiled application source, and native application libraries are not
bundled in this repository.

## Names and affiliation

Petoneer, SkyRC, Tuya, Home Assistant, and other product or project names identify
their respective products and projects. This community integration does not
claim endorsement or authorization from Petoneer, SkyRC, or Tuya.
