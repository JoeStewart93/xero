from __future__ import annotations

import asyncio
import contextlib
import uuid
from dataclasses import dataclass
from datetime import datetime

from starlette.websockets import WebSocket, WebSocketState
from xero_common.models import utc_now

BEACON_WEBSOCKET_PROTOCOL = "xero.beacon.v1"
TOKEN_PROTOCOL_PREFIX = "bearer."
WS_CLOSE_PROTOCOL_ERROR = 4400
WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_DUPLICATE = 4409
WS_CLOSE_OVERLOADED = 1013


@dataclass(frozen=True)
class BeaconConnectionSnapshot:
    id: str
    beacon_id: uuid.UUID
    connected_at: datetime
    last_seen: datetime


class ManagedBeaconConnection:
    def __init__(self, websocket: WebSocket, beacon_id: uuid.UUID, *, queue_size: int) -> None:
        self.id = str(uuid.uuid4())
        self.beacon_id = beacon_id
        self.connected_at = utc_now()
        self.last_seen = self.connected_at
        self.websocket = websocket
        self.queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=queue_size)
        self.sender_task = asyncio.create_task(self._send_loop())

    async def enqueue(self, payload: bytes) -> bool:
        if self.queue.full():
            await self.close(code=WS_CLOSE_OVERLOADED)
            return False
        await self.queue.put(payload)
        return True

    async def close(self, *, code: int = 1000) -> None:
        if self.websocket.application_state == WebSocketState.CONNECTED:
            with contextlib.suppress(RuntimeError):
                await self.websocket.close(code=code)
        await self.cancel_sender()

    async def cancel_sender(self) -> None:
        self.sender_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, RuntimeError):
            await self.sender_task

    def touch(self) -> None:
        self.last_seen = utc_now()

    def snapshot(self) -> BeaconConnectionSnapshot:
        return BeaconConnectionSnapshot(
            id=self.id,
            beacon_id=self.beacon_id,
            connected_at=self.connected_at,
            last_seen=self.last_seen,
        )

    async def _send_loop(self) -> None:
        while True:
            payload = await self.queue.get()
            await self.websocket.send_bytes(payload)


class BeaconTransportManager:
    def __init__(self, *, queue_size: int) -> None:
        self.queue_size = queue_size
        self._connections: dict[uuid.UUID, ManagedBeaconConnection] = {}
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def register(self, websocket: WebSocket, beacon_id: uuid.UUID) -> ManagedBeaconConnection:
        connection = ManagedBeaconConnection(websocket, beacon_id, queue_size=self.queue_size)
        old_connection: ManagedBeaconConnection | None = None
        async with self._lock:
            old_connection = self._connections.get(beacon_id)
            self._connections[beacon_id] = connection
        if old_connection is not None:
            await old_connection.close(code=WS_CLOSE_DUPLICATE)
        return connection

    async def unregister(self, beacon_id: uuid.UUID, connection_id: str) -> bool:
        async with self._lock:
            connection = self._connections.get(beacon_id)
            if connection is None or connection.id != connection_id:
                return False
            self._connections.pop(beacon_id, None)
        await connection.cancel_sender()
        return True

    async def close_all(self) -> None:
        async with self._lock:
            connections = list(self._connections.values())
            self._connections.clear()
        for connection in connections:
            await connection.close()

    async def snapshots(self) -> list[BeaconConnectionSnapshot]:
        async with self._lock:
            return [connection.snapshot() for connection in self._connections.values()]


def parse_websocket_subprotocols(websocket: WebSocket) -> list[str]:
    header_value = websocket.headers.get("sec-websocket-protocol", "")
    return [part.strip() for part in header_value.split(",") if part.strip()]


def extract_beacon_websocket_token(websocket: WebSocket) -> str | None:
    protocol_token = next(
        (
            protocol.removeprefix(TOKEN_PROTOCOL_PREFIX)
            for protocol in parse_websocket_subprotocols(websocket)
            if protocol.startswith(TOKEN_PROTOCOL_PREFIX)
        ),
        None,
    )
    authorization = websocket.headers.get("authorization", "")
    scheme, _, header_token = authorization.partition(" ")
    if protocol_token:
        return protocol_token
    if scheme.lower() == "bearer" and header_token:
        return header_token
    return websocket.query_params.get("access_token")
