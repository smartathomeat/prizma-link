from prizma_link.protocol.auto import AutoDetector
from prizma_link.protocol.prizsalt import PrizsaltObservedParser


def test_unknown_stable_shape_becomes_read_only() -> None:
    detector = AutoDetector()
    frame = "%ms,0123456789ABCDEF;"
    for _ in range(9):
        assert detector.observe(frame) is None
    result = detector.observe(frame)
    assert isinstance(result, PrizsaltObservedParser)
    assert not result.evidence.write_verified


def test_live_prizsalt_frame_exposes_narrow_start_stop_proof_after_ten_samples() -> None:
    detector = AutoDetector()
    frame = "%ms,0100995940aaaaaaaaaaa------;"
    for _ in range(9):
        assert detector.observe(frame) is None

    result = detector.observe(frame)
    assert isinstance(result, PrizsaltObservedParser)
    assert result.evidence.write_verified
    state = result.parse_status(frame, safe_mode=True)
    assert state.connected
    assert state.safe_mode
    assert state.protocol_verified
    assert state.operating_state.value == "STOPPED"
    assert state.duration_minutes == 99
    assert state.remaining_seconds == 5940
    assert state.error_code == 0
    assert state.error_text == "Kein Fehler"
    assert state.last_raw_frame == frame
    assert result.encode_action("start") == "%st,1;"
    assert result.encode_action("stop") == "%st,0;"


def test_live_prizsalt_running_transition_and_countdown() -> None:
    parser = PrizsaltObservedParser(expected_length=32)

    first = parser.parse_status("%ms,0110995913aaaaaaaaaaa------;", safe_mode=True)
    second = parser.parse_status("%ms,0110995912aaaaaaaaaaa------;", safe_mode=True)
    stopped = parser.parse_status("%ms,0100990000aaaaaaaaaaa------;", safe_mode=True)

    assert first.operating_state.value == "RUNNING"
    assert first.remaining_seconds == 5913
    assert second.remaining_seconds == 5912
    assert stopped.operating_state.value == "STOPPED"
    assert stopped.remaining_seconds == 0


def test_mixed_lengths_do_not_verify() -> None:
    detector = AutoDetector()
    for index in range(10):
        frame = "%ms,1234;" if index % 2 else "%ms,12345;"
        assert detector.observe(frame) is None
