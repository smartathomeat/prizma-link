from prizma_link.cli import _pair_all
from prizma_link.config import AppConfig, DeviceConfig


def fleet() -> AppConfig:
    return AppConfig(
        devices=(
            DeviceConfig("PRISM 1", "AA:BB:CC:DD:EE:01"),
            DeviceConfig("PRISM 2", "AA:BB:CC:DD:EE:02"),
        )
    )


async def test_pair_all_attempts_second_device_after_first_failure() -> None:
    calls: list[str] = []

    async def pairer(address: str, pin: str) -> None:
        del pin
        calls.append(address)
        if address.endswith("01"):
            raise ConnectionError("first device absent")

    failures = await _pair_all(fleet(), pairer)
    assert failures == 1
    assert calls == ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]


async def test_pair_all_reports_no_failure_when_both_succeed() -> None:
    calls: list[str] = []

    async def pairer(address: str, pin: str) -> None:
        del pin
        calls.append(address)

    failures = await _pair_all(fleet(), pairer)
    assert failures == 0
    assert len(calls) == 2
