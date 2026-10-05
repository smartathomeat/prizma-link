from __future__ import annotations

from dataclasses import asdict, dataclass

from prizma_link.config import DeviceConfig
from prizma_link.protocol.base import SPP_UUID


@dataclass(frozen=True, slots=True)
class DevicePreflight:
    name: str
    address: str
    visible: bool
    paired: bool
    trusted: bool
    connected: bool
    spp_uuid: bool

    @property
    def read_only_ready(self) -> bool:
        return self.visible and self.paired and self.trusted and self.spp_uuid

    def masked_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["address"] = self.address
        result["read_only_ready"] = self.read_only_ready
        return result


def parse_bluetoothctl_info(device: DeviceConfig, output: str) -> DevicePreflight:
    lowered = output.lower()
    unavailable = "not available" in lowered or "missing device address" in lowered
    visible = not unavailable and "device " in lowered
    return DevicePreflight(
        name=device.name,
        address=device.masked_address,
        visible=visible,
        paired=_property_is_yes(output, "Paired"),
        trusted=_property_is_yes(output, "Trusted"),
        connected=_property_is_yes(output, "Connected"),
        spp_uuid=SPP_UUID.lower() in lowered,
    )


def _property_is_yes(output: str, name: str) -> bool:
    prefix = f"{name.casefold()}:"
    for line in output.splitlines():
        stripped = line.strip().casefold()
        if stripped.startswith(prefix):
            return stripped.removeprefix(prefix).strip() == "yes"
    return False
