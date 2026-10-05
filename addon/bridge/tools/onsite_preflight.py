#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from prizma_link.cli import _options_config
from prizma_link.onsite import parse_bluetoothctl_info


def bluetoothctl(*arguments: str) -> str:
    completed = subprocess.run(
        ["bluetoothctl", *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return completed.stdout + completed.stderr


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only preflight for all configured generators; sends no RFCOMM command"
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--expect-devices", type=int, default=2)
    args = parser.parse_args()

    config = _options_config(args.config)
    adapter = bluetoothctl("show")
    adapter_powered = any(line.strip().casefold() == "powered: yes" for line in adapter.splitlines())
    reports = [parse_bluetoothctl_info(device, bluetoothctl("info", device.address)) for device in config.devices]
    result = {
        "mode": "read_only",
        "configured_devices": len(config.devices),
        "expected_devices": args.expect_devices,
        "adapter_powered": adapter_powered,
        "safe_mode": config.safe_mode,
        "allow_start": config.allow_start,
        "devices": [report.masked_dict() for report in reports],
        "all_ready_for_status_probe": (
            len(config.devices) == args.expect_devices
            and adapter_powered
            and config.safe_mode
            and not config.allow_start
            and all(report.read_only_ready for report in reports)
        ),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if len(config.devices) != args.expect_devices:
        raise SystemExit(2)
    if not result["all_ready_for_status_probe"]:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
