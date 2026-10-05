# Prizma Link

**Prizma Link** is a local-first Bluetooth Classic RFCOMM/SPP bridge for selected Prizma
dry-salt generators. It publishes device state and deliberately limited controls to Home
Assistant through MQTT Discovery. The project is maintained by **smartathome®**.

> [!IMPORTANT]
> This is an independent community project, not an official Prizma product. It is not medical
> advice and does not replace the manufacturer's instructions, safety limits, maintenance or
> supervision requirements.

## Current support

| Model / path | Status | Write support |
| --- | --- | --- |
| PRIZSALT+ with the independently observed 32-character status frame | Tested | START and STOP only |
| multiSALT and unknown frame shapes | Experimental read-only | None |
| Home Assistant OS / Supervised app | Experimental | Uses host BlueZ and the Mosquitto service |
| Raspberry Pi OS 64-bit | Supported deployment | systemd service and optional weekly bridge restart |
| macOS | Read-only gateway | Native IOBluetooth helper; status requests only |

Bluetooth Low Energy, ESPHome Bluetooth proxies and cloud services are intentionally not used.
The generator exposes the Bluetooth Classic Serial Port Profile (SPP) UUID
`00001101-0000-1000-8000-00805F9B34FB`.

## Safety model

The defaults are fail-closed:

- `safe_mode: true` blocks every device write.
- `allow_start: false` adds a separate START gate.
- `model: auto` may detect a stable status-frame shape but can never unlock writes.
- Only an explicit `model: prizsalt` plus the independently verified 32-character frame can
  unlock the two confirmed actions, `%st,1;` (START) and `%st,0;` (STOP).
- Pause, program selection, duration, fan level and salt interval writes remain blocked.
- Every command is followed by a fresh `%ms;` status request. No state is assumed optimistically.
- Reconnect sends a status request only and discards stale queued commands.

Do not disable Safe Mode until the exact device, frame shape and physical START/STOP response have
been verified on site. A real first START should always happen under direct supervision.

## Install in Home Assistant

Requirements:

- Home Assistant OS or Supervised on `aarch64` or `amd64`
- a Bluetooth adapter with Bluetooth Classic RFCOMM/SPP support
- the official Mosquitto Broker app and the MQTT integration
- the manufacturer's mobile app fully closed while Prizma Link is connected

1. Create a full Home Assistant backup.
2. Open **Settings → Apps → App store → ⋮ → Repositories**.
3. Add `https://github.com/smartathomeat/prizma-link`.
4. Install **Prizma Link**. The first build is local and may take several minutes.
5. Add one configuration entry per generator, keeping `model: auto`, `safe_mode: true` and
   `allow_start: false` for the initial read-only check.
6. Start the app and confirm pairing, connection and stable status updates.
7. Only after the on-site checks in [the app documentation](addon/DOCS.md), change the verified
   PRIZSALT+ device to `model: prizsalt`. Enable writes only when physically supervised.

Example:

```yaml
devices:
  - name: Dry salt generator 1
    address: "AA:BB:CC:DD:EE:FF"
    model: auto
    pin: "1234"
safe_mode: true
allow_start: false
poll_interval: 1.0
command_timeout: 3.0
reconnect_max_seconds: 60
log_level: info
mqtt_discovery_prefix: homeassistant
```

The Bluetooth address and PIN are stored only in the local Home Assistant app configuration.
Never post device captures, credentials or unmasked addresses in a public issue.

## Raspberry Pi deployment

For a dedicated Bluetooth gateway, see
[`deploy/rpi3bplus/README.md`](deploy/rpi3bplus/README.md). The installer intentionally leaves
the bridge service and weekly maintenance timer disabled until local validation is complete.

## macOS gateway

Compile the native helper:

```bash
swiftc -framework IOBluetooth tools/macos_prism_rfcomm_helper.swift \
  -o tools/macos_prism_rfcomm_helper
```

Then use `transport: macos_native`, the exact Bluetooth address, PIN and `PSN_IF-*` device name,
plus local MQTT credentials. The helper refuses name/address mismatches and ambiguous paired-device
matches. The published macOS helper intentionally accepts status requests only; START and STOP
remain blocked on this transport. `config.macos.local.yaml`, compiled helpers and logs are excluded
from Git.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install '.[dev]'
python -m compileall src
ruff check .
mypy src
pytest -q
```

Useful read-only diagnostics:

```bash
python tools/diagnose_bluez.py --scan-seconds 30
python tools/read_only_probe.py --address AA:BB:CC:DD:EE:FF --count 10 \
  --label generator-1-stopped --output generator-1-capture.jsonl
```

The read-only probe sends only `%ms;`. Captures are ignored by Git and must be reviewed for
identifiers before they are shared.

## Protocol provenance

The published PRIZSALT+ parser and command gates are based on independently recorded, controlled
on-site observations. The public repository intentionally excludes protocol implementations whose
reuse rights are unclear. New write commands require repeatable evidence, fail-closed tests and a
supervised device validation before they can be accepted.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) before proposing protocol changes. Please report security
issues privately as described in [SECURITY.md](SECURITY.md), not in a public issue.

## License and trademarks

The source code is available under the [MIT License](LICENSE). The license does not grant rights
to the smartathome® name or logo; see [TRADEMARKS.md](TRADEMARKS.md). Product names belong to their
respective owners and are used only to describe compatibility.
