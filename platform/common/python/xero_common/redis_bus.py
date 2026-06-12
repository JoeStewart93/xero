from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import redis.asyncio as redis
from fastapi import Request
from redis.exceptions import RedisError

JsonObject = dict[str, Any]


class RedisSettings(Protocol):
    app_env: str
    service_name: str
    service_role: str
    redis_url: str
    redis_max_connections: int


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int
    degraded: bool = False


def create_redis_client(settings: RedisSettings) -> redis.Redis:
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        max_connections=settings.redis_max_connections,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


async def initialize_redis(app: Any, settings: RedisSettings) -> None:
    if settings.app_env.lower() == "test":
        app.state.redis_client = None
        app.state.redis_startup_status = {"status": "skipped"}
        return
    client = create_redis_client(settings)
    app.state.redis_client = client
    try:
        await client.ping()
        app.state.redis_startup_status = {"status": "healthy"}
    except RedisError as exc:
        app.state.redis_startup_status = {"status": "unhealthy", "error": str(exc)}


async def close_redis(app: Any) -> None:
    client = getattr(app.state, "redis_client", None)
    if client is not None:
        await client.aclose()
    app.state.redis_client = None


def get_redis_client(request: Request) -> redis.Redis | None:
    return getattr(request.app.state, "redis_client", None)


def task_queue_key(queue_name: str) -> str:
    return f"queue:{queue_name.strip()}"


def operator_events_channel(operator_id: object) -> str:
    return f"events:operator:{operator_id}"


def operator_events_broadcast_channel() -> str:
    return "events:operator"


def session_cache_key(session_id: object) -> str:
    return f"session:{session_id}"


def rate_limit_key(operator_id: object, route_family: str) -> str:
    sanitized_route = route_family.strip("/").replace("/", ":") or "root"
    return f"ratelimit:{operator_id}:{sanitized_route}"


def _encode_payload(payload: JsonObject) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _decode_payload(payload: str) -> JsonObject | None:
    try:
        decoded = json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


async def enqueue_task(client: redis.Redis, queue_name: str, payload: JsonObject) -> bool:
    try:
        await client.rpush(task_queue_key(queue_name), _encode_payload(payload))
        return True
    except RedisError:
        return False


async def dequeue_task(client: redis.Redis, queue_name: str, timeout_seconds: float = 1) -> JsonObject | None:
    try:
        result = await client.blpop([task_queue_key(queue_name)], timeout=timeout_seconds)
    except RedisError:
        return None
    if result is None:
        return None
    _, payload = result
    return _decode_payload(payload)


async def publish_event(client: redis.Redis, channel: str, payload: JsonObject) -> bool:
    try:
        await client.publish(channel, _encode_payload(payload))
        return True
    except RedisError:
        return False


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_operator_event(
    settings: RedisSettings,
    event_type: str,
    *,
    data: JsonObject | None = None,
    event_id: str | None = None,
    scope: JsonObject | None = None,
) -> JsonObject:
    return {
        "id": event_id or str(uuid.uuid4()),
        "version": 1,
        "type": event_type,
        "occurred_at": utc_timestamp(),
        "source": {
            "service": settings.service_name,
            "role": settings.service_role,
        },
        "scope": {
            "project_id": None,
            "beacon_id": None,
            "task_id": None,
            "session_id": None,
            **(scope or {}),
        },
        "data": data or {},
    }


async def publish_operator_event(
    client: redis.Redis | None,
    settings: RedisSettings,
    event_type: str,
    *,
    data: JsonObject | None = None,
    scope: JsonObject | None = None,
) -> JsonObject:
    event = build_operator_event(settings, event_type, data=data, scope=scope)
    if client is not None:
        await publish_event(client, operator_events_broadcast_channel(), event)
    return event


async def receive_event(client: redis.Redis, channel: str, timeout_seconds: float = 1) -> JsonObject | None:
    pubsub = client.pubsub()
    try:
        await pubsub.subscribe(channel)
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            remaining = max(0.01, deadline - asyncio.get_running_loop().time())
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=remaining)
            if message and message.get("type") == "message":
                data = message.get("data")
                return _decode_payload(data)
            await asyncio.sleep(0.01)
    except RedisError:
        return None
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except RedisError:
            pass
    return None


async def cache_set_json(
    client: redis.Redis,
    key: str,
    payload: JsonObject,
    *,
    ttl_seconds: int | None = None,
) -> bool:
    try:
        await client.set(key, _encode_payload(payload), ex=ttl_seconds)
        return True
    except RedisError:
        return False


async def cache_get_json(client: redis.Redis, key: str) -> JsonObject | None:
    try:
        payload = await client.get(key)
    except RedisError:
        return None
    if payload is None:
        return None
    return _decode_payload(payload)


async def cache_delete(client: redis.Redis, key: str) -> bool:
    try:
        await client.delete(key)
        return True
    except RedisError:
        return False


async def check_rate_limit(
    client: redis.Redis | None,
    *,
    key: str,
    limit: int,
    window_seconds: int,
) -> RateLimitResult:
    if client is None:
        return RateLimitResult(
            allowed=True,
            remaining=limit,
            retry_after_seconds=0,
            degraded=True,
        )

    try:
        count = int(await client.incr(key))
        if count == 1:
            await client.expire(key, window_seconds)
            ttl = window_seconds
        else:
            ttl = int(await client.ttl(key))
            if ttl < 0:
                await client.expire(key, window_seconds)
                ttl = window_seconds
    except RedisError:
        return RateLimitResult(
            allowed=True,
            remaining=limit,
            retry_after_seconds=0,
            degraded=True,
        )

    return RateLimitResult(
        allowed=count <= limit,
        remaining=max(0, limit - count),
        retry_after_seconds=max(1, ttl),
    )
