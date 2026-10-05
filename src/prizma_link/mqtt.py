from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from prizma_link.config import DeviceConfig
from prizma_link.state import DeviceState


class Publisher(Protocol):
    def publish(self, topic: str, payload: str, *, retain: bool) -> object: ...


@dataclass(frozen=True, slots=True)
class EntitySpec:
    component: str
    object_id: str
    name: str
    diagnostic: bool = False
    command: bool = False
    options: tuple[str, ...] = ()
    minimum: int | None = None
    maximum: int | None = None
    step: int | None = None


ENTITY_SPECS: tuple[EntitySpec, ...] = (
    EntitySpec("binary_sensor", "connected", "Verbunden"),
    EntitySpec("binary_sensor", "paired", "Gekoppelt"),
    EntitySpec("binary_sensor", "protocol_verified", "Protokoll verifiziert"),
    EntitySpec("binary_sensor", "safe_mode", "Safe Mode"),
    EntitySpec("sensor", "status", "Betriebsstatus"),
    EntitySpec("sensor", "remaining_time", "Restlaufzeit"),
    EntitySpec("sensor", "remaining_seconds", "Restlaufzeit Sekunden"),
    EntitySpec("sensor", "error_code", "Fehlercode"),
    EntitySpec("sensor", "error_text", "Fehlertext"),
    EntitySpec("sensor", "active_program", "Aktives Programm"),
    EntitySpec("sensor", "last_update", "Letzte Aktualisierung"),
    EntitySpec("sensor", "protocol_name", "Protokoll"),
    EntitySpec("sensor", "device_identifier", "Gerätekennung"),
    EntitySpec("number", "duration_minutes", "Sitzungsdauer", command=True, minimum=10, maximum=99, step=1),
    EntitySpec("number", "fan_percent", "Lüfterleistung", command=True, minimum=0, maximum=100, step=1),
    *(
        EntitySpec("number", f"salt_interval_{i}", f"Salzintervall {i}", command=True, minimum=0, maximum=15, step=1)
        for i in range(1, 11)
    ),
    EntitySpec("select", "program", "Programmauswahl", command=True, options=tuple(map(str, range(1, 10)))),
    EntitySpec("button", "start", "Start", command=True),
    EntitySpec("button", "pause", "Pause/Fortsetzen", command=True),
    EntitySpec("button", "stop", "Stop", command=True),
    EntitySpec("button", "refresh_status", "Status aktualisieren", command=True),
    EntitySpec("button", "reconnect", "Neu verbinden", command=True),
    EntitySpec("sensor", "last_raw_frame", "Letztes Rohtelegramm", diagnostic=True),
    EntitySpec("sensor", "reconnect_count", "Neuverbinden-Zähler", diagnostic=True),
    EntitySpec("sensor", "command_failures", "Befehlsfehler", diagnostic=True),
    EntitySpec("sensor", "response_latency_ms", "Antwortlatenz", diagnostic=True),
)

ENTITY_COMPONENTS = {spec.object_id: spec.component for spec in ENTITY_SPECS}


class DiscoveryBuilder:
    def __init__(self, prefix: str = "homeassistant") -> None:
        self.prefix = prefix

    def base_topic(self, device: DeviceConfig) -> str:
        return f"prizma/{device.normalized_address}"

    def discovery(self, device: DeviceConfig, spec: EntitySpec) -> tuple[str, dict[str, Any]]:
        normalized = device.normalized_address
        base = self.base_topic(device)
        unique_id = f"prizma_{normalized}_{spec.object_id}"
        topic = f"{self.prefix}/{spec.component}/prizma_{normalized}/{spec.object_id}/config"
        payload: dict[str, Any] = {
            "name": spec.name,
            "unique_id": unique_id,
            "object_id": unique_id,
            "availability_topic": f"{base}/availability",
            "payload_available": "online",
            "payload_not_available": "offline",
            "state_topic": f"{base}/state/{spec.object_id}",
            "device": {
                "identifiers": [f"prizma_{normalized}"],
                "name": device.name,
                "manufacturer": "Prizma",
                "model": device.model,
            },
        }
        if spec.diagnostic:
            payload["entity_category"] = "diagnostic"
            payload["enabled_by_default"] = False
        if spec.command:
            payload["command_topic"] = f"{base}/command/{spec.object_id}"
            payload["optimistic"] = False
        if spec.options:
            payload["options"] = list(spec.options)
        if spec.minimum is not None:
            payload.update({"min": spec.minimum, "max": spec.maximum, "step": spec.step})
        if spec.component == "button":
            payload.pop("state_topic", None)
        return topic, payload

    def all_discovery(self, device: DeviceConfig) -> list[tuple[str, dict[str, Any]]]:
        return [self.discovery(device, spec) for spec in ENTITY_SPECS]


class MqttBridge:
    def __init__(self, publisher: Publisher, prefix: str = "homeassistant") -> None:
        self.publisher = publisher
        self.builder = DiscoveryBuilder(prefix)

    def publish_discovery(self, device: DeviceConfig) -> None:
        for topic, payload in self.builder.all_discovery(device):
            self.publisher.publish(topic, json.dumps(payload, separators=(",", ":")), retain=True)

    def publish_availability(self, device: DeviceConfig, available: bool) -> None:
        self.publisher.publish(
            f"{self.builder.base_topic(device)}/availability",
            "online" if available else "offline",
            retain=True,
        )

    def publish_state(self, device: DeviceConfig, state: DeviceState) -> None:
        values = state_values(state)
        for key, value in values.items():
            # MQTT number/select reject the textual payload "unknown" and log on every
            # status poll. Leave those entities without a state until a numeric/allowed
            # value has actually been decoded. Sensor entities may legitimately use the
            # Home Assistant state "unknown".
            if value is None and ENTITY_COMPONENTS.get(key) in {"number", "select"}:
                continue
            self.publisher.publish(
                f"{self.builder.base_topic(device)}/state/{key}",
                "unknown" if value is None else str(value),
                retain=True,
            )

    def publish_command(self, device: DeviceConfig, object_id: str, value: str, *, retain: bool = False) -> None:
        if retain:
            raise ValueError("MQTT command messages must never be retained")
        self.publisher.publish(f"{self.builder.base_topic(device)}/command/{object_id}", value, retain=False)


def state_values(state: DeviceState) -> dict[str, object]:
    remaining = None
    if state.remaining_seconds is not None:
        minutes, seconds = divmod(state.remaining_seconds, 60)
        remaining = f"{minutes:02d}:{seconds:02d}"
    values: dict[str, object] = {
        "connected": "ON" if state.connected else "OFF",
        "paired": "ON" if state.paired else "OFF",
        "protocol_verified": "ON" if state.protocol_verified else "OFF",
        "safe_mode": "ON" if state.safe_mode else "OFF",
        "status": state.operating_state.value,
        "remaining_time": remaining,
        "remaining_seconds": state.remaining_seconds,
        "error_code": state.error_code,
        "error_text": state.error_text,
        "active_program": state.active_program,
        "last_update": state.last_update,
        "protocol_name": state.protocol_name,
        "device_identifier": state.device_identifier,
        "duration_minutes": state.duration_minutes,
        "fan_percent": state.fan_percent,
        "last_raw_frame": state.last_raw_frame,
        "reconnect_count": state.reconnect_count,
        "command_failures": state.command_failures,
        "response_latency_ms": state.response_latency_ms,
        "program": state.active_program,
    }
    for index in range(10):
        values[f"salt_interval_{index + 1}"] = (
            state.salt_intervals[index] if index < len(state.salt_intervals) else None
        )
    return values
