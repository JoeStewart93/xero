from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

import redis.asyncio as redis
from fastapi import WebSocket
from redis.exceptions import RedisError
from starlette.websockets import WebSocketDisconnect, WebSocketState
from xero_common.redis_bus import (
    JsonObject,
    build_operator_event,
    operator_events_broadcast_channel,
)
from xero_common.security import AuthTokenError, decode_c2_access_token

from xero_c2.config import Settings

WEBSOCKET_PROTOCOL = "xero.operator.v1"
TOKEN_PROTOCOL_PREFIX = "bearer."
WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_FORBIDDEN = 4403
WS_CLOSE_OVERLOADED = 1013
CLIENT_QUEUE_SIZE = 100
REDIS_RECONNECT_MAX_SECONDS = 5


@dataclass(frozen=True)
class RealtimePrincipal:
    subject: str
    token_kind: str


class ManagedOperatorConnection:
    def __init__(self, websocket: WebSocket, principal: RealtimePrincipal) -> None:
        self.id = str(uuid.uuid4())
        self.principal = principal
        self.websocket = websocket
        self.queue: asyncio.Queue[JsonObject] = asyncio.Queue(maxsize=CLIENT_QUEUE_SIZE)
        self.sender_task = asyncio.create_task(self._send_loop())

    async def enqueue(self, payload: JsonObject) -> None:
        if self.queue.full():
            await self.close(code=WS_CLOSE_OVERLOADED)
            return
        await self.queue.put(payload)

    async def close(self, *, code: int = 1000) -> None:
        if self.websocket.application_state == WebSocketState.CONNECTED:
            with contextlib.suppress(RuntimeError):
                await self.websocket.close(code=code)
        self.sender_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self.sender_task

    async def _send_loop(self) -> None:
        while True:
            payload = await self.queue.get()
            await self.websocket.send_json(payload)


class OperatorConnectionRegistry:
    def __init__(self) -> None:
        self._connections: dict[str, ManagedOperatorConnection] = {}
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def register(self, websocket: WebSocket, principal: RealtimePrincipal) -> ManagedOperatorConnection:
        connection = ManagedOperatorConnection(websocket, principal)
        async with self._lock:
            self._connections[connection.id] = connection
        return connection

    async def unregister(self, connection_id: str) -> None:
        async with self._lock:
            connection = self._connections.pop(connection_id, None)
        if connection is not None:
            connection.sender_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await connection.sender_task

    async def close_all(self) -> None:
        async with self._lock:
            connections = list(self._connections.values())
            self._connections.clear()
        for connection in connections:
            await connection.close()

    async def broadcast(self, payload: JsonObject) -> None:
        async with self._lock:
            connections = list(self._connections.values())
        for connection in connections:
            await connection.enqueue(payload)


class OperatorRealtimeHub:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.registry = OperatorConnectionRegistry()
        self.redis_client: redis.Redis | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def start(self, redis_client: redis.Redis | None) -> None:
        self.redis_client = redis_client
        if self._listener_task is not None:
            return
        self._listener_task = asyncio.create_task(self._redis_listener())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._listener_task is not None:
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task
            self._listener_task = None
        await self.registry.close_all()

    async def register(self, websocket: WebSocket, principal: RealtimePrincipal) -> ManagedOperatorConnection:
        connection = await self.registry.register(websocket, principal)
        await connection.enqueue(build_operator_event(self.settings, "realtime.connected"))
        return connection

    async def unregister(self, connection_id: str) -> None:
        await self.registry.unregister(connection_id)

    async def broadcast(self, payload: JsonObject) -> None:
        await self.registry.broadcast(payload)

    async def _redis_listener(self) -> None:
        backoff_seconds = 0.25
        degraded = False
        channel = operator_events_broadcast_channel()

        while not self._stop_event.is_set():
            pubsub = None
            try:
                if self.redis_client is None:
                    raise RedisError("redis client is unavailable")
                pubsub = self.redis_client.pubsub()
                await pubsub.subscribe(channel)
                if degraded:
                    await self.broadcast(build_operator_event(self.settings, "system.realtime.recovered"))
                    degraded = False
                backoff_seconds = 0.25
                while not self._stop_event.is_set():
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
                    if message and message.get("type") == "message":
                        payload = decode_operator_event(message.get("data"))
                        if payload is not None:
                            await self.broadcast(payload)
                    await asyncio.sleep(0.01)
            except (RedisError, OSError, RuntimeError):
                if not degraded:
                    await self.broadcast(build_operator_event(self.settings, "system.realtime.degraded"))
                    degraded = True
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(REDIS_RECONNECT_MAX_SECONDS, backoff_seconds * 2)
            finally:
                if pubsub is not None:
                    with contextlib.suppress(RedisError, RuntimeError):
                        await pubsub.unsubscribe(channel)
                        await pubsub.aclose()


def decode_operator_event(raw_payload: Any) -> JsonObject | None:
    try:
        payload = json.loads(raw_payload)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("version") != 1 or not payload.get("id") or not payload.get("type"):
        return None
    return payload


def parse_subprotocols(websocket: WebSocket) -> list[str]:
    header_value = websocket.headers.get("sec-websocket-protocol", "")
    return [part.strip() for part in header_value.split(",") if part.strip()]


def extract_websocket_token(websocket: WebSocket) -> tuple[str | None, str | None]:
    protocols = parse_subprotocols(websocket)
    protocol_token = next(
        (
            protocol.removeprefix(TOKEN_PROTOCOL_PREFIX)
            for protocol in protocols
            if protocol.startswith(TOKEN_PROTOCOL_PREFIX)
        ),
        None,
    )
    authorization = websocket.headers.get("authorization", "")
    scheme, _, header_token = authorization.partition(" ")
    query_token = websocket.query_params.get("access_token")
    accepted_protocol = WEBSOCKET_PROTOCOL if WEBSOCKET_PROTOCOL in protocols else None

    if protocol_token:
        return protocol_token, accepted_protocol
    if scheme.lower() == "bearer" and header_token:
        return header_token, accepted_protocol
    return query_token, accepted_protocol


async def close_unauthorized(websocket: WebSocket) -> None:
    await websocket.close(code=WS_CLOSE_UNAUTHORIZED)


async def close_forbidden(websocket: WebSocket) -> None:
    await websocket.close(code=WS_CLOSE_FORBIDDEN)


def websocket_origin_allowed(websocket: WebSocket, settings: Settings) -> bool:
    origin = websocket.headers.get("origin")
    return not origin or origin.rstrip("/") == settings.frontend_origin.rstrip("/")


def authenticate_websocket(websocket: WebSocket, settings: Settings) -> tuple[RealtimePrincipal, str | None] | None:
    token, accepted_protocol = extract_websocket_token(websocket)
    if not token:
        return None

    try:
        claims = decode_c2_access_token(token, settings)
    except AuthTokenError:
        return None
    return RealtimePrincipal(subject=str(claims.get("sub", "xero-ui-client")), token_kind="c2"), accepted_protocol


async def run_operator_websocket(
    websocket: WebSocket,
    *,
    hub: OperatorRealtimeHub,
    principal: RealtimePrincipal,
    accepted_protocol: str | None,
) -> None:
    await websocket.accept(subprotocol=accepted_protocol)
    connection = await hub.register(websocket, principal)
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await connection.enqueue(build_operator_event(hub.settings, "realtime.heartbeat"))
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unregister(connection.id)
