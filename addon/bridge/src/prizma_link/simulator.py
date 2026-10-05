from __future__ import annotations

import asyncio
from dataclasses import dataclass

from prizma_link.protocol.base import STATUS_QUERY
from prizma_link.protocol.prizsalt import prizsalt_status_fixture
from prizma_link.state import OperatingState


@dataclass(slots=True)
class SimulatedGenerator:
    state: OperatingState = OperatingState.STOPPED
    error_code: int = 0
    connected: bool = True
    response_delay: float = 0.0

    async def exchange(self, command: bytes) -> bytes:
        if not self.connected:
            raise ConnectionError("simulated generator is disconnected")
        if self.response_delay:
            await asyncio.sleep(self.response_delay)
        text = command.decode("ascii")
        if text == "%st,0;":
            self.state = OperatingState.STOPPED
        elif text == "%st,1;":
            self.state = OperatingState.RUNNING
        elif text != STATUS_QUERY:
            raise ValueError("unsupported simulated command")
        codes = {
            OperatingState.STOPPED: 0,
            OperatingState.RUNNING: 1,
            OperatingState.ERROR: 0,
        }
        status = codes.get(self.state, 0)
        error = self.error_code if self.state is OperatingState.ERROR else 0
        remaining = 2700 if self.state is OperatingState.RUNNING else 0
        return prizsalt_status_fixture(status=status, error=error, remaining_seconds=remaining).encode("ascii")

    def disconnect(self) -> None:
        self.connected = False

    def reconnect(self) -> None:
        self.connected = True
