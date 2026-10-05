from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from prizma_link import __version__
from prizma_link.bridge import run_bridge
from prizma_link.config import AppConfig, DeviceConfig, MqttConfig, _strict_bool, load_config
from prizma_link.pairing import pair_device
from prizma_link.protocol.prizsalt import prizsalt_status_fixture


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prizma-link")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the Bluetooth-to-MQTT bridge")
    run.add_argument("--config", required=True)
    pair = sub.add_parser("pair", help="pair exactly one configured device")
    pair.add_argument("--config", required=True)
    pair.add_argument("--address", required=True)
    pair_all = sub.add_parser("pair-all", help="pair all and only configured devices")
    pair_all.add_argument("--config", required=True)
    pair_all.add_argument(
        "--best-effort",
        action="store_true",
        help="continue when one configured device is absent so other devices can still run",
    )
    simulate = sub.add_parser("simulate", help="print safe status fixtures")
    simulate.add_argument("--state", choices=["stopped", "running", "error"], default="stopped")
    return parser


def _options_config(path: str | Path) -> AppConfig:
    source = Path(path)
    if source.suffix != ".json":
        config = load_config(source)
        return replace(
            config,
            mqtt=replace(
                config.mqtt,
                host=os.environ.get("PRIZMA_MQTT_HOST", config.mqtt.host),
                port=int(os.environ.get("PRIZMA_MQTT_PORT", str(config.mqtt.port))),
                username=os.environ.get("PRIZMA_MQTT_USERNAME", config.mqtt.username),
                password=os.environ.get("PRIZMA_MQTT_PASSWORD", config.mqtt.password),
                client_id=os.environ.get("PRIZMA_MQTT_CLIENT_ID", config.mqtt.client_id),
            ),
        )
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("options JSON must be an object")
    devices_value = raw.get("devices")
    if not isinstance(devices_value, list):
        raise ValueError("options devices must be a list")
    devices = tuple(_device_from_json(item) for item in devices_value)
    return AppConfig(
        devices=devices,
        transport=str(raw.get("transport", "auto")),
        macos_helper_path=str(raw.get("macos_helper_path", "tools/macos_prism_rfcomm_helper")),
        safe_mode=_strict_bool(raw.get("safe_mode"), "safe_mode", True),
        allow_start=_strict_bool(raw.get("allow_start"), "allow_start", False),
        poll_interval=float(raw.get("poll_interval", 1.0)),
        command_timeout=float(raw.get("command_timeout", 3.0)),
        reconnect_max_seconds=int(raw.get("reconnect_max_seconds", 60)),
        log_level=str(raw.get("log_level", "info")),
        mqtt=MqttConfig(
            host=os.environ.get("PRIZMA_MQTT_HOST", "core-mosquitto"),
            port=int(os.environ.get("PRIZMA_MQTT_PORT", "1883")),
            username=os.environ.get("PRIZMA_MQTT_USERNAME") or None,
            password=os.environ.get("PRIZMA_MQTT_PASSWORD") or None,
            discovery_prefix=str(raw.get("mqtt_discovery_prefix", "homeassistant")),
            client_id=os.environ.get("PRIZMA_MQTT_CLIENT_ID", "prizma-link"),
        ),
    )


def _device_from_json(value: object) -> DeviceConfig:
    if not isinstance(value, dict):
        raise ValueError("each device must be an object")
    item: dict[str, Any] = {str(key): val for key, val in value.items()}
    return DeviceConfig(
        name=str(item["name"]),
        address=str(item["address"]),
        model=str(item.get("model", "auto")),
        pin=str(item.get("pin", "1234")),
        bluetooth_name=None if item.get("bluetooth_name") in (None, "") else str(item["bluetooth_name"]),
    )


Pairer = Callable[[str, str], Awaitable[None]]


async def _pair_all(config: AppConfig, pairer: Pairer = pair_device) -> int:
    failures = 0
    for device in config.devices:
        logging.info("Ensuring configured device ending in %s is paired and trusted", device.address[-5:])
        try:
            await pairer(device.address, device.pin)
        except Exception as exc:
            failures += 1
            logging.warning("Pairing unavailable for device ending in %s: %s", device.address[-5:], exc)
    return failures


def main() -> None:
    args = _parser().parse_args()
    if args.command == "simulate":
        states = {"stopped": (0, 0), "running": (1, 0), "error": (0, 2)}
        status, error = states[args.state]
        remaining = 2700 if args.state == "running" else 0
        print(prizsalt_status_fixture(status=status, error=error, remaining_seconds=remaining))
        return
    config = _options_config(args.config)
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if args.command == "pair":
        device = next((item for item in config.devices if item.address.upper() == args.address.upper()), None)
        if device is None:
            raise SystemExit("address is not present in the configuration")
        asyncio.run(pair_device(device.address, device.pin))
        return
    if args.command == "pair-all":
        failures = asyncio.run(_pair_all(config))
        if failures and not args.best_effort:
            raise SystemExit(f"pairing failed for {failures} configured device(s)")
        return
    asyncio.run(run_bridge(config))


if __name__ == "__main__":
    main()
