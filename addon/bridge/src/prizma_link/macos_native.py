from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from prizma_link.config import DeviceConfig
from prizma_link.protocol.base import STATUS_QUERY


class MacNativeError(RuntimeError):
    """The native macOS IOBluetooth RFCOMM helper failed."""


@dataclass(slots=True)
class MacNativeConnection:
    device_path: str
    process: asyncio.subprocess.Process

    async def read(self, size: int = 1024) -> bytes:
        del size
        if self.process.stdout is None:
            raise MacNativeError("helper stdout is unavailable")
        line = await self.process.stdout.readline()
        if not line:
            raise MacNativeError("native RFCOMM helper closed")
        frame = line.rstrip(b"\r\n")
        if not frame.startswith(b"%") or not frame.endswith(b";"):
            raise MacNativeError("native RFCOMM helper returned an invalid frame")
        return frame

    async def write(self, data: bytes) -> None:
        if data != STATUS_QUERY.encode("ascii"):
            raise MacNativeError("native helper is read-only until the device protocol is verified")
        if self.process.stdin is None or self.process.returncode is not None:
            raise MacNativeError("native RFCOMM helper is not running")
        self.process.stdin.write(data + b"\n")
        await self.process.stdin.drain()

    async def close(self) -> None:
        if self.process.stdin is not None:
            self.process.stdin.close()
        if self.process.returncode is None:
            self.process.terminate()
        await self.process.wait()


class MacNativeProfileClient:
    """Create one native IOBluetooth helper process per configured PRISM."""

    def __init__(self, devices: Iterable[DeviceConfig], helper_path: str) -> None:
        self._devices = {
            device.normalized_address: device
            for device in devices
            if device.bluetooth_name is not None
        }
        self._helper_path = str(Path(helper_path).expanduser())
        helper = Path(self._helper_path)
        if not helper.is_file() or not helper.stat().st_mode & 0o111:
            raise MacNativeError(f"native helper is missing or not executable: {helper}")

    async def start(self) -> None:
        return None

    async def connect(self, address: str, connect_timeout: float = 15.0) -> MacNativeConnection:
        normalized = address.lower().replace(":", "")
        device = self._devices.get(normalized)
        if device is None or device.bluetooth_name is None:
            raise MacNativeError("no bluetooth_name is configured for this device")
        process = await asyncio.create_subprocess_exec(
            self._helper_path,
            "--name",
            device.bluetooth_name,
            "--address",
            device.address.upper(),
            "--pin",
            device.pin,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert process.stdout is not None
        try:
            ready = await asyncio.wait_for(process.stdout.readline(), timeout=max(connect_timeout, 45.0))
        except TimeoutError:
            process.terminate()
            await process.wait()
            raise MacNativeError("native RFCOMM helper did not become ready") from None
        if ready.rstrip(b"\r\n") != b"READY":
            error = await _helper_error(process)
            raise MacNativeError(error)
        return MacNativeConnection(device.address.upper(), process)

    async def close(self) -> None:
        return None


async def _helper_error(process: asyncio.subprocess.Process) -> str:
    if process.returncode is None:
        process.terminate()
    await process.wait()
    if process.stderr is None:
        return "native RFCOMM helper failed"
    detail = (await process.stderr.read()).decode("utf-8", errors="replace").strip()
    return detail.splitlines()[-1] if detail else "native RFCOMM helper failed"
