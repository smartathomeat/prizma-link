#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess

MAC = re.compile(r"(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b")


def mask(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        parts = match.group(0).upper().split(":")
        return f"XX:XX:XX:XX:{parts[-2]}:{parts[-1]}"

    return MAC.sub(replace, text)


def run(*command: str, timeout: int = 10) -> str:
    completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    return mask(completed.stdout + completed.stderr).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-seconds", type=int, default=30)
    args = parser.parse_args()
    seconds = min(max(args.scan_seconds, 1), 30)
    print(run("bluetoothctl", "show"))
    subprocess.run(
        ["timeout", str(seconds), "bluetoothctl", "scan", "on"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(run("bluetoothctl", "devices"))
    print(run("bluetoothctl", "devices", "Paired"))


if __name__ == "__main__":
    main()
