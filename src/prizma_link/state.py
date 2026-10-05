from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum


class OperatingState(StrEnum):
    UNKNOWN = "UNKNOWN"
    DISCONNECTED = "DISCONNECTED"
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    DELAYED = "DELAYED"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class DeviceState:
    operating_state: OperatingState = OperatingState.UNKNOWN
    connected: bool = False
    paired: bool = False
    protocol_verified: bool = False
    safe_mode: bool = True
    remaining_seconds: int | None = None
    error_code: int | None = None
    error_text: str = "Unknown"
    active_program: int | None = None
    duration_minutes: int | None = None
    fan_percent: int | None = None
    salt_intervals: tuple[int, ...] = field(default_factory=tuple)
    protocol_name: str = "unknown"
    device_identifier: str | None = None
    last_raw_frame: str | None = None
    last_update: str | None = None
    reconnect_count: int = 0
    command_failures: int = 0
    response_latency_ms: int | None = None

    def unavailable(self) -> DeviceState:
        return replace(
            self,
            operating_state=OperatingState.DISCONNECTED,
            connected=False,
            remaining_seconds=None,
            last_update=datetime.now(UTC).isoformat(),
        )


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
