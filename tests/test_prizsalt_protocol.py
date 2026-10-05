import pytest

from prizma_link.protocol.base import ProtocolError
from prizma_link.protocol.prizsalt import PrizsaltObservedParser, prizsalt_status_fixture
from prizma_link.state import OperatingState


@pytest.mark.parametrize(
    ("status", "expected"),
    [(0, OperatingState.STOPPED), (1, OperatingState.RUNNING)],
)
def test_observed_prizsalt_statuses(status: int, expected: OperatingState) -> None:
    state = PrizsaltObservedParser(32).parse_status(
        prizsalt_status_fixture(status=status), safe_mode=True
    )
    assert state.operating_state is expected
    assert state.protocol_verified


def test_prizsalt_error_overrides_status() -> None:
    state = PrizsaltObservedParser(32).parse_status(prizsalt_status_fixture(error=2), safe_mode=True)
    assert state.operating_state is OperatingState.ERROR
    assert state.error_code == 2
    assert state.error_text == "Gerätefehler 2"


@pytest.mark.parametrize(
    "frame",
    [
        "%ms;",
        "%ms,00Z03018008110000;",
        "%ms,00003018A08110000;",
        "%ms,0009918008110000;",
        "%ms,00403018008110000;",
    ],
)
def test_invalid_prizsalt_frames_are_rejected(frame: str) -> None:
    with pytest.raises(ProtocolError):
        PrizsaltObservedParser(32).parse_status(frame, safe_mode=True)


def test_unknown_error_code_is_preserved() -> None:
    state = PrizsaltObservedParser(32).parse_status(prizsalt_status_fixture(error=3), safe_mode=True)
    assert state.error_code == 3
    assert state.error_text == "Gerätefehler 3"


def test_prizsalt_observed_parser_never_enables_writes() -> None:
    frame = "%ms,0123456789ABCDEF;"
    parser = PrizsaltObservedParser(len(frame))
    state = parser.parse_status(frame, safe_mode=True)
    assert not state.protocol_verified
    assert state.operating_state is OperatingState.UNKNOWN
    with pytest.raises(ProtocolError):
        parser.encode_settings(state)
