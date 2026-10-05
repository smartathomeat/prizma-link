import asyncio
from dataclasses import replace

import pytest

from prizma_link.bridge import LiveSession
from prizma_link.config import AppConfig, DeviceConfig
from prizma_link.mqtt import DiscoveryBuilder, MqttBridge
from prizma_link.protocol.prizsalt import PrizsaltObservedParser, prizsalt_status_fixture
from prizma_link.state import OperatingState


class Publisher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bool]] = []

    def publish(self, topic: str, payload: str, *, retain: bool) -> object:
        self.calls.append((topic, payload, retain))
        return object()


class Profile:
    pass


class WaitingConnection:
    def __init__(self) -> None:
        self.read_cancelled = False
        self.writes: list[bytes] = []

    async def read(self, size: int = 1024) -> bytes:
        del size
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.read_cancelled = True
            raise
        return b""

    async def write(self, data: bytes) -> None:
        self.writes.append(data)

    async def close(self) -> None:
        return None


def fleet() -> tuple[AppConfig, DeviceConfig, DeviceConfig]:
    first = DeviceConfig("PRISM 1", "AA:BB:CC:DD:EE:01", model="prizsalt")
    second = DeviceConfig("PRISM 2", "AA:BB:CC:DD:EE:02", model="prizsalt")
    return AppConfig(devices=(first, second)), first, second


def test_all_discovery_topics_and_ids_are_unique_for_two_devices() -> None:
    _, first, second = fleet()
    builder = DiscoveryBuilder()
    discoveries = builder.all_discovery(first) + builder.all_discovery(second)
    topics = [topic for topic, _ in discoveries]
    ids = [payload["unique_id"] for _, payload in discoveries]
    assert len(topics) == len(set(topics))
    assert len(ids) == len(set(ids))


def test_state_and_disconnect_are_isolated_per_device() -> None:
    app, first, second = fleet()
    publisher = Publisher()
    mqtt = MqttBridge(publisher)
    one = LiveSession(app, first, Profile(), mqtt)  # type: ignore[arg-type]
    two = LiveSession(app, second, Profile(), mqtt)  # type: ignore[arg-type]
    one.controller.set_protocol(PrizsaltObservedParser(32))
    two.controller.set_protocol(PrizsaltObservedParser(32))
    one.controller.accept_status(prizsalt_status_fixture(status=1, remaining_seconds=2700))
    two.controller.accept_status(prizsalt_status_fixture(status=0))
    one.controller.disconnect()
    assert one.controller.state.operating_state is OperatingState.DISCONNECTED
    assert two.controller.state.operating_state is OperatingState.STOPPED
    assert two.controller.state.connected


@pytest.mark.asyncio
async def test_blocked_start_on_one_device_does_not_change_other_device() -> None:
    app, first, second = fleet()
    publisher = Publisher()
    mqtt = MqttBridge(publisher)
    one = LiveSession(app, first, Profile(), mqtt)  # type: ignore[arg-type]
    two = LiveSession(app, second, Profile(), mqtt)  # type: ignore[arg-type]
    one.controller.state = replace(one.controller.state, command_failures=4)
    two.controller.state = replace(two.controller.state, command_failures=7)
    await one.handle_command("start", "PRESS", retain=False)
    assert one.controller.state.command_failures == 5
    assert two.controller.state.command_failures == 7
    assert not one.reconnect_requested.is_set()
    assert not two.reconnect_requested.is_set()


@pytest.mark.asyncio
async def test_reconnect_request_targets_only_selected_device() -> None:
    app, first, second = fleet()
    mqtt = MqttBridge(Publisher())
    one = LiveSession(app, first, Profile(), mqtt)  # type: ignore[arg-type]
    two = LiveSession(app, second, Profile(), mqtt)  # type: ignore[arg-type]
    await two.handle_command("reconnect", "PRESS", retain=False)
    assert not one.reconnect_requested.is_set()
    assert two.reconnect_requested.is_set()


@pytest.mark.asyncio
async def test_connected_loop_cancels_reader_on_shutdown() -> None:
    app, first, _ = fleet()
    session = LiveSession(app, first, Profile(), MqttBridge(Publisher()))  # type: ignore[arg-type]
    connection = WaitingConnection()
    session.connection = connection
    task = asyncio.create_task(session._connected_loop())
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert connection.read_cancelled
