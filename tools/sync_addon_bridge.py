#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "addon" / "bridge"
ADDON_TOOLS = (
    "diagnose_bluez.py",
    "onsite_preflight.py",
    "read_only_probe.py",
)


def sync() -> None:
    """Regenerate the self-contained Home Assistant app build context."""
    if TARGET.is_symlink():
        raise RuntimeError("refusing to replace a symlinked addon/bridge directory")
    with tempfile.TemporaryDirectory(prefix="prizma-link-addon-") as temporary:
        stage = Path(temporary) / "bridge"
        (stage / "src").mkdir(parents=True)
        shutil.copytree(
            ROOT / "src" / "prizma_link",
            stage / "src" / "prizma_link",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        (stage / "tools").mkdir()
        for filename in ADDON_TOOLS:
            shutil.copy2(ROOT / "tools" / filename, stage / "tools" / filename)
        for filename in ("pyproject.toml", "requirements.lock", "README.md", "CHANGELOG.md", "LICENSE"):
            shutil.copy2(ROOT / filename, stage / filename)

        if TARGET.exists():
            shutil.rmtree(TARGET)
        shutil.copytree(stage, TARGET)


def check() -> None:
    """Fail unless the committed add-on bridge exactly matches generated public inputs."""
    with tempfile.TemporaryDirectory(prefix="prizma-link-addon-check-") as temporary:
        expected = Path(temporary) / "bridge"
        (expected / "src").mkdir(parents=True)
        shutil.copytree(
            ROOT / "src" / "prizma_link",
            expected / "src" / "prizma_link",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        (expected / "tools").mkdir()
        for filename in ADDON_TOOLS:
            shutil.copy2(ROOT / "tools" / filename, expected / "tools" / filename)
        for filename in ("pyproject.toml", "requirements.lock", "README.md", "CHANGELOG.md", "LICENSE"):
            shutil.copy2(ROOT / filename, expected / filename)

        expected_files = {item.relative_to(expected) for item in expected.rglob("*") if item.is_file()}
        actual_files = {
            item.relative_to(TARGET)
            for item in TARGET.rglob("*")
            if item.is_file() and ".ruff_cache" not in item.parts and "__pycache__" not in item.parts
        }
        if expected_files != actual_files:
            missing = sorted(str(item) for item in expected_files - actual_files)
            extra = sorted(str(item) for item in actual_files - expected_files)
            raise RuntimeError(f"add-on bridge file set mismatch: missing={missing}, extra={extra}")
        changed = [
            item
            for item in sorted(expected_files)
            if (expected / item).read_bytes() != (TARGET / item).read_bytes()
        ]
        if changed:
            raise RuntimeError(f"add-on bridge content mismatch: {[str(item) for item in changed]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate or verify the self-contained app bridge")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    check() if args.check else sync()
