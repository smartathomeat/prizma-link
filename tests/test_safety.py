from dataclasses import replace

import pytest

from prizma_link.config import AppConfig, DeviceConfig
from prizma_link.device import DeviceController, SafetyError
from prizma_link.protocol.prizsalt import PrizsaltObservedParser, prizsalt_status_fixture
from prizma_link.state import DeviceState, OperatingState


class Writer:
    def __init__(self) -> None:
        self.messages: list[bytes] = []

    async def __call__(self, data: bytes) -> None:
        self.messages.append(data)


def controller(*, safe_mode: bool = True, allow_start: bool = False) -> tuple[DeviceController, Writer]:
    writer = Writer()
    app = AppConfig(
        devices=(DeviceConfig("PRIZSALT+", "AA:BB:CC:DD:EE:FF", model="prizsalt"),),
        safe_mode=safe_mode,
        allow_start=allow_start,
    )
    control = DeviceController(app.devices[0], app, writer)
    control.set_protocol(PrizsaltObservedParser(32))
    control.state = DeviceState(
        operating_state=OperatingState.STOPPED,
        connected=True,
        protocol_verified=True,
        safe_mode=safe_mode,
        error_code=0,
    )
    return control, writer


@pytest.mark.asyncio
async def test_safe_mode_blocks_every_write() -> None:
    control, writer = controller(safe_mode=True, allow_start=True)
    for action in ("start", "pause", "stop"):
        with pytest.raises(SafetyError):
            await control.execute_action(action)
    assert writer.messages == []


@pytest.mark.asyncio
@pytest.mark.parametrize("state", [OperatingState.ERROR, OperatingState.DISCONNECTED, OperatingState.UNKNOWN])
async def test_start_is_blocked_in_unsafe_states(state: OperatingState) -> None:
    control, writer = controller(safe_mode=False, allow_start=True)
    control.state = replace(control.state, operating_state=state, connected=state is not OperatingState.DISCONNECTED)
    with pytest.raises(SafetyError):
        await control.execute_action("start")
    assert writer.messages == []


@pytest.mark.asyncio
async def test_start_is_blocked_when_error_is_active() -> None:
    control, writer = controller(safe_mode=False, allow_start=True)
    control.state = replace(control.state, error_code=2)
    with pytest.raises(SafetyError):
        await control.execute_action("start")
    assert writer.messages == []


@pytest.mark.asyncio
async def test_unverified_protocol_blocks_writes() -> None:
    control, writer = controller(safe_mode=False, allow_start=True)
    control.set_protocol(PrizsaltObservedParser(20))
    with pytest.raises(SafetyError):
        await control.execute_action("start")
    assert writer.messages == []


@pytest.mark.asyncio
async def test_live_verified_prizsalt_start_and_stop_use_confirmed_telegrams() -> None:
    control, writer = controller(safe_mode=False, allow_start=True)
    await control.execute_action("start")
    control.state = replace(control.state, operating_state=OperatingState.RUNNING)
    await control.execute_action("stop")
    assert writer.messages == [b"%st,1;", b"%ms;", b"%st,0;", b"%ms;"]


@pytest.mark.asyncio
async def test_prizsalt_pause_remains_blocked() -> None:
    control, writer = controller(safe_mode=False, allow_start=True)
    control.state = replace(control.state, operating_state=OperatingState.RUNNING)
    with pytest.raises(SafetyError, match="unsupported verified PRIZSALT"):
        await control.execute_action("pause")
    assert writer.messages == []


@pytest.mark.asyncio
async def test_auto_model_never_unlocks_live_prizsalt_shape() -> None:
    writer = Writer()
    app = AppConfig(
        devices=(DeviceConfig("Unknown", "AA:BB:CC:DD:EE:FF", model="auto"),),
        safe_mode=False,
        allow_start=True,
    )
    control = DeviceController(app.devices[0], app, writer)
    control.set_protocol(PrizsaltObservedParser(32))
    control.state = replace(
        control.state,
        operating_state=OperatingState.STOPPED,
        connected=True,
        error_code=0,
    )
    assert not control.state.protocol_verified
    with pytest.raises(SafetyError):
        await control.execute_action("start")
    assert writer.messages == []


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["auto", "multisalt"])
async def test_verified_shape_never_unlocks_unverified_models(model: str) -> None:
    writer = Writer()
    app = AppConfig(
        devices=(DeviceConfig("Test", "AA:BB:CC:DD:EE:FF", model=model),),
        safe_mode=False,
        allow_start=True,
    )
    control = DeviceController(app.devices[0], app, writer)
    control.set_protocol(PrizsaltObservedParser(32))
    control.state = replace(
        control.state,
        operating_state=OperatingState.STOPPED,
        connected=True,
        error_code=0,
    )
    assert not control.state.protocol_verified
    with pytest.raises(SafetyError):
        await control.execute_action("start")
    assert writer.messages == []


@pytest.mark.asyncio
async def test_command_requires_follow_up_status() -> None:
    control, writer = controller(safe_mode=False, allow_start=False)
    await control.execute_action("stop")
    assert writer.messages == [b"%st,0;", b"%ms;"]


@pytest.mark.asyncio
async def test_writer_failure_never_leaves_command_in_flight() -> None:
    async def broken_writer(data: bytes) -> None:
        del data
        raise ConnectionError("link lost")

    app = AppConfig(
        devices=(DeviceConfig("Test", "AA:BB:CC:DD:EE:FF", model="prizsalt"),),
        safe_mode=False,
    )
    control = DeviceController(app.devices[0], app, broken_writer)
    control.set_protocol(PrizsaltObservedParser(32))
    control.state = DeviceState(
        operating_state=OperatingState.STOPPED,
        connected=True,
        protocol_verified=True,
        safe_mode=False,
        error_code=0,
    )
    with pytest.raises(ConnectionError):
        await control.execute_action("stop")
    assert not control.command_in_flight


@pytest.mark.asyncio
async def test_restart_constructs_no_command() -> None:
    control, writer = controller(safe_mode=False, allow_start=True)
    del control
    assert writer.messages == []


def test_status_refresh_preserves_diagnostic_counters() -> None:
    control, _ = controller(safe_mode=True)
    control.state = replace(
        control.state,
        paired=True,
        reconnect_count=3,
        command_failures=4,
        response_latency_ms=17,
    )
    state = control.accept_status(prizsalt_status_fixture(status=0))
    assert state.paired
    assert state.reconnect_count == 3
    assert state.command_failures == 4
    assert state.response_latency_ms == 17
