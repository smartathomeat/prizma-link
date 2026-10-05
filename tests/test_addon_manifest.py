import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_addon_versions_match_package_version() -> None:
    config = yaml.safe_load((ROOT / "addon/config.yaml").read_text(encoding="utf-8"))
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    init = (ROOT / "src/prizma_link/__init__.py").read_text(encoding="utf-8")
    assert config["version"] == "0.1.13"
    assert 'version = "0.1.13"' in pyproject
    assert '__version__ = "0.1.13"' in init


def test_public_repository_metadata_and_safe_defaults() -> None:
    repository = yaml.safe_load((ROOT / "repository.yaml").read_text(encoding="utf-8"))
    config = yaml.safe_load((ROOT / "addon/config.yaml").read_text(encoding="utf-8"))
    assert repository["url"] == "https://github.com/smartathomeat/prizma-link"
    assert config["url"] == repository["url"]
    assert config["stage"] == "experimental"
    assert config["options"]["safe_mode"] is True
    assert config["options"]["allow_start"] is False
    assert config["schema"]["devices"][0]["model"] == "list(auto|prizsalt|multisalt)"
    assert config["host_dbus"] is True
    assert config["hassio_api"] is True
    assert "full_access" not in config
    assert "docker_api" not in config
    assert "privileged" not in config


def test_addon_bridge_is_self_contained_and_matches_root_package() -> None:
    root_package = ROOT / "src/prizma_link"
    addon_package = ROOT / "addon/bridge/src/prizma_link"
    assert addon_package.is_dir()
    expected = {item.relative_to(root_package) for item in root_package.rglob("*.py")}
    actual = {item.relative_to(addon_package) for item in addon_package.rglob("*.py")}
    assert actual == expected
    for relative in expected:
        assert (addon_package / relative).read_bytes() == (root_package / relative).read_bytes()
    assert (ROOT / "addon/bridge/requirements.lock").read_bytes() == (ROOT / "requirements.lock").read_bytes()


def test_dockerfile_uses_modern_explicit_multiarch_base() -> None:
    dockerfile = (ROOT / "addon/Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.startswith(
        "FROM ghcr.io/home-assistant/base-python:3.13-alpine3.22@"
        "sha256:5acf09473efb414f4949d08e81c4ef325e03b888d9644ac8b86c9acd0d0e8ef8\n"
    )
    assert "ARG BUILD_FROM" not in dockerfile
    assert 'io.hass.type="app"' in dockerfile
    assert 'io.hass.arch="aarch64|amd64"' in dockerfile
    assert "--require-hashes -r /opt/prizma-link/requirements.lock" in dockerfile
    assert "pip3 install --no-cache-dir /opt/prizma-link" not in dockerfile


def test_s6_service_is_executable_and_uses_best_effort_pairing() -> None:
    run = ROOT / "addon/rootfs/etc/services.d/prizma-link/run"
    assert os.access(run, os.X_OK)
    text = run.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/with-contenv bashio\n")
    assert "python3 -m prizma_link.cli pair-all --best-effort" in text
    assert "export PYTHONPATH=/opt/prizma-link/src" in text


def test_apparmor_contains_official_s6_and_bashio_minimum() -> None:
    profile = (ROOT / "addon/apparmor.txt").read_text(encoding="utf-8")
    required = {
        "file,",
        "signal (send) set=(kill,term,int,hup,cont),",
        "/usr/bin/** ix,",
        "/run/{s6,s6-rc*,service}/** ix,",
        "/etc/services.d/** rwix,",
        "/run/{,**} rwk,",
        "/usr/lib/bashio/** ix,",
        "deny /var/run/docker.sock rw,",
    }
    assert all(rule in profile for rule in required)
