# Security policy

## Supported versions

Until the first stable release, security fixes are provided for the latest published 0.1.x
version only.

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Use GitHub's private
vulnerability reporting for this repository:

<https://github.com/smartathomeat/prizma-link/security/advisories/new>

Include the affected version, platform, reproduction steps and impact. Remove Bluetooth
addresses, MQTT credentials, device captures and customer/site data before attaching evidence.

Security-sensitive reports include, but are not limited to:

- a path that bypasses `safe_mode`, `allow_start` or the model/protocol gates;
- an unexpected device command during startup, reconnect, diagnostics or shutdown;
- credential or identifier exposure through logs, MQTT Discovery or diagnostic exports;
- unauthorised MQTT command acceptance;
- unsafe pairing or control of a device outside the explicit configuration.

We will acknowledge a report as soon as practicable, investigate privately and coordinate a fix
and disclosure. Do not test against equipment or networks you do not own or have permission to
use.
