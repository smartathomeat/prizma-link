from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from prizma_link.protocol.base import ProtocolParser, require_ascii_frame
from prizma_link.protocol.prizsalt import PrizsaltObservedParser


@dataclass(slots=True)
class AutoDetector:
    required_frames: int = 10
    _frames: list[str] = field(default_factory=list)

    def observe(self, frame: str) -> ProtocolParser | None:
        require_ascii_frame(frame)
        if not frame.startswith("%ms"):
            return None
        self._frames.append(frame)
        if not self._stable():
            return None
        lengths = Counter(map(len, self._frames[-self.required_frames :]))
        expected_length, count = lengths.most_common(1)[0]
        if count != self.required_frames:
            return None
        return PrizsaltObservedParser(expected_length)

    def _stable(self) -> bool:
        recent = self._frames[-self.required_frames :]
        return len(recent) == self.required_frames and all(item.startswith("%ms") for item in recent)

    @property
    def observed_count(self) -> int:
        return len(self._frames)
