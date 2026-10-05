import asyncio

import pytest

from prizma_link.simulator import SimulatedGenerator
from prizma_link.state import OperatingState


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "needle"),
    [
        (OperatingState.STOPPED, b"%ms,"),
        (OperatingState.RUNNING, b"%ms,"),
        (OperatingState.ERROR, b"%ms,"),
    ],
)
async def test_simulated_statuses(state: OperatingState, needle: bytes) -> None:
    generator = SimulatedGenerator(state=state, error_code=2)
    assert needle in await generator.exchange(b"%ms;")


@pytest.mark.asyncio
async def test_simulated_disconnect_and_reconnect() -> None:
    generator = SimulatedGenerator()
    generator.disconnect()
    with pytest.raises(ConnectionError):
        await generator.exchange(b"%ms;")
    generator.reconnect()
    assert await generator.exchange(b"%ms;")


@pytest.mark.asyncio
async def test_simulated_delayed_response_times_out() -> None:
    generator = SimulatedGenerator(response_delay=0.05)
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(generator.exchange(b"%ms;"), timeout=0.001)
