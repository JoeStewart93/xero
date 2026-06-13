from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import posixpath
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from fastapi import HTTPException, WebSocket, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect, WebSocketState
from xero_common.database import session_factory_for_settings
from xero_common.models import utc_now
from xero_common.redis_bus import publish_operator_event
from xero_common.security import AuthTokenError, decode_c2_access_token

from xero_c2.models import Beacon, InteractiveSession
from xero_c2.protocol import SESSION_DATA, ProtocolError, encode_frame, load_private_key
from xero_c2.registry_sessions import (
    REGISTRY_BEACON_OPS,
    REGISTRY_ERROR_CODES,
    REGISTRY_SESSION_OPS,
    REGISTRY_SESSION_TYPE,
    SESSION_OP_REG_DELETE_VALUE,
    SESSION_OP_REG_PREPARE_DELETE_VALUE,
    SESSION_OP_REG_PREPARE_WRITE_VALUE,
    SESSION_OP_REG_WRITE_VALUE,
    consume_registry_confirmation,
    create_registry_confirmation,
    normalize_registry_hive,
    normalize_registry_key_path,
    parse_registry_request,
    record_registry_audit_result,
    registry_frame_fields,
    registry_operator_message,
)

SESSION_WEBSOCKET_PROTOCOL = "xero.session.v1"
TOKEN_PROTOCOL_PREFIX = "bearer."
WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_NOT_FOUND = 4404
WS_CLOSE_DUPLICATE = 4409
WS_CLOSE_OVERLOADED = 1013

SESSION_STATUS_OPENING = "opening"
SESSION_STATUS_OPEN = "open"
SESSION_STATUS_DETACHED = "detached"
SESSION_STATUS_CLOSING = "closing"
SESSION_STATUS_CLOSED = "closed"
SESSION_STATUS_FAILED = "failed"
ACTIVE_SESSION_STATUSES = {
    SESSION_STATUS_OPENING,
    SESSION_STATUS_OPEN,
    SESSION_STATUS_DETACHED,
    SESSION_STATUS_CLOSING,
}

SESSION_OP_OPEN = "open"
SESSION_OP_OPEN_ACK = "open_ack"
SESSION_OP_STDIN = "stdin"
SESSION_OP_STDOUT = "stdout"
SESSION_OP_STDERR = "stderr"
SESSION_OP_RESIZE = "resize"
SESSION_OP_CLOSE = "close"
SESSION_OP_EXIT = "exit"
SESSION_OP_ERROR = "error"
SESSION_OP_LIST_DIR = "list_dir"
SESSION_OP_STAT = "stat"
SESSION_OP_READ_FILE = "read_file"
SESSION_DATA_OPS = {
    SESSION_OP_OPEN,
    SESSION_OP_OPEN_ACK,
    SESSION_OP_STDIN,
    SESSION_OP_STDOUT,
    SESSION_OP_STDERR,
    SESSION_OP_RESIZE,
    SESSION_OP_CLOSE,
    SESSION_OP_EXIT,
    SESSION_OP_ERROR,
    SESSION_OP_LIST_DIR,
    SESSION_OP_STAT,
    SESSION_OP_READ_FILE,
    *REGISTRY_BEACON_OPS,
}

FILE_BROWSER_SESSION_TYPE = "file_browser"
SHELL_SESSION_TYPE = "shell"
FILE_BROWSER_OPS = {SESSION_OP_LIST_DIR, SESSION_OP_STAT, SESSION_OP_READ_FILE}
SESSION_ERROR_CODES = {
    "access_denied",
    "binary_file",
    "not_found",
    "path_invalid",
    "unsupported_operation",
    *REGISTRY_ERROR_CODES,
}


class DuplicateSessionAttachError(RuntimeError):
    pass


@dataclass(frozen=True)
class SessionDataOutcome:
    session_id: uuid.UUID
    session_payload: dict[str, Any]
    operator_message: dict[str, Any] | None
    event_type: str | None
    cache_listing: dict[str, Any] | None = None


class FileListingCache:
    def __init__(self, *, ttl_seconds: float = 5.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[tuple[uuid.UUID, str], tuple[float, dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def get(self, session_id: uuid.UUID, path: str, *, request_id: str) -> dict[str, Any] | None:
        key = (session_id, normalize_file_browser_path(path))
        async with self._lock:
            cached = self._items.get(key)
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= time.monotonic():
                self._items.pop(key, None)
                return None
            response = dict(payload)
        response["request_id"] = request_id
        response["cached"] = True
        return response

    async def store(self, session_id: uuid.UUID, payload: dict[str, Any]) -> None:
        if payload.get("op") != SESSION_OP_LIST_DIR or payload.get("ok") is not True:
            return
        path = normalize_file_browser_path(str(payload.get("path") or ""))
        key = (session_id, path)
        cached = dict(payload)
        cached["path"] = path
        cached["cached"] = False
        async with self._lock:
            self._items[key] = (time.monotonic() + self.ttl_seconds, cached)

    async def clear_session(self, session_id: uuid.UUID) -> None:
        async with self._lock:
            for key in list(self._items):
                if key[0] == session_id:
                    self._items.pop(key, None)


class ManagedSessionConnection:
    def __init__(self, websocket: WebSocket, session_id: uuid.UUID, *, queue_size: int) -> None:
        self.id = str(uuid.uuid4())
        self.websocket = websocket
        self.session_id = session_id
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=queue_size)
        self.sender_task = asyncio.create_task(self._send_loop())

    async def enqueue(self, payload: dict[str, Any]) -> None:
        if self.queue.full():
            await self.close(code=WS_CLOSE_OVERLOADED)
            return
        await self.queue.put(payload)

    async def close(self, *, code: int = 1000) -> None:
        if self.websocket.application_state == WebSocketState.CONNECTED:
            with contextlib.suppress(RuntimeError):
                await self.websocket.close(code=code)
        await self.cancel_sender()

    async def cancel_sender(self) -> None:
        self.sender_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, RuntimeError):
            await self.sender_task

    async def _send_loop(self) -> None:
        while True:
            payload = await self.queue.get()
            await self.websocket.send_json(payload)


class SessionRelayManager:
    def __init__(self, *, queue_size: int) -> None:
        self.queue_size = queue_size
        self._connections: dict[uuid.UUID, ManagedSessionConnection] = {}
        self._lock = asyncio.Lock()

    async def register(self, websocket: WebSocket, session_id: uuid.UUID) -> ManagedSessionConnection:
        connection = ManagedSessionConnection(websocket, session_id, queue_size=self.queue_size)
        async with self._lock:
            if session_id in self._connections:
                await connection.close(code=WS_CLOSE_DUPLICATE)
                raise DuplicateSessionAttachError("Session already has an attached operator")
            self._connections[session_id] = connection
        return connection

    async def unregister(self, session_id: uuid.UUID, connection_id: str) -> bool:
        async with self._lock:
            connection = self._connections.get(session_id)
            if connection is None or connection.id != connection_id:
                return False
            self._connections.pop(session_id, None)
        await connection.cancel_sender()
        return True

    async def deliver(self, session_id: uuid.UUID, payload: dict[str, Any]) -> bool:
        async with self._lock:
            connection = self._connections.get(session_id)
        if connection is None:
            return False
        await connection.enqueue(payload)
        return True

    async def close_all(self) -> None:
        async with self._lock:
            connections = list(self._connections.values())
            self._connections.clear()
        for connection in connections:
            await connection.close()


def parse_websocket_subprotocols(websocket: WebSocket) -> list[str]:
    header_value = websocket.headers.get("sec-websocket-protocol", "")
    return [part.strip() for part in header_value.split(",") if part.strip()]


def authenticate_session_websocket(websocket: WebSocket, settings) -> tuple[str, str | None] | None:
    protocols = parse_websocket_subprotocols(websocket)
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
    token = protocol_token or (header_token if scheme.lower() == "bearer" else None) or query_token
    if not token:
        return None
    try:
        claims = decode_c2_access_token(token, settings)
    except AuthTokenError:
        return None
    accepted_protocol = SESSION_WEBSOCKET_PROTOCOL if SESSION_WEBSOCKET_PROTOCOL in protocols else None
    subject = claims.get("operator_id") or claims.get("sub") or "xero-ui-client"
    return str(subject), accepted_protocol


def public_session(shell_session: InteractiveSession) -> dict[str, Any]:
    return {
        "id": str(shell_session.id),
        "beacon_id": str(shell_session.beacon_id),
        "session_type": shell_session.session_type,
        "shell_type": shell_session.shell_type,
        "status": shell_session.status,
        "actor_subject": shell_session.actor_subject,
        "opened_at": shell_session.opened_at.isoformat(),
        "last_activity_at": shell_session.last_activity_at.isoformat(),
        "detached_at": shell_session.detached_at.isoformat() if shell_session.detached_at else None,
        "closed_at": shell_session.closed_at.isoformat() if shell_session.closed_at else None,
        "close_reason": shell_session.close_reason,
        "rows": shell_session.rows,
        "cols": shell_session.cols,
        "created_at": shell_session.created_at.isoformat(),
        "updated_at": shell_session.updated_at.isoformat(),
    }


def public_shell_session(shell_session: InteractiveSession) -> dict[str, Any]:
    return public_session(shell_session)


def resolve_shell_type(beacon: Beacon, requested: str) -> str:
    if requested != "auto":
        return requested
    if "windows" in beacon.os.lower():
        return "powershell"
    return "bash"


def create_shell_session(
    session: Session,
    *,
    beacon: Beacon,
    actor_subject: str,
    shell_type: str,
    rows: int,
    cols: int,
) -> InteractiveSession:
    now = utc_now()
    shell_session = InteractiveSession(
        beacon_id=beacon.id,
        session_type="shell",
        shell_type=resolve_shell_type(beacon, shell_type),
        status=SESSION_STATUS_OPENING,
        actor_subject=actor_subject,
        opened_at=now,
        last_activity_at=now,
        rows=rows,
        cols=cols,
    )
    session.add(shell_session)
    session.flush()
    return shell_session


def create_file_browser_session(
    session: Session,
    *,
    beacon: Beacon,
    actor_subject: str,
) -> InteractiveSession:
    now = utc_now()
    file_session = InteractiveSession(
        beacon_id=beacon.id,
        session_type=FILE_BROWSER_SESSION_TYPE,
        shell_type="none",
        status=SESSION_STATUS_OPENING,
        actor_subject=actor_subject,
        opened_at=now,
        last_activity_at=now,
        rows=32,
        cols=120,
    )
    session.add(file_session)
    session.flush()
    return file_session


def create_registry_session(
    session: Session,
    *,
    beacon: Beacon,
    actor_subject: str,
) -> InteractiveSession:
    now = utc_now()
    registry_session = InteractiveSession(
        beacon_id=beacon.id,
        session_type=REGISTRY_SESSION_TYPE,
        shell_type="none",
        status=SESSION_STATUS_OPENING,
        actor_subject=actor_subject,
        opened_at=now,
        last_activity_at=now,
        rows=32,
        cols=120,
    )
    session.add(registry_session)
    session.flush()
    return registry_session


def mark_shell_session_open(session: InteractiveSession) -> InteractiveSession:
    session.status = SESSION_STATUS_OPEN
    session.detached_at = None
    session.last_activity_at = utc_now()
    return session


def mark_shell_session_detached(session: InteractiveSession) -> InteractiveSession:
    if session.status in {SESSION_STATUS_CLOSED, SESSION_STATUS_FAILED}:
        return session
    session.status = SESSION_STATUS_DETACHED
    session.detached_at = utc_now()
    session.last_activity_at = session.detached_at
    return session


def close_shell_session(session: InteractiveSession, *, reason: str) -> InteractiveSession:
    now = utc_now()
    session.status = SESSION_STATUS_CLOSED
    session.closed_at = now
    session.last_activity_at = now
    session.close_reason = reason
    return session


def fail_shell_session(session: InteractiveSession, *, reason: str) -> InteractiveSession:
    now = utc_now()
    session.status = SESSION_STATUS_FAILED
    session.closed_at = now
    session.last_activity_at = now
    session.close_reason = reason
    return session


def terminal_data_b64(data: str | bytes) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return base64.b64encode(raw).decode("ascii")


def terminal_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("data"), str):
        return str(payload["data"])
    raw = payload.get("data_b64")
    if not isinstance(raw, str):
        return ""
    try:
        return base64.b64decode(raw.encode("ascii"), validate=True).decode("utf-8", errors="replace")
    except (ValueError, UnicodeEncodeError):
        return ""


def normalize_file_browser_path(path: str | None) -> str:
    raw = (path or "").replace("\\", "/").strip()
    if not raw or raw == ".":
        return ""
    if raw.startswith("/") or ":" in raw:
        raise ValueError("File browser path must be relative to the session root")
    normalized = posixpath.normpath(raw)
    if normalized in {"", "."}:
        return ""
    parts = [part for part in normalized.split("/") if part]
    if any(part == ".." for part in parts) or normalized.startswith("../"):
        raise ValueError("File browser path cannot traverse above the session root")
    return "/".join(parts)


def parse_file_browser_request(raw_message: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError as exc:
        raise ValueError("File browser message must be JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("File browser message must be a JSON object")
    op = payload.get("op")
    if op not in {SESSION_OP_LIST_DIR, SESSION_OP_STAT, SESSION_OP_READ_FILE, SESSION_OP_CLOSE, "ping"}:
        raise ValueError("File browser message op is invalid")
    if op == "ping":
        return {"op": "ping"}
    if op == SESSION_OP_CLOSE:
        return {"op": SESSION_OP_CLOSE}
    request_id = payload.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("File browser request_id is required")
    path = normalize_file_browser_path(str(payload.get("path") or ""))
    return {
        "op": op,
        "path": path,
        "refresh": bool(payload.get("refresh")),
        "request_id": request_id.strip(),
    }


def validate_session_data_payload(payload: dict[str, Any]) -> None:
    raw_session_id = payload.get("session_id")
    if not isinstance(raw_session_id, str):
        raise ProtocolError("INVALID_PAYLOAD", "SESSION_DATA session_id is required")
    try:
        uuid.UUID(raw_session_id)
    except ValueError as exc:
        raise ProtocolError("INVALID_PAYLOAD", "SESSION_DATA session_id must be a UUID") from exc
    op = payload.get("op")
    if not isinstance(op, str) or op not in SESSION_DATA_OPS:
        raise ProtocolError("INVALID_PAYLOAD", "SESSION_DATA op is invalid")
    session_type = payload.get("session_type")
    if session_type is not None and session_type not in {
        FILE_BROWSER_SESSION_TYPE,
        REGISTRY_SESSION_TYPE,
        SHELL_SESSION_TYPE,
    }:
        raise ProtocolError("INVALID_PAYLOAD", "SESSION_DATA session_type is invalid")
    request_id = payload.get("request_id")
    if request_id is not None and (not isinstance(request_id, str) or not request_id.strip()):
        raise ProtocolError("INVALID_PAYLOAD", "SESSION_DATA request_id is invalid")
    path = payload.get("path")
    if path is not None:
        if not isinstance(path, str):
            raise ProtocolError("INVALID_PAYLOAD", "SESSION_DATA path must be a string")
        try:
            normalize_file_browser_path(path)
        except ValueError as exc:
            raise ProtocolError("INVALID_PAYLOAD", str(exc)) from exc
    if op in REGISTRY_BEACON_OPS:
        if session_type != REGISTRY_SESSION_TYPE:
            raise ProtocolError("INVALID_PAYLOAD", "Registry SESSION_DATA requires registry session_type")
        try:
            normalize_registry_hive(payload.get("hive"))
            normalize_registry_key_path(payload.get("key_path"))
        except ValueError as exc:
            raise ProtocolError("INVALID_PAYLOAD", str(exc)) from exc
    error_code = payload.get("error_code")
    if error_code is not None and error_code not in SESSION_ERROR_CODES:
        raise ProtocolError("INVALID_PAYLOAD", "SESSION_DATA error_code is invalid")
    data_b64 = payload.get("data_b64")
    if data_b64 is not None:
        if not isinstance(data_b64, str):
            raise ProtocolError("INVALID_PAYLOAD", "SESSION_DATA data_b64 must be a string")
        try:
            base64.b64decode(data_b64.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError) as exc:
            raise ProtocolError("INVALID_PAYLOAD", "SESSION_DATA data_b64 is invalid") from exc
    cols = payload.get("cols")
    rows = payload.get("rows")
    if cols is not None and (not isinstance(cols, int) or cols < 20 or cols > 300):
        raise ProtocolError("INVALID_PAYLOAD", "SESSION_DATA cols is invalid")
    if rows is not None and (not isinstance(rows, int) or rows < 5 or rows > 80):
        raise ProtocolError("INVALID_PAYLOAD", "SESSION_DATA rows is invalid")


def session_frame_payload(shell_session: InteractiveSession, op: str, **fields: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "beacon_id": str(shell_session.beacon_id),
        "session_id": str(shell_session.id),
        "op": op,
    }
    payload.update({key: value for key, value in fields.items() if value is not None})
    return payload


def encode_session_data_frame(settings, beacon: Beacon, payload: dict[str, Any]) -> bytes:
    if not beacon.protocol_session_id or not beacon.protocol_peer_public_key_b64:
        raise ProtocolError("PROTOCOL_METADATA_REQUIRED", "Beacon protocol metadata is required for session delivery")
    try:
        protocol_session_id = uuid.UUID(beacon.protocol_session_id)
        peer_public_key = base64.b64decode(beacon.protocol_peer_public_key_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise ProtocolError("PROTOCOL_METADATA_INVALID", "Beacon protocol metadata is invalid") from exc
    private_key = load_private_key(settings.protocol_private_key_b64)
    return encode_frame(
        private_key=private_key,
        peer_public_key=peer_public_key,
        message_type=SESSION_DATA,
        payload=payload,
        session_id=protocol_session_id,
        max_frame_bytes=settings.protocol_max_frame_bytes,
    )


async def enqueue_session_data_frame(
    app,
    settings,
    db: Session,
    shell_session: InteractiveSession,
    payload: dict[str, Any],
) -> None:
    beacon = db.get(Beacon, shell_session.beacon_id)
    if beacon is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")
    try:
        frame = encode_session_data_frame(settings, beacon, payload)
    except ProtocolError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    sent = await app.state.beacon_transport_manager.send_to_beacon(shell_session.beacon_id, frame)
    if not sent:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Beacon WebSocket transport is not connected")


def apply_beacon_session_data(
    session: Session,
    *,
    beacon_id: uuid.UUID,
    payload: dict[str, Any],
) -> SessionDataOutcome:
    validate_session_data_payload(payload)
    shell_session_id = uuid.UUID(str(payload["session_id"]))
    shell_session = session.get(InteractiveSession, shell_session_id)
    if shell_session is None:
        raise ProtocolError("UNKNOWN_SESSION", "SESSION_DATA references an unknown session")
    if shell_session.beacon_id != beacon_id:
        raise ProtocolError("SESSION_BEACON_MISMATCH", "SESSION_DATA session_id does not belong to the beacon")

    op = str(payload["op"])
    now = utc_now()
    shell_session.last_activity_at = now
    operator_message: dict[str, Any] | None = None
    event_type: str | None = None

    if op == SESSION_OP_OPEN_ACK:
        mark_shell_session_open(shell_session)
        event_type = "session.opened"
        operator_message = {
            "op": "opened",
            "root_path": payload.get("root_path"),
            "session": public_session(shell_session),
        }
    elif op in {SESSION_OP_STDOUT, SESSION_OP_STDERR}:
        if shell_session.session_type != SHELL_SESSION_TYPE:
            raise ProtocolError("INVALID_SESSION_OP", "Terminal output is only valid for shell sessions")
        if shell_session.status in {SESSION_STATUS_OPENING, SESSION_STATUS_DETACHED}:
            shell_session.status = SESSION_STATUS_OPEN
            shell_session.detached_at = None
        operator_message = {
            "op": op,
            "session_id": str(shell_session.id),
            "stream": op.removeprefix("std"),
            "data": terminal_text(payload),
            "data_b64": payload.get("data_b64"),
        }
        event_type = "session.output.received"
    elif op in FILE_BROWSER_OPS:
        if shell_session.session_type != FILE_BROWSER_SESSION_TYPE:
            raise ProtocolError("INVALID_SESSION_OP", "File browser op is only valid for file browser sessions")
        if shell_session.status in {SESSION_STATUS_OPENING, SESSION_STATUS_DETACHED}:
            shell_session.status = SESSION_STATUS_OPEN
            shell_session.detached_at = None
        path = normalize_file_browser_path(str(payload.get("path") or ""))
        operator_message = {
            "cached": False,
            "entries": payload.get("entries", []),
            "error_code": payload.get("error_code"),
            "message": payload.get("message"),
            "modified_at": payload.get("modified_at"),
            "ok": payload.get("ok", True),
            "op": op,
            "path": path,
            "permissions": payload.get("permissions"),
            "request_id": payload.get("request_id"),
            "session_id": str(shell_session.id),
            "size": payload.get("size"),
            "truncated": payload.get("truncated", False),
            "type": payload.get("type"),
            "content": payload.get("content"),
            "encoding": payload.get("encoding"),
        }
        event_type = "session.file.response.received" if operator_message["ok"] else "session.file.error"
    elif op in REGISTRY_BEACON_OPS:
        if shell_session.session_type != REGISTRY_SESSION_TYPE:
            raise ProtocolError("INVALID_SESSION_OP", "Registry op is only valid for registry sessions")
        if shell_session.status in {SESSION_STATUS_OPENING, SESSION_STATUS_DETACHED}:
            shell_session.status = SESSION_STATUS_OPEN
            shell_session.detached_at = None
        operator_message = registry_operator_message(payload, shell_session.id)
        record_registry_audit_result(session, shell_session, payload)
        event_type = (
            "session.registry.response.received"
            if operator_message.get("ok") is not False
            else "session.registry.error"
        )
    elif op == SESSION_OP_EXIT:
        close_shell_session(shell_session, reason=str(payload.get("reason") or "process_exit"))
        operator_message = {"op": "closed", "session": public_session(shell_session)}
        event_type = "session.closed"
    elif op == SESSION_OP_ERROR:
        if shell_session.session_type == FILE_BROWSER_SESSION_TYPE and payload.get("request_id"):
            operator_message = {
                "error_code": payload.get("error_code") or "unsupported_operation",
                "message": str(payload.get("message") or payload.get("reason") or "File browser operation failed."),
                "ok": False,
                "op": "error",
                "path": normalize_file_browser_path(str(payload.get("path") or "")),
                "request_id": payload.get("request_id"),
                "session_id": str(shell_session.id),
            }
            event_type = "session.file.error"
        elif shell_session.session_type == REGISTRY_SESSION_TYPE and payload.get("request_id"):
            operator_message = {
                "error_code": payload.get("error_code") or "unsupported_operation",
                "hive": payload.get("hive"),
                "key_path": normalize_registry_key_path(payload.get("key_path")),
                "message": str(payload.get("message") or payload.get("reason") or "Registry operation failed."),
                "ok": False,
                "op": "error",
                "request_id": payload.get("request_id"),
                "session_id": str(shell_session.id),
                "value_name": payload.get("value_name"),
            }
            event_type = "session.registry.error"
        else:
            fail_shell_session(
                shell_session,
                reason=str(payload.get("reason") or payload.get("message") or "beacon_error"),
            )
            operator_message = {
                "op": "error",
                "session": public_session(shell_session),
                "message": shell_session.close_reason,
            }
            event_type = "session.failed"
    elif op == SESSION_OP_CLOSE:
        close_shell_session(shell_session, reason=str(payload.get("reason") or "beacon_closed"))
        operator_message = {"op": "closed", "session": public_session(shell_session)}
        event_type = "session.closed"
    else:
        operator_message = {"op": "ack", "session": public_session(shell_session)}

    session.add(shell_session)
    return SessionDataOutcome(
        session_id=shell_session.id,
        session_payload=public_session(shell_session),
        operator_message=operator_message,
        event_type=event_type,
        cache_listing=operator_message if op == SESSION_OP_LIST_DIR and operator_message is not None else None,
    )


def expire_idle_sessions(session: Session, settings, *, now=None) -> list[InteractiveSession]:
    current = now or utc_now()
    idle_cutoff = current - timedelta(seconds=settings.session_idle_timeout_seconds)
    detached_cutoff = current - timedelta(seconds=settings.session_detach_grace_seconds)
    candidates = (
        session.execute(
            select(InteractiveSession).where(
                InteractiveSession.status.in_(ACTIVE_SESSION_STATUSES),
            )
        )
        .scalars()
        .all()
    )
    expired: list[InteractiveSession] = []
    for shell_session in candidates:
        if shell_session.status == SESSION_STATUS_DETACHED and shell_session.detached_at:
            should_close = shell_session.detached_at <= detached_cutoff
            reason = "operator_disconnected"
        else:
            should_close = shell_session.last_activity_at <= idle_cutoff
            reason = "idle_timeout"
        if should_close:
            close_shell_session(shell_session, reason=reason)
            session.add(shell_session)
            expired.append(shell_session)
    return expired


async def publish_session_event(app, settings, event_type: str, shell_session: InteractiveSession) -> None:
    await publish_session_payload_event(app, settings, event_type, public_shell_session(shell_session))


async def publish_session_payload_event(app, settings, event_type: str, session_payload: dict[str, Any]) -> None:
    redis_client = getattr(app.state, "redis_client", None)
    event = await publish_operator_event(
        redis_client,
        settings,
        event_type,
        data={"session": session_payload},
        scope={"beacon_id": session_payload["beacon_id"], "session_id": session_payload["id"]},
    )
    if redis_client is None:
        await app.state.operator_realtime_hub.broadcast(event)


async def close_detached_after_grace(app, settings, session_id: uuid.UUID) -> None:
    await asyncio.sleep(settings.session_detach_grace_seconds)
    SessionFactory = session_factory_for_settings(settings)
    shell_session: InteractiveSession | None = None
    with SessionFactory() as db:
        shell_session = db.get(InteractiveSession, session_id)
        if shell_session is None or shell_session.status != SESSION_STATUS_DETACHED:
            return
        close_payload = session_frame_payload(shell_session, SESSION_OP_CLOSE, reason="operator_disconnected")
        with contextlib.suppress(HTTPException):
            await enqueue_session_data_frame(app, settings, db, shell_session, close_payload)
        close_shell_session(shell_session, reason="operator_disconnected")
        db.add(shell_session)
        db.commit()
        db.refresh(shell_session)
    await publish_session_event(app, settings, "session.closed", shell_session)


async def run_session_cleanup_monitor(app, settings) -> None:
    while True:
        await asyncio.sleep(settings.session_cleanup_interval_seconds)
        SessionFactory = session_factory_for_settings(settings)
        expired: list[InteractiveSession] = []
        with SessionFactory() as db:
            expired = expire_idle_sessions(db, settings)
            for shell_session in expired:
                close_payload = session_frame_payload(
                    shell_session,
                    SESSION_OP_CLOSE,
                    reason=shell_session.close_reason,
                )
                with contextlib.suppress(HTTPException):
                    await enqueue_session_data_frame(app, settings, db, shell_session, close_payload)
            db.commit()
            for shell_session in expired:
                db.refresh(shell_session)
        for shell_session in expired:
            await app.state.session_relay_manager.deliver(
                shell_session.id,
                {"op": "closed", "session": public_shell_session(shell_session)},
            )
            await publish_session_event(app, settings, "session.closed", shell_session)


def parse_operator_terminal_message(raw_message: str, max_chunk_bytes: int) -> dict[str, Any]:
    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError as exc:
        raise ValueError("Terminal message must be JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Terminal message must be a JSON object")
    op = payload.get("op")
    if op not in {SESSION_OP_STDIN, SESSION_OP_RESIZE, SESSION_OP_CLOSE, "ping"}:
        raise ValueError("Terminal message op is invalid")
    if op == SESSION_OP_STDIN:
        data = payload.get("data")
        data_b64 = payload.get("data_b64")
        if isinstance(data, str):
            raw = data.encode("utf-8")
            if len(raw) > max_chunk_bytes:
                raise ValueError("Terminal input chunk is too large")
            payload["data_b64"] = terminal_data_b64(raw)
        elif isinstance(data_b64, str):
            raw = base64.b64decode(data_b64.encode("ascii"), validate=True)
            if len(raw) > max_chunk_bytes:
                raise ValueError("Terminal input chunk is too large")
        else:
            raise ValueError("Terminal input requires data")
    return payload


async def run_shell_session_websocket(websocket: WebSocket, *, settings, session_id: uuid.UUID) -> None:
    authenticated = authenticate_session_websocket(websocket, settings)
    if authenticated is None:
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return
    actor_subject, accepted_protocol = authenticated
    await websocket.accept(subprotocol=accepted_protocol)

    SessionFactory = session_factory_for_settings(settings)
    with SessionFactory() as db:
        shell_session = db.get(InteractiveSession, session_id)
        if shell_session is None:
            await websocket.close(code=WS_CLOSE_NOT_FOUND)
            return
        if shell_session.actor_subject != actor_subject or shell_session.status in {
            SESSION_STATUS_CLOSED,
            SESSION_STATUS_FAILED,
        }:
            await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
            return
        session_type = shell_session.session_type
        shell_session.detached_at = None
        if shell_session.status == SESSION_STATUS_DETACHED:
            shell_session.status = SESSION_STATUS_OPEN
        shell_session.last_activity_at = utc_now()
        db.add(shell_session)
        db.commit()
        db.refresh(shell_session)
        attach_message = {"op": "attached", "session": public_session(shell_session)}

    manager: SessionRelayManager = websocket.app.state.session_relay_manager
    try:
        connection = await manager.register(websocket, session_id)
    except DuplicateSessionAttachError:
        await websocket.close(code=WS_CLOSE_DUPLICATE)
        return

    await connection.enqueue(attach_message)
    try:
        while True:
            raw_message = await websocket.receive_text()
            try:
                if session_type == FILE_BROWSER_SESSION_TYPE:
                    message = parse_file_browser_request(raw_message)
                elif session_type == REGISTRY_SESSION_TYPE:
                    message = parse_registry_request(raw_message)
                else:
                    message = parse_operator_terminal_message(raw_message, settings.session_max_chunk_bytes)
            except (ValueError, UnicodeEncodeError) as exc:
                await connection.enqueue({"op": "error", "message": str(exc)})
                continue

            if message["op"] == "ping":
                await connection.enqueue({"op": "pong"})
                continue

            with SessionFactory() as db:
                shell_session = db.get(InteractiveSession, session_id)
                if shell_session is None or shell_session.status in {SESSION_STATUS_CLOSED, SESSION_STATUS_FAILED}:
                    await connection.enqueue({"op": "closed"})
                    break
                if shell_session.actor_subject != actor_subject:
                    await connection.close(code=WS_CLOSE_UNAUTHORIZED)
                    break
                if session_type == FILE_BROWSER_SESSION_TYPE and message["op"] == SESSION_OP_LIST_DIR:
                    shell_session.last_activity_at = utc_now()
                    db.add(shell_session)
                    db.commit()
                    if not message.get("refresh"):
                        cached = await websocket.app.state.session_file_cache.get(
                            session_id,
                            message["path"],
                            request_id=message["request_id"],
                        )
                        if cached is not None:
                            await connection.enqueue(cached)
                            continue
                    frame_payload = session_frame_payload(
                        shell_session,
                        SESSION_OP_LIST_DIR,
                        path=message["path"],
                        request_id=message["request_id"],
                        session_type=FILE_BROWSER_SESSION_TYPE,
                    )
                    await enqueue_session_data_frame(websocket.app, settings, db, shell_session, frame_payload)
                    continue
                if session_type == REGISTRY_SESSION_TYPE and message["op"] != SESSION_OP_CLOSE:
                    if message["op"] in {
                        SESSION_OP_REG_PREPARE_WRITE_VALUE,
                        SESSION_OP_REG_PREPARE_DELETE_VALUE,
                    }:
                        shell_session.last_activity_at = utc_now()
                        db.add(shell_session)
                        confirm_payload = create_registry_confirmation(
                            db,
                            actor_subject=actor_subject,
                            registry_session=shell_session,
                            request=message,
                            ttl_seconds=settings.registry_confirm_token_ttl_seconds,
                        )
                        db.commit()
                        await connection.enqueue(confirm_payload)
                        continue
                    if message["op"] in {SESSION_OP_REG_WRITE_VALUE, SESSION_OP_REG_DELETE_VALUE}:
                        try:
                            consume_registry_confirmation(
                                db,
                                actor_subject=actor_subject,
                                registry_session=shell_session,
                                request=message,
                            )
                        except ValueError as exc:
                            await connection.enqueue(
                                {
                                    "error_code": "confirm_token_invalid",
                                    "message": str(exc),
                                    "ok": False,
                                    "op": "error",
                                    "request_id": message["request_id"],
                                    "session_id": str(shell_session.id),
                                }
                            )
                            continue
                    if message["op"] in REGISTRY_SESSION_OPS:
                        frame_payload = session_frame_payload(
                            shell_session,
                            message["op"],
                            **registry_frame_fields(message),
                        )
                    else:
                        await connection.enqueue({"op": "error", "message": "Registry message op is invalid"})
                        continue
                elif session_type == FILE_BROWSER_SESSION_TYPE and message["op"] in {
                    SESSION_OP_STAT,
                    SESSION_OP_READ_FILE,
                }:
                    frame_payload = session_frame_payload(
                        shell_session,
                        message["op"],
                        path=message["path"],
                        request_id=message["request_id"],
                        session_type=FILE_BROWSER_SESSION_TYPE,
                    )
                elif message["op"] == SESSION_OP_RESIZE:
                    cols = int(message.get("cols", shell_session.cols))
                    rows = int(message.get("rows", shell_session.rows))
                    if cols < 20 or cols > 300 or rows < 5 or rows > 80:
                        await connection.enqueue({"op": "error", "message": "Terminal resize is out of range"})
                        continue
                    shell_session.cols = cols
                    shell_session.rows = rows
                    frame_payload = session_frame_payload(shell_session, SESSION_OP_RESIZE, cols=cols, rows=rows)
                elif message["op"] == SESSION_OP_CLOSE:
                    shell_session.status = SESSION_STATUS_CLOSING
                    frame_payload = session_frame_payload(
                        shell_session,
                        SESSION_OP_CLOSE,
                        reason="operator",
                        session_type=session_type,
                    )
                else:
                    frame_payload = session_frame_payload(shell_session, SESSION_OP_STDIN, data_b64=message["data_b64"])
                shell_session.last_activity_at = utc_now()
                db.add(shell_session)
                await enqueue_session_data_frame(websocket.app, settings, db, shell_session, frame_payload)
                if message["op"] == SESSION_OP_CLOSE:
                    close_shell_session(shell_session, reason="operator")
                    await websocket.app.state.session_file_cache.clear_session(session_id)
                    await connection.enqueue({"op": "closed", "session": public_session(shell_session)})
                db.commit()
                db.refresh(shell_session)
                if message["op"] == SESSION_OP_CLOSE:
                    await publish_session_event(websocket.app, settings, "session.closed", shell_session)
                    break
    except WebSocketDisconnect:
        pass
    finally:
        removed = await manager.unregister(session_id, connection.id)
        if removed:
            with SessionFactory() as db:
                shell_session = db.get(InteractiveSession, session_id)
                if shell_session is not None and shell_session.status in {SESSION_STATUS_OPENING, SESSION_STATUS_OPEN}:
                    mark_shell_session_detached(shell_session)
                    db.add(shell_session)
                    db.commit()
                    db.refresh(shell_session)
                    await publish_session_event(websocket.app, settings, "session.detached", shell_session)
                    asyncio.create_task(close_detached_after_grace(websocket.app, settings, session_id))
