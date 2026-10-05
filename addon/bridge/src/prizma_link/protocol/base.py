from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from prizma_link.state import DeviceState

STATUS_QUERY = "%ms;"
HISTORY_QUERY = "%rh;"
SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"


class ProtocolError(ValueError):
    """A frame failed strict protocol validation."""


@dataclass(frozen=True, slots=True)
class ProtocolEvidence:
    name: str
    write_verified: bool
    source: str


class ProtocolParser(ABC):
    evidence: ProtocolEvidence

    @abstractmethod
    def matches(self, frame: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse_status(self, frame: str, *, safe_mode: bool) -> DeviceState:
        raise NotImplementedError

    def encode_settings(self, state: DeviceState) -> str:
        raise ProtocolError("write protocol has not been verified")

    def encode_program(self, program: int) -> str:
        raise ProtocolError("program write protocol has not been verified")

    def encode_action(self, action: str) -> str:
        raise ProtocolError("state write protocol has not been verified")


def require_ascii_frame(frame: str, prefix: str = "%ms") -> str:
    if not frame.startswith(prefix) or not frame.endswith(";"):
        raise ProtocolError(f"expected {prefix} ASCII frame")
    try:
        frame.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ProtocolError("frame is not ASCII") from exc
    return frame


def decimal(text: str, field: str, minimum: int, maximum: int) -> int:
    if not text.isdecimal():
        raise ProtocolError(f"{field} is not decimal")
    value = int(text)
    if not minimum <= value <= maximum:
        raise ProtocolError(f"{field} outside range {minimum}..{maximum}")
    return value


def hexadecimal(text: str, field: str, minimum: int, maximum: int) -> int:
    if not text or any(char not in "0123456789abcdefABCDEF" for char in text):
        raise ProtocolError(f"{field} is not hexadecimal")
    value = int(text, 16)
    if not minimum <= value <= maximum:
        raise ProtocolError(f"{field} outside range {minimum}..{maximum}")
    return value
