#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path

REQUIRED_MEMBERS = {
    "prizma_link/config.yaml",
    "prizma_link/Dockerfile",
    "prizma_link/rootfs/etc/services.d/prizma-link/run",
    "prizma_link/bridge/pyproject.toml",
    "prizma_link/bridge/requirements.lock",
    "prizma_link/bridge/src/prizma_link/cli.py",
    "prizma_link/bridge/tools/onsite_preflight.py",
    "prizma_link/bridge/tools/read_only_probe.py",
}

ADDON_TOOLS = (
    "diagnose_bluez.py",
    "onsite_preflight.py",
    "read_only_probe.py",
)


def build(source: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing archive: {destination}")
    with tempfile.TemporaryDirectory(prefix="prizma-link-package-") as temporary:
        stage = Path(temporary) / "prizma_link"
        shutil.copytree(source / "addon", stage, ignore=shutil.ignore_patterns("bridge"))
        bridge = stage / "bridge"
        (bridge / "src").mkdir(parents=True)
        shutil.copytree(
            source / "src" / "prizma_link",
            bridge / "src" / "prizma_link",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        (bridge / "tools").mkdir()
        for filename in ADDON_TOOLS:
            shutil.copy2(source / "tools" / filename, bridge / "tools" / filename)
        for filename in ("pyproject.toml", "requirements.lock", "README.md", "CHANGELOG.md", "LICENSE"):
            shutil.copy2(source / filename, bridge / filename)

        with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in sorted(stage.rglob("*")):
                if item.is_dir() or "__pycache__" in item.parts or item.suffix == ".pyc":
                    continue
                archive.write(item, item.relative_to(stage.parent))

    with zipfile.ZipFile(destination) as archive:
        members = set(archive.namelist())
        missing = REQUIRED_MEMBERS - members
        if missing:
            raise RuntimeError(f"archive is missing required members: {sorted(missing)}")
        if any("__pycache__" in item or item.endswith(".pyc") for item in members):
            raise RuntimeError("archive contains Python bytecode cache")
        forbidden = (".deploy-", ".local.yaml", "macos_prism_pair_probe", "sonic_reference")
        if any(any(marker in item for marker in forbidden) for item in members):
            raise RuntimeError("archive contains a forbidden private or unlicensed member")
        bad_layout = [item for item in members if item.startswith("prizma_link/bridge/prizma_link/")]
        if bad_layout:
            raise RuntimeError("archive contains obsolete flat Python package layout")
        corrupt = archive.testzip()
        if corrupt is not None:
            raise RuntimeError(f"archive member failed CRC verification: {corrupt}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and validate a Home Assistant Prizma Link add-on ZIP")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    build(args.source.resolve(), args.destination.resolve())
    print(args.destination.resolve())


if __name__ == "__main__":
    main()
