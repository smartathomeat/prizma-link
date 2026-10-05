import json

import pytest

from prizma_link.config import DeviceConfig
from prizma_link.mqtt import ENTITY_SPECS, DiscoveryBuilder, MqttBridge
from prizma_link.state import DeviceState


class Publisher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bool]] = []

    def publish(self, topic: str, payload: str, *, retain: bool) -> object:
        self.calls.append((topic, payload, retain))
        return object()


def test_discovery_contains_every_required_entity_and_unique_ids() -> None:
    device = DeviceConfig("Generator", "AA:BB:CC:DD:EE:FF")
    payloads = DiscoveryBuilder().all_discovery(device)
    assert len(payloads) == len(ENTITY_SPECS)
    decoded = [payload for _, payload in payloads]
    assert len({item["unique_id"] for item in decoded}) == len(decoded)
    assert all(item["availability_topic"].endswith("/availability") for item in decoded)
    assert all("password" not in json.dumps(item).lower() for item in decoded)


def test_commands_are_non_optimistic_and_buttons_are_not_switches() -> None:
    device = DeviceConfig("Generator", "AA:BB:CC:DD:EE:FF")
    payloads = DiscoveryBuilder().all_discovery(device)
    for topic, payload in payloads:
        if "command_topic" in payload:
            assert payload["optimistic"] is False
        if "/button/" in topic:
            assert "/switch/" not in topic
            assert "state_topic" not in payload


def test_diagnostic_entities_are_disabled_by_default() -> None:
    device = DeviceConfig("Generator", "AA:BB:CC:DD:EE:FF")
    payloads = DiscoveryBuilder().all_discovery(device)
    diagnostics = [item for _, item in payloads if item.get("entity_category") == "diagnostic"]
    assert diagnostics
    assert all(item["enabled_by_default"] is False for item in diagnostics)


def test_retained_command_is_rejected() -> None:
    publisher = Publisher()
    bridge = MqttBridge(publisher)
    device = DeviceConfig("Generator", "AA:BB:CC:DD:EE:FF")
    with pytest.raises(ValueError):
        bridge.publish_command(device, "start", "PRESS", retain=True)
    assert publisher.calls == []


def test_non_retained_command_is_published_without_secrets() -> None:
    publisher = Publisher()
    bridge = MqttBridge(publisher)
    device = DeviceConfig("Generator", "AA:BB:CC:DD:EE:FF")
    bridge.publish_command(device, "stop", "PRESS")
    assert publisher.calls == [("prizma/aabbccddeeff/command/stop", "PRESS", False)]


def test_unknown_number_and_select_values_are_not_published() -> None:
    publisher = Publisher()
    bridge = MqttBridge(publisher)
    device = DeviceConfig("Generator", "AA:BB:CC:DD:EE:FF")

    bridge.publish_state(device, DeviceState())

    state_payloads = {topic: payload for topic, payload, _ in publisher.calls}
    base = "prizma/aabbccddeeff/state"
    assert f"{base}/duration_minutes" not in state_payloads
    assert f"{base}/fan_percent" not in state_payloads
    assert f"{base}/program" not in state_payloads
    assert all(f"{base}/salt_interval_{index}" not in state_payloads for index in range(1, 11))
    assert state_payloads[f"{base}/active_program"] == "unknown"


def test_multiple_devices_use_separate_topics() -> None:
    builder = DiscoveryBuilder()
    first = DeviceConfig("A", "AA:BB:CC:DD:EE:01")
    second = DeviceConfig("B", "AA:BB:CC:DD:EE:02")
    first_topics = {topic for topic, _ in builder.all_discovery(first)}
    second_topics = {topic for topic, _ in builder.all_discovery(second)}
    assert first_topics.isdisjoint(second_topics)
