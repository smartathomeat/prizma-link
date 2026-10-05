import asyncio
from pathlib import Path

import pytest

from prizma_link.config import DeviceConfig
from prizma_link.macos_native import MacNativeError, MacNativeProfileClient


def helper(tmp_path: Path, body: str) -> Path:
    source = tmp_path / "helper.sh"
    source.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    source.chmod(0o700)
    return source


@pytest.mark.asyncio
async def test_native_helper_relays_only_status_queries(tmp_path: Path) -> None:
    arguments = tmp_path / "arguments.txt"
    source = helper(
        tmp_path,
        f'printf "%s\\n" "$@" > "{arguments}"\n'
        'echo READY\nwhile read line; do echo "%ms,reply;"; done\n',
    )
    device = DeviceConfig(
        "PRISM",
        "AA:BB:CC:DD:EE:FF",
        pin="9876",
        bluetooth_name="PSN_IF-TEST",
    )
    profile = MacNativeProfileClient((device,), str(source))
    await profile.start()
    connection = await profile.connect(device.address)
    try:
        await connection.write(b"%ms;")
        assert await asyncio.wait_for(connection.read(), timeout=1) == b"%ms,reply;"
        assert arguments.read_text(encoding="utf-8").splitlines() == [
            "--name",
            "PSN_IF-TEST",
            "--address",
            "AA:BB:CC:DD:EE:FF",
            "--pin",
            "9876",
        ]
        with pytest.raises(MacNativeError, match="read-only"):
            await connection.write(b"%st,1;")
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_native_helper_rejects_unconfigured_device(tmp_path: Path) -> None:
    source = helper(tmp_path, "echo READY\n")
    device = DeviceConfig("PRISM", "AA:BB:CC:DD:EE:FF")
    profile = MacNativeProfileClient((device,), str(source))
    await profile.start()
    with pytest.raises(MacNativeError, match="no bluetooth_name"):
        await profile.connect(device.address)


def test_swift_helper_has_no_default_pin_and_requires_exact_identity() -> None:
    text = (Path(__file__).resolve().parents[1] / "tools/macos_prism_rfcomm_helper.swift").read_text(
        encoding="utf-8"
    )
    assert 'Array("1234".utf8)' not in text
    assert 'argumentValue("--address")' in text
    assert 'argumentValue("--pin")' in text
    assert "device.addressString.uppercased() == address" in text
