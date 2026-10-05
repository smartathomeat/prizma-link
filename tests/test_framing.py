import pytest

from prizma_link.framing import AsciiFramer


def test_partial_frame_across_reads() -> None:
    framer = AsciiFramer()
    assert framer.feed(b"%m") == []
    assert framer.feed(b"s;") == ["%ms;"]


def test_multiple_frames_in_one_read() -> None:
    assert AsciiFramer().feed(b"%ms;%rh;") == ["%ms;", "%rh;"]


def test_garbage_before_start_is_discarded() -> None:
    framer = AsciiFramer()
    assert framer.feed(b"garbage%ms;") == ["%ms;"]
    assert framer.discarded_bytes == 7


def test_missing_semicolon_remains_pending() -> None:
    framer = AsciiFramer()
    assert framer.feed(b"%ms,123") == []
    assert framer.pending == b"%ms,123"


def test_oversized_frame_is_dropped() -> None:
    framer = AsciiFramer(max_frame_size=8)
    assert framer.feed(b"%123456789;") == []
    assert framer.oversized_frames == 1


@pytest.mark.parametrize("invalid", [b"\x00", b"\n", b"\xff"])
def test_invalid_bytes_drop_partial_frame(invalid: bytes) -> None:
    framer = AsciiFramer()
    assert framer.feed(b"%ms" + invalid + b";") == []
    assert not framer.pending


def test_new_start_discards_old_partial() -> None:
    framer = AsciiFramer()
    assert framer.feed(b"%bad%ms;") == ["%ms;"]
    assert framer.discarded_bytes == 4


@pytest.mark.parametrize("split", range(1, 22))
def test_status_frame_survives_every_two_chunk_boundary(split: int) -> None:
    frame = b"%ms,00003018008110000;"
    framer = AsciiFramer()
    assert framer.feed(frame[:split]) == []
    assert framer.feed(frame[split:]) == [frame.decode("ascii")]


def test_framer_recovers_after_oversize_and_noise() -> None:
    framer = AsciiFramer(max_frame_size=8)
    assert framer.feed(b"noise%123456789;\x00more%ms;") == ["%ms;"]
    assert framer.oversized_frames == 1
    assert framer.discarded_bytes > 0
