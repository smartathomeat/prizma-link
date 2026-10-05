from __future__ import annotations

from prizma_link.protocol.base import (
    ProtocolError,
    ProtocolEvidence,
    ProtocolParser,
    decimal,
    hexadecimal,
    require_ascii_frame,
)
from prizma_link.state import DeviceState, OperatingState, utc_now_iso

_LIVE_FRAME_LENGTH = 32
_OBSERVED_STATES = {
    0: OperatingState.STOPPED,
    1: OperatingState.RUNNING,
}


def prizsalt_status_fixture(
    *,
    status: int = 0,
    error: int = 0,
    duration_minutes: int = 45,
    remaining_seconds: int = 0,
    device_identifier: str = "0",
) -> str:
    """Build a synthetic frame with the independently observed PRIZSALT+ shape."""
    if status not in _OBSERVED_STATES:
        raise ValueError("status must be 0 (stopped) or 1 (running)")
    if not 0 <= error <= 15:
        raise ValueError("error must be between 0 and 15")
    if not 0 <= duration_minutes <= 99:
        raise ValueError("duration_minutes must be between 0 and 99")
    if not 0 <= remaining_seconds <= 5940:
        raise ValueError("remaining_seconds must be between 0 and 5940")
    if len(device_identifier) != 1 or device_identifier not in "0123456789ABCDEFabcdef":
        raise ValueError("device_identifier must be one hexadecimal character")
    opaque_tail = "aaaaaaaaaaa------"
    return (
        f"%ms,{device_identifier}1{status:X}{error:X}"
        f"{duration_minutes:02d}{remaining_seconds:04d}{opaque_tail};"
    )


class PrizsaltObservedParser(ProtocolParser):
    """Parser for observed PRIZSALT+ frames with narrowly scoped live proof."""

    def __init__(self, expected_length: int) -> None:
        if expected_length < 8:
            raise ValueError("expected_length is implausibly short")
        self.expected_length = expected_length
        live_shape = expected_length == _LIVE_FRAME_LENGTH
        self.evidence = ProtocolEvidence(
            name="prizsalt_live_verified" if live_shape else "prizsalt_observed_read_only",
            write_verified=live_shape,
            source=(
                "Controlled on-site verification: %ms status plus confirmed %st,1; START "
                "and %st,0; STOP with follow-up status"
                if live_shape
                else "Stable unknown %ms shape; read-only until model-specific live proof exists"
            ),
        )

    def matches(self, frame: str) -> bool:
        return len(frame) == self.expected_length and frame.startswith("%ms") and frame.endswith(";")

    def parse_status(self, frame: str, *, safe_mode: bool) -> DeviceState:
        require_ascii_frame(frame)
        if not self.matches(frame):
            raise ProtocolError("frame differs from the stable observed PRIZSALT+ shape")

        operating_state = OperatingState.UNKNOWN
        remaining_seconds = None
        error_code = None
        error_text = "Feldlayout noch nicht verifiziert"
        duration_minutes = None
        device_identifier = None

        # On-site captures on 2026-08-06 proved this ten-character header by
        # observing STOPPED -> RUNNING with a one-second countdown -> STOPPED.
        # The rest of the 27-character PRIZSALT+ payload remains opaque.
        if len(frame) == _LIVE_FRAME_LENGTH:
            payload = frame[4:-1]
            device_identifier = payload[0]
            raw_status = hexadecimal(payload[2], "status", 0, 15)
            error_code = hexadecimal(payload[3], "error", 0, 15)
            duration_minutes = decimal(payload[4:6], "duration", 0, 99)
            remaining_seconds = decimal(payload[6:10], "remaining", 0, 5940)
            operating_state = _OBSERVED_STATES.get(raw_status, OperatingState.UNKNOWN)
            if error_code:
                operating_state = OperatingState.ERROR
                error_text = f"Gerätefehler {error_code}"
            else:
                error_text = "Kein Fehler"

        return DeviceState(
            operating_state=operating_state,
            connected=True,
            protocol_verified=self.evidence.write_verified,
            safe_mode=safe_mode,
            remaining_seconds=remaining_seconds,
            error_code=error_code,
            error_text=error_text,
            duration_minutes=duration_minutes,
            protocol_name=self.evidence.name,
            device_identifier=device_identifier,
            last_raw_frame=frame,
            last_update=utc_now_iso(),
        )

    def encode_action(self, action: str) -> str:
        if not self.evidence.write_verified:
            raise ProtocolError("PRIZSALT+ frame shape is not write-verified")
        values = {"stop": 0, "start": 1}
        if action not in values:
            raise ProtocolError(f"unsupported verified PRIZSALT+ action: {action}")
        return f"%st,{values[action]};"
