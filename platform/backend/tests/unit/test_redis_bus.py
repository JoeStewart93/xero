from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from app.config import Settings
from app.redis_bus import (
    cache_delete,
    cache_get_json,
    cache_set_json,
    check_rate_limit,
    close_redis,
    dequeue_task,
    enqueue_task,
    initialize_redis,
    operator_events_channel,
    publish_event,
    receive_event,
    session_cache_key,
    task_queue_key,
)
from redis.exceptions import ConnectionError


class FakePubSub:
    def __init__(self, client: FakeRedis) -> None:
        self.client = client
        self.channel = ""
        self.messages: list[dict[str, Any]] = []

    async def subscribe(self, channel: str) -> None:
        self.channel = channel
        self.client.subscribers.setdefault(channel, []).append(self)

    async def get_message(self, *, ignore_subscribe_messages: bool, timeout: float) -> dict[str, Any] | None:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if self.messages:
                message = self.messages.pop(0)
                if ignore_subscribe_messages and message.get("type") != "message":
                    continue
                return message
            await asyncio.sleep(0.01)
        return None

    async def unsubscribe(self, channel: str) -> None:
        if channel in self.client.subscribers:
            self.client.subscribers[channel] = [
                subscriber for subscriber in self.client.subscribers[channel] if subscriber is not self
            ]

    async def aclose(self) -> None:
        await self.unsubscribe(self.channel)


class FakeRedis:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.closed = False
        self.queues: dict[str, list[str]] = {}
        self.values: dict[str, str] = {}
        self.counters: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.subscribers: dict[str, list[FakePubSub]] = {}

    def _raise_if_failed(self) -> None:
        if self.fail:
            raise ConnectionError("redis unavailable")

    async def ping(self) -> bool:
        self._raise_if_failed()
        return True

    async def aclose(self) -> None:
        self.closed = True

    async def rpush(self, key: str, value: str) -> int:
        self._raise_if_failed()
        self.queues.setdefault(key, []).append(value)
        return len(self.queues[key])

    async def blpop(self, keys: list[str], timeout: float = 0) -> tuple[str, str] | None:
        self._raise_if_failed()
        key = keys[0]
        if self.queues.get(key):
            return key, self.queues[key].pop(0)
        return None

    def pubsub(self) -> FakePubSub:
        return FakePubSub(self)

    async def publish(self, channel: str, value: str) -> int:
        self._raise_if_failed()
        subscribers = self.subscribers.get(channel, [])
        for subscriber in subscribers:
            subscriber.messages.append({"type": "message", "channel": channel, "data": value})
        return len(subscribers)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._raise_if_failed()
        self.values[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True

    async def get(self, key: str) -> str | None:
        self._raise_if_failed()
        return self.values.get(key)

    async def delete(self, key: str) -> int:
        self._raise_if_failed()
        existed = key in self.values or key in self.queues or key in self.counters
        self.values.pop(key, None)
        self.queues.pop(key, None)
        self.counters.pop(key, None)
        self.ttls.pop(key, None)
        return int(existed)

    async def incr(self, key: str) -> int:
        self._raise_if_failed()
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key: str, seconds: int) -> bool:
        self._raise_if_failed()
        self.ttls[key] = seconds
        return True

    async def ttl(self, key: str) -> int:
        self._raise_if_failed()
        return self.ttls.get(key, -1)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_initialize_redis_records_startup_status_and_closes(monkeypatch):
    fake = FakeRedis()
    app = SimpleNamespace(state=SimpleNamespace())
    monkeypatch.setattr("app.redis_bus.create_redis_client", lambda _: fake)

    await initialize_redis(app, Settings(app_env="development"))

    assert app.state.redis_client is fake
    assert app.state.redis_startup_status == {"status": "healthy"}

    await close_redis(app)

    assert fake.closed is True
    assert app.state.redis_client is None


@pytest.mark.anyio
async def test_redis_enqueue_dequeue_round_trip():
    fake = FakeRedis()
    payload = {"task_id": "task-1", "priority": 10}

    assert await enqueue_task(fake, "beacon:test", payload) is True
    assert fake.queues[task_queue_key("beacon:test")]
    assert await dequeue_task(fake, "beacon:test", timeout_seconds=0.01) == payload
    assert await dequeue_task(fake, "beacon:test", timeout_seconds=0.01) is None


@pytest.mark.anyio
async def test_redis_helpers_fail_gracefully_when_unavailable():
    fake = FakeRedis(fail=True)

    assert await enqueue_task(fake, "beacon:test", {"task_id": "task-1"}) is False
    assert await dequeue_task(fake, "beacon:test", timeout_seconds=0.01) is None
    assert await publish_event(fake, "events:test", {"kind": "probe"}) is False

    result = await check_rate_limit(fake, key="ratelimit:test", limit=1, window_seconds=60)
    assert result.allowed is True
    assert result.degraded is True


@pytest.mark.anyio
async def test_pubsub_publish_receive():
    fake = FakeRedis()
    channel = operator_events_channel("operator-1")

    receiver = asyncio.create_task(receive_event(fake, channel, timeout_seconds=1))
    await asyncio.sleep(0.01)
    assert await publish_event(fake, channel, {"kind": "probe", "status": "ok"}) is True

    assert await receiver == {"kind": "probe", "status": "ok"}


@pytest.mark.anyio
async def test_session_cache_json_round_trip():
    fake = FakeRedis()
    key = session_cache_key("session-1")

    assert await cache_set_json(fake, key, {"state": "active"}, ttl_seconds=30) is True
    assert await cache_get_json(fake, key) == {"state": "active"}
    assert fake.ttls[key] == 30

    assert await cache_delete(fake, key) is True
    assert await cache_get_json(fake, key) is None


@pytest.mark.anyio
async def test_rate_limiter_blocks_after_threshold():
    fake = FakeRedis()

    first = await check_rate_limit(fake, key="ratelimit:operator:me", limit=2, window_seconds=60)
    second = await check_rate_limit(fake, key="ratelimit:operator:me", limit=2, window_seconds=60)
    third = await check_rate_limit(fake, key="ratelimit:operator:me", limit=2, window_seconds=60)

    assert first.allowed is True
    assert first.remaining == 1
    assert second.allowed is True
    assert second.remaining == 0
    assert third.allowed is False
    assert third.retry_after_seconds == 60
