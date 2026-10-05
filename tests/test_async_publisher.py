import asyncio

import pytest

from prizma_link.bridge import AsyncPublisher


class Client:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bool]] = []
        self.active = 0
        self.max_active = 0

    async def publish(self, topic: str, payload: str, *, retain: bool) -> None:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0)
        self.calls.append((topic, payload, retain))
        self.active -= 1


@pytest.mark.asyncio
async def test_publish_burst_is_serialized_and_ordered() -> None:
    client = Client()
    publisher = AsyncPublisher(client)  # type: ignore[arg-type]
    for index in range(40):
        publisher.publish(f"topic/{index}", str(index), retain=True)
    await publisher.flush()
    assert client.max_active == 1
    assert client.calls == [(f"topic/{index}", str(index), True) for index in range(40)]
    await publisher.close()


@pytest.mark.asyncio
async def test_publish_failure_is_reported_at_flush() -> None:
    class BrokenClient:
        async def publish(self, topic: str, payload: str, *, retain: bool) -> None:
            del topic, payload, retain
            raise ConnectionError("broker unavailable")

    publisher = AsyncPublisher(BrokenClient())  # type: ignore[arg-type]
    publisher.publish("topic", "value", retain=False)
    with pytest.raises(ConnectionError):
        await publisher.flush()
    await publisher.close()
