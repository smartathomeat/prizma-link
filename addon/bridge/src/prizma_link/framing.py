from __future__ import annotations


class FrameError(ValueError):
    """Malformed protocol frame."""


class AsciiFramer:
    def __init__(self, max_frame_size: int = 256) -> None:
        if max_frame_size < 4:
            raise ValueError("max_frame_size must be at least 4")
        self.max_frame_size = max_frame_size
        self._buffer = bytearray()
        self.discarded_bytes = 0
        self.oversized_frames = 0

    def feed(self, data: bytes) -> list[str]:
        frames: list[str] = []
        for value in data:
            if not self._buffer:
                if value == ord("%"):
                    self._buffer.append(value)
                else:
                    self.discarded_bytes += 1
                continue

            if value == ord("%"):
                self.discarded_bytes += len(self._buffer)
                self._buffer.clear()
                self._buffer.append(value)
                continue

            if value < 0x20 or value > 0x7E:
                self.discarded_bytes += len(self._buffer) + 1
                self._buffer.clear()
                continue

            self._buffer.append(value)
            if len(self._buffer) > self.max_frame_size:
                self.oversized_frames += 1
                self._buffer.clear()
                continue

            if value == ord(";"):
                frames.append(self._buffer.decode("ascii"))
                self._buffer.clear()
        return frames

    def reset(self) -> None:
        self._buffer.clear()

    @property
    def pending(self) -> bytes:
        return bytes(self._buffer)
