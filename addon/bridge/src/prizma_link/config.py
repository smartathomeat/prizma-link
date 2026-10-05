from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when configuration is unsafe or invalid."""


@dataclass(frozen=True, slots=True)
class DeviceConfig:
    name: str
    address: str
    model: str = "auto"
    pin: str = "1234"
    bluetooth_name: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ConfigError("device name must not be empty")
        parts = self.address.upper().split(":")
        if len(parts) != 6 or any(
            len(part) != 2 or any(char not in "0123456789ABCDEF" for char in part) for part in parts
        ):
            raise ConfigError("device address must be a Bluetooth MAC address")
        if self.model not in {"auto", "prizsalt", "multisalt"}:
            raise ConfigError(f"unsupported model: {self.model}")
        if not self.pin.isdigit() or not 1 <= len(self.pin) <= 16:
            raise ConfigError("pin must contain 1 to 16 digits")
        if self.bluetooth_name is not None and not self.bluetooth_name.startswith("PSN_IF-"):
            raise ConfigError("bluetooth_name must start with PSN_IF-")

    @property
    def normalized_address(self) -> str:
        return self.address.lower().replace(":", "")

    @property
    def masked_address(self) -> str:
        parts = self.address.upper().split(":")
        return f"XX:XX:XX:XX:{parts[-2]}:{parts[-1]}"


@dataclass(frozen=True, slots=True)
class MqttConfig:
    host: str = "core-mosquitto"
    port: int = 1883
    username: str | None = None
    password: str | None = None
    discovery_prefix: str = "homeassistant"
    client_id: str = "prizma-link"


@dataclass(frozen=True, slots=True)
class AppConfig:
    devices: tuple[DeviceConfig, ...]
    transport: str = "auto"
    macos_helper_path: str = "tools/macos_prism_rfcomm_helper"
    safe_mode: bool = True
    allow_start: bool = False
    poll_interval: float = 1.0
    command_timeout: float = 3.0
    reconnect_max_seconds: int = 60
    log_level: str = "info"
    mqtt: MqttConfig = field(default_factory=MqttConfig)

    def __post_init__(self) -> None:
        if not self.devices:
            raise ConfigError("at least one device is required")
        if self.transport not in {"auto", "bluez", "macos_native"}:
            raise ConfigError("transport must be auto, bluez, or macos_native")
        if self.transport == "macos_native" and any(item.bluetooth_name is None for item in self.devices):
            raise ConfigError("macos_native transport requires bluetooth_name for every device")
        if len({item.address.upper() for item in self.devices}) != len(self.devices):
            raise ConfigError("device addresses must be unique")
        if len({item.name.strip().casefold() for item in self.devices}) != len(self.devices):
            raise ConfigError("device names must be unique")
        if not 0.5 <= self.poll_interval <= 60:
            raise ConfigError("poll_interval must be between 0.5 and 60 seconds")
        if not 1 <= self.command_timeout <= 30:
            raise ConfigError("command_timeout must be between 1 and 30 seconds")
        if not 1 <= self.reconnect_max_seconds <= 300:
            raise ConfigError("reconnect_max_seconds must be between 1 and 300")


def _mapping(value: object, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{where} must be a mapping")
    return {str(key): item for key, item in value.items()}


def _strict_bool(value: object, where: str, default: bool) -> bool:
    """Accept YAML booleans only; quoted strings must never open a safety gate."""
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ConfigError(f"{where} must be an unquoted YAML boolean")
    return value


def load_config(path: str | Path) -> AppConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    root = _mapping(raw, "configuration")
    devices_raw = root.get("devices")
    if not isinstance(devices_raw, list):
        raise ConfigError("devices must be a list")
    devices = tuple(
        DeviceConfig(
            name=str(item_map["name"]),
            address=str(item_map["address"]),
            model=str(item_map.get("model", "auto")),
            pin=str(item_map.get("pin", "1234")),
            bluetooth_name=_optional_string(item_map.get("bluetooth_name")),
        )
        for item_map in (_mapping(item, "device") for item in devices_raw)
    )
    mqtt_raw = _mapping(root.get("mqtt", {}), "mqtt")
    mqtt = MqttConfig(
        host=str(mqtt_raw.get("host", "core-mosquitto")),
        port=int(mqtt_raw.get("port", 1883)),
        username=_optional_string(mqtt_raw.get("username")),
        password=_optional_string(mqtt_raw.get("password")),
        discovery_prefix=str(root.get("mqtt_discovery_prefix", mqtt_raw.get("discovery_prefix", "homeassistant"))),
        client_id=str(mqtt_raw.get("client_id", "prizma-link")),
    )
    return AppConfig(
        devices=devices,
        transport=str(root.get("transport", "auto")),
        macos_helper_path=str(root.get("macos_helper_path", "tools/macos_prism_rfcomm_helper")),
        safe_mode=_strict_bool(root.get("safe_mode"), "safe_mode", True),
        allow_start=_strict_bool(root.get("allow_start"), "allow_start", False),
        poll_interval=float(root.get("poll_interval", 1.0)),
        command_timeout=float(root.get("command_timeout", 3.0)),
        reconnect_max_seconds=int(root.get("reconnect_max_seconds", 60)),
        log_level=str(root.get("log_level", "info")),
        mqtt=mqtt,
    )


def _optional_string(value: object) -> str | None:
    return None if value in (None, "") else str(value)
