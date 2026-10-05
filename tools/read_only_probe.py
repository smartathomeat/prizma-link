#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from prizma_link.bluez import BluezProfileClient
from prizma_link.framing import AsciiFramer
from prizma_link.protocol.auto import AutoDetector
from prizma_link.protocol.base import STATUS_QUERY


async def probe(address: str, count: int, response_timeout: float, *, label: str, output: Path | None) -> None:
    profile = BluezProfileClient()
    await profile.start()
    connection = await profile.connect(address, connect_timeout=max(response_timeout, 10))
    framer = AsciiFramer()
    detector = AutoDetector(required_frames=count)
    try:
        for index in range(count):
            started = time.monotonic()
            await connection.write(STATUS_QUERY.encode("ascii"))
            while True:
                chunk = await asyncio.wait_for(connection.read(), response_timeout)
                frames = framer.feed(chunk)
                if not frames:
                    continue
                frame = frames[0]
                protocol = detector.observe(frame)
                printable = "".join(char if char.isprintable() else "." for char in frame)
                record: dict[str, object] = {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "label": label,
                    "frame": index + 1,
                    "count": count,
                    "length": len(frame),
                    "latency_ms": round((time.monotonic() - started) * 1000),
                    "hex": frame.encode("ascii").hex(),
                    "ascii": printable,
                }
                if protocol is not None:
                    record["protocol"] = protocol.evidence.name
                    record["write_verified"] = protocol.evidence.write_verified
                rendered = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                print(rendered)
                if output is not None:
                    with output.open("a", encoding="utf-8") as capture:
                        capture.write(rendered + "\n")
                break
    finally:
        await connection.close()
        await profile.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Send only %ms; and collect stable status frames")
    parser.add_argument("--address", required=True)
    parser.add_argument("--count", type=int, default=10, choices=range(10, 31))
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--label", default="baseline", help="capture label, for example prism1-stopped")
    parser.add_argument("--output", type=Path, help="append JSONL evidence to this file")
    args = parser.parse_args()
    asyncio.run(probe(args.address, args.count, args.timeout, label=args.label, output=args.output))


if __name__ == "__main__":
    main()
