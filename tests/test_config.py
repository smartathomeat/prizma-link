from pathlib import Path

import pytest

from prizma_link.config import AppConfig, ConfigError, DeviceConfig, load_config


@pytest.mark.parametrize(
    "address",
    [
        "GG:BB:CC:DD:EE:FF",
        "AA:BB:CC:DD:EE",
        "AA-BB-CC-DD-EE-FF",
        "AA:BB:CC:DD:EE:FFF",
    ],
)
def test_invalid_bluetooth_addresses_are_rejected(address: str) -> None:
    with pytest.raises(ConfigError):
        DeviceConfig("Generator", address)


def test_empty_device_name_is_rejected() -> None:
    with pytest.raises(ConfigError):
        DeviceConfig("  ", "AA:BB:CC:DD:EE:FF")


def test_duplicate_addresses_are_case_insensitive() -> None:
    with pytest.raises(ConfigError):
        AppConfig(
            devices=(
                DeviceConfig("Generator 1", "AA:BB:CC:DD:EE:FF"),
                DeviceConfig("Generator 2", "aa:bb:cc:dd:ee:ff"),
            )
        )


def test_duplicate_names_are_case_and_whitespace_insensitive() -> None:
    with pytest.raises(ConfigError):
        AppConfig(
            devices=(
                DeviceConfig("Generator", "AA:BB:CC:DD:EE:01"),
                DeviceConfig(" generator ", "AA:BB:CC:DD:EE:02"),
            )
        )


def test_two_device_yaml_loads_with_safe_defaults(tmp_path: Path) -> None:
    source = tmp_path / "fleet.yaml"
    source.write_text(
        """
devices:
  - name: PRISM 1
    address: AA:BB:CC:DD:EE:01
    model: prizsalt
  - name: PRISM 2
    address: AA:BB:CC:DD:EE:02
    model: prizsalt
""",
        encoding="utf-8",
    )
    config = load_config(source)
    assert len(config.devices) == 2
    assert config.safe_mode is True
    assert config.allow_start is False
    assert {item.normalized_address for item in config.devices} == {"aabbccddee01", "aabbccddee02"}


@pytest.mark.parametrize("field", ["safe_mode", "allow_start"])
def test_quoted_safety_boolean_is_rejected(tmp_path: Path, field: str) -> None:
    source = tmp_path / "unsafe.yaml"
    source.write_text(
        f"""
devices:
  - name: PRISM 1
    address: AA:BB:CC:DD:EE:01
    model: prizsalt
{field}: "false"
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="unquoted YAML boolean"):
        load_config(source)


def test_macos_native_requires_a_name_for_every_device() -> None:
    with pytest.raises(ConfigError, match="requires bluetooth_name"):
        AppConfig(
            devices=(DeviceConfig("PRISM", "AA:BB:CC:DD:EE:FF"),),
            transport="macos_native",
        )


def test_macos_native_yaml_loads(tmp_path: Path) -> None:
    source = tmp_path / "macos.yaml"
    source.write_text(
        """
transport: macos_native
devices:
  - name: PRISM 1
    address: AA:BB:CC:DD:EE:01
    model: auto
    bluetooth_name: PSN_IF-0001
""",
        encoding="utf-8",
    )
    config = load_config(source)
    assert config.transport == "macos_native"
    assert config.devices[0].bluetooth_name == "PSN_IF-0001"
    assert config.safe_mode is True
    assert config.allow_start is False
