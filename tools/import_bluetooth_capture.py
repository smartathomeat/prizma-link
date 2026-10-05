#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from prizma_link.framing import AsciiFramer
from prizma_link.protocol.auto import AutoDetector


def main() -> None:
    parser = argparse.ArgumentParser(description="Import an authorized hex RFCOMM capture")
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    detector = AutoDetector()
    framer = AsciiFramer()
    data = bytes.fromhex("".join(args.capture.read_text(encoding="utf-8").split()))
    for frame in framer.feed(data):
        protocol = detector.observe(frame)
        print(f"length={len(frame)} hex={frame.encode('ascii').hex()}")
        if protocol:
            print(f"protocol={protocol.evidence.name} write_verified={str(protocol.evidence.write_verified).lower()}")


if __name__ == "__main__":
    main()
