from collections.abc import Callable

from dbus_next import BusType, Variant
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method

from prizma_link.protocol.base import SPP_UUID


class PairingDenied(RuntimeError):
    """BlueZ requested an operation outside the configured device boundary."""


class RestrictedPairingAgent(ServiceInterface):
    def __init__(self, allowed_path: str, pin: str) -> None:
        super().__init__("org.bluez.Agent1")
        self.allowed_path = allowed_path
        self.pin = pin

    def _check(self, device: str) -> None:
        if device != self.allowed_path:
            raise PairingDenied("pairing request is not for the configured device")

    @method()
    def Release(self) -> "":
        return None

    @method()
    def RequestPinCode(self, device: "o") -> "s":
        self._check(device)
        return self.pin

    @method()
    def DisplayPinCode(self, device: "o", pincode: "s") -> "":
        self._check(device)

    @method()
    def RequestPasskey(self, device: "o") -> "u":
        self._check(device)
        return int(self.pin)

    @method()
    def DisplayPasskey(self, device: "o", passkey: "u", entered: "q") -> "":
        self._check(device)

    @method()
    def RequestConfirmation(self, device: "o", passkey: "u") -> "":
        self._check(device)

    @method()
    def RequestAuthorization(self, device: "o") -> "":
        self._check(device)

    @method()
    def AuthorizeService(self, device: "o", uuid: "s") -> "":
        self._check(device)
        if uuid.lower() != SPP_UUID.lower():
            raise PairingDenied("only the SPP service is authorized")

    @method()
    def Cancel(self) -> "":
        return None


def device_path(address: str, adapter: str = "hci0") -> str:
    normalized = address.upper().replace(":", "_")
    return f"/org/bluez/{adapter}/dev_{normalized}"


async def pair_device(
    address: str,
    pin: str,
    *,
    adapter: str = "hci0",
    on_stage: Callable[[str], None] | None = None,
) -> None:
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    path = device_path(address, adapter)
    agent_path = "/io/smartathome/prizma_link/agent"
    agent = RestrictedPairingAgent(path, pin)
    bus.export(agent_path, agent)
    bluez = await bus.introspect("org.bluez", "/org/bluez")
    manager_obj = bus.get_proxy_object("org.bluez", "/org/bluez", bluez)
    manager = manager_obj.get_interface("org.bluez.AgentManager1")
    await manager.call_register_agent(agent_path, "KeyboardDisplay")
    try:
        if on_stage:
            on_stage("pairing")
        device_intro = await bus.introspect("org.bluez", path)
        device_obj = bus.get_proxy_object("org.bluez", path, device_intro)
        device = device_obj.get_interface("org.bluez.Device1")
        properties = device_obj.get_interface("org.freedesktop.DBus.Properties")
        paired = await properties.call_get("org.bluez.Device1", "Paired")
        if not bool(paired.value):
            await device.call_pair()
        await properties.call_set("org.bluez.Device1", "Trusted", Variant("b", True))
        if on_stage:
            on_stage("paired_and_trusted")
    finally:
        await manager.call_unregister_agent(agent_path)
        bus.unexport(agent_path)
        bus.disconnect()
