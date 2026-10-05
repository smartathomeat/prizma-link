from __future__ import annotations

import asyncio
import logging
import sys
import time
from collections.abc import Awaitable
from dataclasses import dataclass, field, replace
from typing import Protocol

import aiomqtt

from prizma_link.bluez import BluezProfileClient, DirectRfcommClient
from prizma_link.config import AppConfig, DeviceConfig
from prizma_link.device import DeviceController, SafetyError
from prizma_link.framing import AsciiFramer
from prizma_link.macos_native import MacNativeProfileClient
from prizma_link.mqtt import DiscoveryBuilder, MqttBridge
from prizma_link.protocol.auto import AutoDetector
from prizma_link.protocol.base import STATUS_QUERY, ProtocolError

LOGGER = logging.getLogger(__name__)


class Connection(Protocol):
    async def read(self, size: int = 1024) -> bytes: ...

    async def write(self, data: bytes) -> None: ...

    async def close(self) -> None: ...


class ProfileClient(Protocol):
    async def start(self) -> None: ...

    def connect(self, address: str, connect_timeout: float = 15.0) -> Awaitable[Connection]: ...

    async def close(self) -> None: ...


class AsyncPublisher:
    def __init__(self, client: aiomqtt.Client) -> None:
        self.client = client
        self.queue: asyncio.Queue[tuple[str, str, bool]] = asyncio.Queue()
        self.failures: list[Exception] = []
        self.worker = asyncio.create_task(self._run())

    def publish(self, topic: str, payload: str, *, retain: bool) -> object:
        self.queue.put_nowait((topic, payload, retain))
        return self.queue

    async def _run(self) -> None:
        while True:
            topic, payload, retain = await self.queue.get()
            try:
                await self.client.publish(topic, payload, retain=retain)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.failures.append(exc)
                LOGGER.error("MQTT publish failed topic=%s error=%s", topic, exc)
            finally:
                self.queue.task_done()

    async def flush(self) -> None:
        await self.queue.join()
        if self.failures:
            failure = self.failures.pop(0)
            self.failures.clear()
            raise failure

    async def close(self) -> None:
        await self.flush()
        self.worker.cancel()
        await asyncio.gather(self.worker, return_exceptions=True)


@dataclass(slots=True)
class LiveSession:
    config: AppConfig
    device: DeviceConfig
    profile: ProfileClient
    mqtt: MqttBridge
    connection: Connection | None = None
    write_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    controller: DeviceController = field(init=False)
    detector: AutoDetector = field(default_factory=AutoDetector)
    reconnect_requested: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self) -> None:
        self.controller = DeviceController(self.device, self.config, self._write)

    async def _write(self, data: bytes) -> None:
        if self.connection is None:
            raise ConnectionError("RFCOMM connection is unavailable")
        async with self.write_lock:
            await self.connection.write(data)

    async def run(self) -> None:
        backoff = 1
        while True:
            try:
                LOGGER.info("connecting device=%s", self.device.masked_address)
                self.connection = await self.profile.connect(self.device.address)
                self.controller.state = replace(
                    self.controller.state, connected=True, paired=True, safe_mode=self.config.safe_mode
                )
                self.mqtt.publish_availability(self.device, True)
                await self.controller.reconnect()
                backoff = 1
                await self._connected_loop()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOGGER.warning("connection cycle failed device=%s error=%s", self.device.masked_address, exc)
            finally:
                if self.connection is not None:
                    await self.connection.close()
                    self.connection = None
                self.controller.disconnect()
                self.mqtt.publish_state(self.device, self.controller.state)
                self.mqtt.publish_availability(self.device, False)
                self.detector = AutoDetector()
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self.config.reconnect_max_seconds)

    async def _connected_loop(self) -> None:
        assert self.connection is not None
        reader = asyncio.create_task(self._reader_loop())
        poller = asyncio.create_task(self._poll_loop())
        reconnect = asyncio.create_task(self.reconnect_requested.wait())
        tasks = {reader, poller, reconnect}
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task is not reconnect:
                    task.result()
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.reconnect_requested.clear()

    async def _reader_loop(self) -> None:
        assert self.connection is not None
        framer = AsciiFramer()
        while True:
            chunk = await self.connection.read()
            if not chunk:
                raise ConnectionError("RFCOMM connection closed")
            for frame in framer.feed(chunk):
                LOGGER.debug("received frame device=%s length=%d", self.device.masked_address, len(frame))
                if self.controller.protocol is None:
                    protocol = self.detector.observe(frame)
                    if protocol is None:
                        continue
                    self.controller.set_protocol(protocol)
                try:
                    state = self.controller.accept_status(frame)
                except ProtocolError as exc:
                    LOGGER.warning("rejected status frame device=%s error=%s", self.device.masked_address, exc)
                    continue
                self.mqtt.publish_state(self.device, state)

    async def _poll_loop(self) -> None:
        while True:
            started = time.monotonic()
            await self._write(STATUS_QUERY.encode("ascii"))
            elapsed = round((time.monotonic() - started) * 1000)
            self.controller.state = replace(self.controller.state, response_latency_ms=elapsed)
            await asyncio.sleep(self.config.poll_interval)

    async def handle_command(self, object_id: str, payload: str, retain: bool) -> None:
        del payload
        if retain:
            LOGGER.warning("rejected retained command device=%s object=%s", self.device.masked_address, object_id)
            return
        try:
            if object_id in {"start", "pause", "stop"}:
                await asyncio.wait_for(self.controller.execute_action(object_id), timeout=self.config.command_timeout)
            elif object_id == "refresh_status":
                await self.controller.query_status()
            elif object_id == "reconnect":
                self.reconnect_requested.set()
            elif object_id in {"duration_minutes", "fan_percent", "program"} or object_id.startswith("salt_interval_"):
                raise SafetyError("settings encoder is not write-verified for this protocol")
            else:
                raise SafetyError("unknown command topic")
        except (SafetyError, ProtocolError, TimeoutError) as exc:
            self.controller.state = replace(
                self.controller.state,
                command_failures=self.controller.state.command_failures + 1,
            )
            LOGGER.warning("command blocked device=%s object=%s reason=%s", self.device.masked_address, object_id, exc)


async def run_bridge(config: AppConfig) -> None:
    profile = _profile_for(config)
    await profile.start()
    client = aiomqtt.Client(
        hostname=config.mqtt.host,
        port=config.mqtt.port,
        username=config.mqtt.username,
        password=config.mqtt.password,
        identifier=config.mqtt.client_id,
    )
    try:
        async with client:
            publisher = AsyncPublisher(client)
            try:
                mqtt = MqttBridge(publisher, config.mqtt.discovery_prefix)
                sessions = {
                    item.normalized_address: LiveSession(config, item, profile, mqtt) for item in config.devices
                }
                for item in config.devices:
                    mqtt.publish_discovery(item)
                    mqtt.publish_availability(item, False)
                await publisher.flush()
                async with asyncio.TaskGroup() as group:
                    for session in sessions.values():
                        group.create_task(session.run())
                    group.create_task(_command_loop(client, sessions, mqtt.builder))
            finally:
                await publisher.close()
    finally:
        await profile.close()


def _profile_for(config: AppConfig) -> ProfileClient:
    transport = config.transport
    if transport == "auto":
        transport = "macos_native" if sys.platform == "darwin" else "bluez"
    if transport == "macos_native":
        return MacNativeProfileClient(config.devices, config.macos_helper_path)
    if transport == "bluez":
        return DirectRfcommClient()
    return BluezProfileClient()


async def _command_loop(
    client: aiomqtt.Client,
    sessions: dict[str, LiveSession],
    builder: DiscoveryBuilder,
) -> None:
    del builder
    await client.subscribe("prizma/+/command/+")
    async for message in client.messages:
        parts = str(message.topic).split("/")
        if len(parts) != 4:
            continue
        _, normalized, _, object_id = parts
        session = sessions.get(normalized)
        if session is None:
            continue
        payload = bytes(message.payload).decode("utf-8", errors="replace")
        await session.handle_command(object_id, payload, bool(message.retain))
