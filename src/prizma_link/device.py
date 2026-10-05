from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace

from prizma_link.config import AppConfig, DeviceConfig
from prizma_link.protocol.base import STATUS_QUERY, ProtocolError, ProtocolParser
from prizma_link.state import DeviceState, OperatingState


class SafetyError(RuntimeError):
    """A command was blocked by a safety gate."""


Writer = Callable[[bytes], Awaitable[None]]


@dataclass(slots=True)
class DeviceController:
    device: DeviceConfig
    app: AppConfig
    writer: Writer
    state: DeviceState = field(default_factory=DeviceState)
    protocol: ProtocolParser | None = None
    command_queue: asyncio.Queue[str] = field(default_factory=asyncio.Queue)
    command_in_flight: bool = False
    generation: int = 0

    async def query_status(self) -> None:
        await self.writer(STATUS_QUERY.encode("ascii"))

    def set_protocol(self, protocol: ProtocolParser) -> None:
        self.protocol = protocol
        self.state = replace(
            self.state,
            protocol_name=protocol.evidence.name,
            protocol_verified=self._write_protocol_allowed(protocol),
        )

    def _write_protocol_allowed(self, protocol: ProtocolParser | None = None) -> bool:
        selected = self.protocol if protocol is None else protocol
        if selected is None or not selected.evidence.write_verified:
            return False
        # Auto-detection proves only a frame shape. It must never grant write
        # access to a device merely because its frame length looks familiar.
        return self.device.model == "prizsalt" and selected.evidence.name == "prizsalt_live_verified"

    def accept_status(self, frame: str) -> DeviceState:
        if self.protocol is None:
            raise ProtocolError("protocol is not selected")
        previous = self.state
        parsed = self.protocol.parse_status(frame, safe_mode=self.app.safe_mode)
        self.state = replace(
            parsed,
            protocol_verified=self._write_protocol_allowed(),
            paired=previous.paired,
            reconnect_count=previous.reconnect_count,
            command_failures=previous.command_failures,
            response_latency_ms=previous.response_latency_ms,
        )
        return self.state

    def validate_action(self, action: str) -> None:
        if self.app.safe_mode:
            raise SafetyError("safe_mode blocks all writes")
        if not self._write_protocol_allowed() or not self.state.protocol_verified:
            raise SafetyError("protocol is not write-verified")
        assert self.protocol is not None
        try:
            self.protocol.encode_action(action)
        except ProtocolError as exc:
            raise SafetyError(str(exc)) from exc
        if not self.state.connected or self.state.operating_state in {
            OperatingState.DISCONNECTED,
            OperatingState.UNKNOWN,
        }:
            raise SafetyError("device is not in a commandable state")
        if self.command_in_flight:
            raise SafetyError("another command is in flight")
        if action == "start":
            if not self.app.allow_start:
                raise SafetyError("allow_start is false")
            if self.state.error_code not in (None, 0):
                raise SafetyError("START blocked while an error is active")
            if self.state.operating_state not in {OperatingState.STOPPED, OperatingState.PAUSED}:
                raise SafetyError("START is not allowed from this state")
        elif action == "pause" and self.state.operating_state is not OperatingState.RUNNING:
            raise SafetyError("PAUSE is only allowed while running")
        elif action == "stop" and self.state.operating_state not in {
            OperatingState.STOPPED,
            OperatingState.RUNNING,
            OperatingState.PAUSED,
            OperatingState.DELAYED,
            OperatingState.ERROR,
        }:
            raise SafetyError("STOP is not allowed from this state")
        elif action not in {"start", "pause", "stop"}:
            raise SafetyError(f"unknown action: {action}")

    async def execute_action(self, action: str) -> None:
        self.validate_action(action)
        assert self.protocol is not None
        command = self.protocol.encode_action(action)
        self.command_in_flight = True
        try:
            await self.writer(command.encode("ascii"))
            await self.query_status()
        finally:
            self.command_in_flight = False

    def disconnect(self) -> None:
        self.generation += 1
        while not self.command_queue.empty():
            try:
                self.command_queue.get_nowait()
                self.command_queue.task_done()
            except asyncio.QueueEmpty:
                break
        self.command_in_flight = False
        self.state = self.state.unavailable()

    async def reconnect(self) -> None:
        self.state = replace(
            self.state,
            connected=True,
            reconnect_count=self.state.reconnect_count + 1,
        )
        await self.query_status()
