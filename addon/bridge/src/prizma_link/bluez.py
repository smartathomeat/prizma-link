import asyncio
import os
import socket
from dataclasses import dataclass

from dbus_next import BusType
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method

from prizma_link.pairing import device_path
from prizma_link.protocol.base import SPP_UUID

AF_BLUETOOTH = getattr(socket, "AF_BLUETOOTH", 31)
BTPROTO_RFCOMM = getattr(socket, "BTPROTO_RFCOMM", 3)


class BluezError(RuntimeError):
    """BlueZ profile or RFCOMM connection failed."""


class SppProfile(ServiceInterface):
    def __init__(self) -> None:
        super().__init__("org.bluez.Profile1")
        self.connections: asyncio.Queue[tuple[str, int]] = asyncio.Queue()

    @method()
    def Release(self) -> "":
        return None

    @method()
    def NewConnection(self, device: "o", fd: "h", properties: "a{sv}") -> "":
        del properties
        duplicated = os.dup(fd)
        self.connections.put_nowait((device, duplicated))

    @method()
    def RequestDisconnection(self, device: "o") -> "":
        del device


@dataclass(slots=True)
class RfcommConnection:
    device_path: str
    sock: socket.socket

    async def read(self, size: int = 1024) -> bytes:
        loop = asyncio.get_running_loop()
        return await loop.sock_recv(self.sock, size)

    async def write(self, data: bytes) -> None:
        loop = asyncio.get_running_loop()
        await loop.sock_sendall(self.sock, data)

    async def close(self) -> None:
        self.sock.close()


class DirectRfcommClient:
    """Open Linux RFCOMM sockets directly after BlueZ has paired the device.

    Some legacy SPP modules, including the PRIZSALT+ module observed onsite,
    reject ``Device1.ConnectProfile`` while accepting a native RFCOMM socket
    on the advertised serial channel.  Direct sockets still use the BlueZ/
    kernel link key store for authentication; they only bypass Profile1.
    """

    def __init__(self, channel: int = 6) -> None:
        self.channel = channel

    async def start(self) -> None:
        return None

    async def connect(self, address: str, connect_timeout: float = 15.0) -> RfcommConnection:
        def open_socket() -> socket.socket:
            sock = socket.socket(
                AF_BLUETOOTH,
                socket.SOCK_STREAM,
                BTPROTO_RFCOMM,
            )
            try:
                sock.settimeout(connect_timeout)
                sock.connect((address, self.channel))
                sock.setblocking(False)
                return sock
            except Exception:
                sock.close()
                raise

        try:
            sock = await asyncio.to_thread(open_socket)
        except (OSError, TimeoutError) as exc:
            raise BluezError(f"direct RFCOMM connection failed: {exc}") from exc
        return RfcommConnection(device_path(address), sock)

    async def close(self) -> None:
        return None


class BluezProfileClient:
    profile_path = "/io/smartathome/prizma_link/profile"

    def __init__(self, adapter: str = "hci0") -> None:
        self.adapter = adapter
        self.bus: MessageBus | None = None
        self.profile = SppProfile()
        self._manager: object | None = None

    async def start(self) -> None:
        if self.bus is not None:
            return
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        bus.export(self.profile_path, self.profile)
        intro = await bus.introspect("org.bluez", "/org/bluez")
        obj = bus.get_proxy_object("org.bluez", "/org/bluez", intro)
        manager = obj.get_interface("org.bluez.ProfileManager1")
        await manager.call_register_profile(
            self.profile_path,
            SPP_UUID,
            {
                "Name": _variant("s", "Prizma Link SPP"),
                "Role": _variant("s", "client"),
                "RequireAuthentication": _variant("b", True),
                "RequireAuthorization": _variant("b", True),
            },
        )
        self.bus = bus
        self._manager = manager

    async def connect(self, address: str, connect_timeout: float = 15.0) -> RfcommConnection:
        if self.bus is None:
            raise BluezError("profile is not started")
        path = device_path(address, self.adapter)
        intro = await self.bus.introspect("org.bluez", path)
        obj = self.bus.get_proxy_object("org.bluez", path, intro)
        device = obj.get_interface("org.bluez.Device1")
        await device.call_connect_profile(SPP_UUID)
        try:
            incoming_path, fd = await asyncio.wait_for(self.profile.connections.get(), connect_timeout)
        except TimeoutError as exc:
            raise BluezError("BlueZ did not deliver an RFCOMM file descriptor") from exc
        if incoming_path != path:
            os.close(fd)
            raise BluezError("BlueZ delivered a connection for another device")
        sock = socket.socket(fileno=fd)
        sock.setblocking(False)
        return RfcommConnection(path, sock)

    async def close(self) -> None:
        if self.bus is None:
            return
        manager = self._manager
        try:
            if manager is not None:
                await manager.call_unregister_profile(self.profile_path)  # type: ignore[attr-defined]
        finally:
            self.bus.unexport(self.profile_path)
            self.bus.disconnect()
            self.bus = None
            self._manager = None


def _variant(signature: str, value: object) -> object:
    from dbus_next import Variant

    return Variant(signature, value)
