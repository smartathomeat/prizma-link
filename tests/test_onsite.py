from prizma_link.config import DeviceConfig
from prizma_link.onsite import parse_bluetoothctl_info
from prizma_link.protocol.base import SPP_UUID


def test_ready_device_is_reported_with_masked_address() -> None:
    device = DeviceConfig("PRISM 1", "AA:BB:CC:DD:EE:01", model="prizsalt")
    output = f"""
Device AA:BB:CC:DD:EE:01
        Name: PSN_IF-0001
        Paired: yes
        Trusted: yes
        Connected: no
        UUID: Serial Port ({SPP_UUID})
"""
    report = parse_bluetoothctl_info(device, output)
    assert report.read_only_ready
    assert report.address == "XX:XX:XX:XX:EE:01"
    assert not report.connected
    assert "AA:BB:CC:DD" not in str(report.masked_dict())


def test_visible_but_unpaired_device_is_not_ready() -> None:
    device = DeviceConfig("PRISM 2", "AA:BB:CC:DD:EE:02")
    output = """
Device AA:BB:CC:DD:EE:02
        Paired: no
        Trusted: no
        Connected: no
"""
    report = parse_bluetoothctl_info(device, output)
    assert report.visible
    assert not report.read_only_ready
    assert not report.spp_uuid


def test_unavailable_device_is_not_visible() -> None:
    device = DeviceConfig("PRISM 2", "AA:BB:CC:DD:EE:02")
    report = parse_bluetoothctl_info(device, "Device AA:BB:CC:DD:EE:02 not available")
    assert not report.visible
    assert not report.read_only_ready
