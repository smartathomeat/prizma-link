import asyncio

import pytest

from prizma_link.config import AppConfig, DeviceConfig
from prizma_link.device import DeviceController


async def writer(data: bytes) -> None:
    del data


@pytest.mark.asyncio
async def test_disconnect_drops_entire_queue() -> None:
    app = AppConfig(devices=(DeviceConfig("A", "AA:BB:CC:DD:EE:01"),))
    controller = DeviceController(app.devices[0], app, writer)
    await controller.command_queue.put("%st,1;")
    await controller.command_queue.put("%st,0;")
    controller.disconnect()
    assert controller.command_queue.empty()


@pytest.mark.asyncio
async def test_reconnect_sends_only_status_query() -> None:
    messages: list[bytes] = []

    async def capture(data: bytes) -> None:
        messages.append(data)

    app = AppConfig(devices=(DeviceConfig("A", "AA:BB:CC:DD:EE:01"),))
    controller = DeviceController(app.devices[0], app, capture)
    await controller.command_queue.put("%st,1;")
    controller.disconnect()
    await controller.reconnect()
    assert messages == [b"%ms;"]


def test_multiple_devices_have_separate_queues_and_states() -> None:
    app = AppConfig(
        devices=(
            DeviceConfig("A", "AA:BB:CC:DD:EE:01"),
            DeviceConfig("B", "AA:BB:CC:DD:EE:02"),
        )
    )
    first = DeviceController(app.devices[0], app, writer)
    second = DeviceController(app.devices[1], app, writer)
    first.command_queue.put_nowait("%ms;")
    first.disconnect()
    assert first.command_queue.empty()
    assert second.command_queue.empty()
    assert first.state is not second.state
    assert isinstance(second.command_queue, asyncio.Queue)
