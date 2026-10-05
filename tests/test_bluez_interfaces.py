import asyncio
import socket

import pytest

from prizma_link.bluez import DirectRfcommClient, RfcommConnection, SppProfile
from prizma_link.pairing import PairingDenied, RestrictedPairingAgent
from prizma_link.protocol.base import SPP_UUID


def test_dbus_interfaces_import_and_construct() -> None:
    assert SppProfile().name == "org.bluez.Profile1"
    assert RestrictedPairingAgent("/allowed", "1234").name == "org.bluez.Agent1"


def test_pairing_agent_accepts_only_configured_device() -> None:
    agent = RestrictedPairingAgent("/allowed", "1234")
    request_pin = RestrictedPairingAgent.RequestPinCode.__wrapped__
    assert request_pin(agent, "/allowed") == "1234"
    with pytest.raises(PairingDenied):
        request_pin(agent, "/other")


def test_pairing_agent_authorizes_only_spp() -> None:
    agent = RestrictedPairingAgent("/allowed", "1234")
    authorize = RestrictedPairingAgent.AuthorizeService.__wrapped__
    authorize(agent, "/allowed", SPP_UUID)
    with pytest.raises(PairingDenied):
        authorize(agent, "/allowed", "0000180f-0000-1000-8000-00805f9b34fb")


def test_direct_rfcomm_client_opens_configured_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []

    class FakeSocket:
        def settimeout(self, value: float) -> None:
            calls.append(("timeout", value))

        def connect(self, target: tuple[str, int]) -> None:
            calls.append(("connect", target))

        def setblocking(self, value: bool) -> None:
            calls.append(("blocking", value))

        def close(self) -> None:
            calls.append("close")

    def fake_socket(family: int, kind: int, protocol: int) -> FakeSocket:
        calls.append(("socket", family, kind, protocol))
        return FakeSocket()

    client = DirectRfcommClient(channel=6)

    async def exercise() -> RfcommConnection:
        # Patch only after asyncio has created its own real control sockets.
        monkeypatch.setattr(socket, "socket", fake_socket)
        return await client.connect("00:11:22:33:44:55", connect_timeout=9)

    connection = asyncio.run(exercise())

    assert connection.device_path.endswith("dev_00_11_22_33_44_55")
    assert ("connect", ("00:11:22:33:44:55", 6)) in calls
    assert ("timeout", 9) in calls
    assert ("blocking", False) in calls
