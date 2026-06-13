from __future__ import annotations

import base64
import binascii
import hashlib
import math
import posixpath
import re
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from xero_common.models import utc_now

from xero_c2.artifacts import artifact_store_for_settings, normalize_object_key, put_artifact, read_artifact
from xero_c2.models import Artifact, FileTransfer, FileTransferChunk, InteractiveSession

DIRECTION_UPLOAD = "upload"
DIRECTION_DOWNLOAD = "download"

TRANSFER_STATUS_STAGED = "staged"
TRANSFER_STATUS_TRANSFERRING = "transferring"
TRANSFER_STATUS_COMPLETED = "completed"
TRANSFER_STATUS_FAILED = "failed"

SESSION_OP_UPLOAD_START = "upload_start"
SESSION_OP_UPLOAD_CHUNK = "upload_chunk"
SESSION_OP_UPLOAD_COMPLETE = "upload_complete"
SESSION_OP_DOWNLOAD_INIT = "download_init"
SESSION_OP_DOWNLOAD_CHUNK_REQUEST = "download_chunk_request"

SESSION_OP_UPLOAD_INIT = "upload_init"
SESSION_OP_UPLOAD_READY = "upload_ready"
SESSION_OP_UPLOAD_ACK = "upload_ack"
SESSION_OP_UPLOAD_NACK = "upload_nack"
SESSION_OP_DOWNLOAD_READY = "download_ready"
SESSION_OP_DOWNLOAD_CHUNK = "download_chunk"
SESSION_OP_DOWNLOAD_COMPLETE = "download_complete"
SESSION_OP_TRANSFER_ERROR = "transfer_error"

FILE_TRANSFER_OPERATOR_OPS = {
    SESSION_OP_UPLOAD_START,
    SESSION_OP_UPLOAD_CHUNK,
    SESSION_OP_UPLOAD_COMPLETE,
    SESSION_OP_DOWNLOAD_INIT,
    SESSION_OP_DOWNLOAD_CHUNK_REQUEST,
}
FILE_TRANSFER_BEACON_OPS = {
    SESSION_OP_UPLOAD_READY,
    SESSION_OP_UPLOAD_ACK,
    SESSION_OP_UPLOAD_NACK,
    SESSION_OP_UPLOAD_COMPLETE,
    SESSION_OP_DOWNLOAD_READY,
    SESSION_OP_DOWNLOAD_CHUNK,
    SESSION_OP_DOWNLOAD_COMPLETE,
    SESSION_OP_TRANSFER_ERROR,
}
FILE_TRANSFER_SESSION_OPS = FILE_TRANSFER_OPERATOR_OPS | FILE_TRANSFER_BEACON_OPS | {SESSION_OP_UPLOAD_INIT}

SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")


class FileTransferError(ValueError):
    pass


def normalize_transfer_path(path: str | None) -> str:
    raw = (path or "").replace("\\", "/").strip()
    if not raw or raw == ".":
        return ""
    if raw.startswith("/") or ":" in raw:
        raise FileTransferError("File transfer path must be relative to the session root")
    normalized = posixpath.normpath(raw)
    if normalized in {"", "."}:
        return ""
    parts = [part for part in normalized.split("/") if part]
    if any(part == ".." for part in parts) or normalized.startswith("../"):
        raise FileTransferError("File transfer path cannot traverse above the session root")
    return "/".join(parts)


def validate_sha256(value: str | None, *, field_name: str = "sha256", required: bool = True) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not SHA256_RE.match(value):
        raise FileTransferError(f"{field_name} must be a SHA-256 hex digest")
    return value.lower()


def transfer_filename(remote_path: str, fallback: str = "download.bin") -> str:
    name = posixpath.basename(normalize_transfer_path(remote_path)).strip()
    return name or fallback


def total_chunks_for_size(size_bytes: int, chunk_size_bytes: int) -> int:
    if size_bytes < 0:
        raise FileTransferError("File size must be non-negative")
    if chunk_size_bytes <= 0:
        raise FileTransferError("Chunk size must be positive")
    if size_bytes == 0:
        return 0
    return math.ceil(size_bytes / chunk_size_bytes)


def decode_chunk_b64(data_b64: str) -> bytes:
    if not isinstance(data_b64, str) or not data_b64:
        raise FileTransferError("Chunk data_b64 is required")
    try:
        return base64.b64decode(data_b64.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise FileTransferError("Chunk data_b64 is invalid") from exc


def transfer_chunk_object_key(settings, transfer_id: uuid.UUID, sequence: int) -> str:
    return normalize_object_key(settings.artifact_s3_prefix, "file-transfer-chunks", str(transfer_id), str(sequence))


def public_file_transfer(transfer: FileTransfer, *, artifact_available: bool | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "acked_chunks": transfer.acked_chunks,
        "artifact_id": str(transfer.artifact_id) if transfer.artifact_id else None,
        "beacon_id": str(transfer.beacon_id),
        "chunk_size_bytes": transfer.chunk_size_bytes,
        "completed_at": transfer.completed_at.isoformat() if transfer.completed_at else None,
        "created_at": transfer.created_at.isoformat(),
        "direction": transfer.direction,
        "error_message": transfer.error_message,
        "filename": transfer.filename,
        "id": str(transfer.id),
        "remote_path": transfer.remote_path,
        "sha256": transfer.sha256,
        "session_id": str(transfer.session_id),
        "size_bytes": transfer.size_bytes,
        "staged_chunks": transfer.staged_chunks,
        "started_at": transfer.started_at.isoformat() if transfer.started_at else None,
        "status": transfer.status,
        "total_chunks": transfer.total_chunks,
        "updated_at": transfer.updated_at.isoformat(),
    }
    if artifact_available is not None:
        payload["artifact_available"] = artifact_available
    return payload


def create_upload_transfer(
    session: Session,
    *,
    actor_subject: str,
    beacon_id: uuid.UUID,
    session_id: uuid.UUID,
    filename: str,
    remote_path: str,
    size_bytes: int,
    sha256: str,
    chunk_size_bytes: int,
    max_size_bytes: int,
    overwrite: bool,
) -> FileTransfer:
    remote_path = normalize_transfer_path(remote_path)
    filename = transfer_filename(filename, fallback=transfer_filename(remote_path, "upload.bin"))
    sha256 = validate_sha256(sha256) or ""
    if size_bytes > max_size_bytes:
        raise FileTransferError("File exceeds the configured transfer size limit")
    total_chunks = total_chunks_for_size(size_bytes, chunk_size_bytes)
    transfer = FileTransfer(
        actor_subject=actor_subject,
        beacon_id=beacon_id,
        session_id=session_id,
        direction=DIRECTION_UPLOAD,
        status=TRANSFER_STATUS_STAGED,
        remote_path=remote_path,
        filename=filename,
        size_bytes=size_bytes,
        sha256=sha256,
        chunk_size_bytes=chunk_size_bytes,
        total_chunks=total_chunks,
        staged_chunks=0,
        acked_chunks=0,
        overwrite=overwrite,
        transfer_metadata={},
    )
    session.add(transfer)
    session.flush()
    return transfer


def get_transfer_for_actor(
    session: Session,
    transfer_id: uuid.UUID,
    *,
    actor_subject: str,
    direction: str | None = None,
) -> FileTransfer:
    transfer = session.get(FileTransfer, transfer_id)
    if transfer is None or transfer.actor_subject != actor_subject:
        raise FileTransferError("File transfer not found")
    if direction is not None and transfer.direction != direction:
        raise FileTransferError("File transfer direction is invalid")
    return transfer


def stage_upload_chunk(
    session: Session,
    settings,
    transfer_id: uuid.UUID,
    *,
    actor_subject: str,
    sequence: int,
    data_b64: str,
    chunk_sha256: str,
) -> FileTransferChunk:
    transfer = get_transfer_for_actor(
        session,
        transfer_id,
        actor_subject=actor_subject,
        direction=DIRECTION_UPLOAD,
    )
    return _store_transfer_chunk(
        session,
        settings,
        transfer,
        sequence=sequence,
        data=decode_chunk_b64(data_b64),
        chunk_sha256=chunk_sha256,
    )


def _store_transfer_chunk(
    session: Session,
    settings,
    transfer: FileTransfer,
    *,
    sequence: int,
    data: bytes,
    chunk_sha256: str,
) -> FileTransferChunk:
    if transfer.status in {TRANSFER_STATUS_COMPLETED, TRANSFER_STATUS_FAILED}:
        raise FileTransferError("File transfer is no longer accepting chunks")
    if sequence < 0 or sequence >= transfer.total_chunks:
        raise FileTransferError("Chunk sequence is out of range")
    if len(data) > transfer.chunk_size_bytes:
        raise FileTransferError("Chunk exceeds transfer chunk size")
    if sequence < transfer.total_chunks - 1 and len(data) != transfer.chunk_size_bytes:
        raise FileTransferError("Non-final chunk size is invalid")
    expected_final = transfer.size_bytes - (transfer.chunk_size_bytes * sequence)
    if sequence == transfer.total_chunks - 1 and len(data) != expected_final:
        raise FileTransferError("Final chunk size is invalid")
    chunk_sha256 = validate_sha256(chunk_sha256, field_name="chunk_sha256") or ""
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if not compare_digest_sha(actual_sha256, chunk_sha256):
        raise FileTransferError("Chunk SHA-256 does not match data")

    key = transfer_chunk_object_key(settings, transfer.id, sequence)
    store = artifact_store_for_settings(settings)
    store.put(key, data, content_type="application/octet-stream")

    existing = (
        session.execute(
            select(FileTransferChunk).where(
                FileTransferChunk.transfer_id == transfer.id,
                FileTransferChunk.sequence == sequence,
            )
        )
        .scalars()
        .one_or_none()
    )
    if existing is not None:
        if existing.chunk_sha256 != chunk_sha256:
            raise FileTransferError("Chunk sequence was already staged with different content")
        existing.size_bytes = len(data)
        existing.object_key = key
        session.add(existing)
        session.flush()
        return existing

    chunk = FileTransferChunk(
        transfer_id=transfer.id,
        sequence=sequence,
        size_bytes=len(data),
        chunk_sha256=chunk_sha256,
        object_key=key,
    )
    session.add(chunk)
    session.flush()
    transfer.staged_chunks = _count_staged_chunks(session, transfer.id)
    session.add(transfer)
    session.flush()
    return chunk


def compare_digest_sha(actual: str, expected: str) -> bool:
    return len(actual) == len(expected) and actual == expected


def read_staged_chunk(settings, chunk: FileTransferChunk) -> bytes:
    return artifact_store_for_settings(settings).get(chunk.object_key)


def staged_chunk(session: Session, transfer_id: uuid.UUID, sequence: int) -> FileTransferChunk:
    chunk = (
        session.execute(
            select(FileTransferChunk).where(
                FileTransferChunk.transfer_id == transfer_id,
                FileTransferChunk.sequence == sequence,
            )
        )
        .scalars()
        .one_or_none()
    )
    if chunk is None:
        raise FileTransferError("Requested chunk has not been staged")
    return chunk


def upload_init_frame_fields(transfer: FileTransfer) -> dict[str, Any]:
    if transfer.staged_chunks != transfer.total_chunks:
        raise FileTransferError("Upload must be fully staged before transfer begins")
    transfer.status = TRANSFER_STATUS_TRANSFERRING
    transfer.started_at = transfer.started_at or utc_now()
    return {
        "chunk_size_bytes": transfer.chunk_size_bytes,
        "filename": transfer.filename,
        "overwrite": transfer.overwrite,
        "path": transfer.remote_path,
        "request_id": f"upload-start-{transfer.id}",
        "session_type": "file_browser",
        "sha256": transfer.sha256,
        "size_bytes": transfer.size_bytes,
        "total_chunks": transfer.total_chunks,
        "transfer_id": str(transfer.id),
    }


def upload_chunk_frame_fields(session: Session, settings, transfer: FileTransfer, sequence: int) -> dict[str, Any]:
    chunk = staged_chunk(session, transfer.id, sequence)
    data = read_staged_chunk(settings, chunk)
    return {
        "chunk_sha256": chunk.chunk_sha256,
        "data_b64": base64.b64encode(data).decode("ascii"),
        "path": transfer.remote_path,
        "request_id": f"upload-chunk-{transfer.id}-{sequence}",
        "sequence": sequence,
        "session_type": "file_browser",
        "size_bytes": len(data),
        "transfer_id": str(transfer.id),
    }


def upload_complete_frame_fields(transfer: FileTransfer) -> dict[str, Any]:
    return {
        "path": transfer.remote_path,
        "request_id": f"upload-complete-{transfer.id}",
        "session_type": "file_browser",
        "transfer_id": str(transfer.id),
    }


def create_download_transfer(
    session: Session,
    *,
    actor_subject: str,
    beacon_id: uuid.UUID,
    session_id: uuid.UUID,
    remote_path: str,
    chunk_size_bytes: int,
) -> FileTransfer:
    remote_path = normalize_transfer_path(remote_path)
    transfer = FileTransfer(
        actor_subject=actor_subject,
        beacon_id=beacon_id,
        session_id=session_id,
        direction=DIRECTION_DOWNLOAD,
        status=TRANSFER_STATUS_TRANSFERRING,
        remote_path=remote_path,
        filename=transfer_filename(remote_path),
        size_bytes=0,
        sha256=None,
        chunk_size_bytes=chunk_size_bytes,
        total_chunks=0,
        staged_chunks=0,
        acked_chunks=0,
        overwrite=False,
        started_at=utc_now(),
        transfer_metadata={},
    )
    session.add(transfer)
    session.flush()
    return transfer


def download_init_frame_fields(transfer: FileTransfer) -> dict[str, Any]:
    return {
        "chunk_size_bytes": transfer.chunk_size_bytes,
        "path": transfer.remote_path,
        "request_id": f"download-init-{transfer.id}",
        "session_type": "file_browser",
        "transfer_id": str(transfer.id),
    }


def download_chunk_request_frame_fields(transfer: FileTransfer, sequence: int) -> dict[str, Any]:
    if sequence < 0 or sequence >= transfer.total_chunks:
        raise FileTransferError("Chunk sequence is out of range")
    return {
        "chunk_size_bytes": transfer.chunk_size_bytes,
        "path": transfer.remote_path,
        "request_id": f"download-chunk-{transfer.id}-{sequence}",
        "sequence": sequence,
        "session_type": "file_browser",
        "transfer_id": str(transfer.id),
    }


def apply_beacon_file_transfer_payload(
    session: Session,
    settings,
    *,
    shell_session: InteractiveSession,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    if settings is None:
        raise FileTransferError("File transfer settings are required")
    transfer_id = _payload_transfer_id(payload)
    transfer = session.get(FileTransfer, transfer_id)
    if transfer is None:
        raise FileTransferError("File transfer not found")
    if transfer.session_id != shell_session.id or transfer.beacon_id != shell_session.beacon_id:
        raise FileTransferError("File transfer does not belong to this session")

    op = str(payload["op"])
    if op == SESSION_OP_TRANSFER_ERROR:
        return _fail_transfer(transfer, payload)
    if op == SESSION_OP_UPLOAD_READY:
        return _apply_upload_ready(session, transfer, payload)
    if op == SESSION_OP_UPLOAD_ACK:
        return _apply_upload_ack(session, transfer, payload)
    if op == SESSION_OP_UPLOAD_NACK:
        return _apply_upload_nack(transfer, payload)
    if op == SESSION_OP_UPLOAD_COMPLETE:
        return _apply_upload_complete(transfer, payload)
    if op == SESSION_OP_DOWNLOAD_READY:
        return _apply_download_ready(session, settings, transfer, payload)
    if op == SESSION_OP_DOWNLOAD_CHUNK:
        return _apply_download_chunk(session, settings, transfer, payload)
    if op == SESSION_OP_DOWNLOAD_COMPLETE:
        return _transfer_message(transfer, op), "session.file.transfer.completed"
    raise FileTransferError("Unsupported file transfer op")


def download_transfer_artifact(
    session: Session,
    settings,
    transfer_id: uuid.UUID,
    *,
    actor_subject: str,
) -> tuple[FileTransfer, Artifact, bytes]:
    transfer = get_transfer_for_actor(
        session,
        transfer_id,
        actor_subject=actor_subject,
        direction=DIRECTION_DOWNLOAD,
    )
    if transfer.status != TRANSFER_STATUS_COMPLETED or transfer.artifact_id is None:
        raise FileTransferError("Download artifact is not ready")
    artifact = session.get(Artifact, transfer.artifact_id)
    if artifact is None:
        raise FileTransferError("Download artifact is not ready")
    return transfer, artifact, read_artifact(settings, artifact)


def _apply_upload_ready(
    session: Session,
    transfer: FileTransfer,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    transfer.status = TRANSFER_STATUS_TRANSFERRING
    transfer.started_at = transfer.started_at or utc_now()
    received_sequences = payload.get("received_sequences")
    if isinstance(received_sequences, list):
        _mark_sequences_acked(session, transfer, received_sequences)
    transfer.acked_chunks = _count_acked_chunks(session, transfer.id)
    return _transfer_message(transfer, SESSION_OP_UPLOAD_READY), "session.file.transfer.progress"


def _apply_upload_ack(
    session: Session,
    transfer: FileTransfer,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    sequence = _payload_sequence(payload)
    chunk = staged_chunk(session, transfer.id, sequence)
    chunk.acked_at = chunk.acked_at or utc_now()
    session.add(chunk)
    session.flush()
    transfer.acked_chunks = _count_acked_chunks(session, transfer.id)
    message = _transfer_message(transfer, SESSION_OP_UPLOAD_ACK)
    message["sequence"] = sequence
    message["next_sequence"] = _next_unacked_sequence(session, transfer)
    return message, "session.file.transfer.progress"


def _apply_upload_nack(transfer: FileTransfer, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    sequence = _payload_sequence(payload)
    message = _transfer_message(transfer, SESSION_OP_UPLOAD_NACK)
    message["sequence"] = sequence
    message["next_sequence"] = sequence
    message["message"] = str(payload.get("message") or "Chunk verification failed; retransmitting.")
    return message, "session.file.transfer.progress"


def _apply_upload_complete(transfer: FileTransfer, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    remote_sha256 = validate_sha256(str(payload.get("sha256") or ""), field_name="remote_sha256")
    if transfer.sha256 and remote_sha256 != transfer.sha256:
        transfer.status = TRANSFER_STATUS_FAILED
        transfer.error_message = "Remote file hash did not match upload hash"
        return _transfer_message(transfer, SESSION_OP_TRANSFER_ERROR), "session.file.transfer.failed"
    transfer.status = TRANSFER_STATUS_COMPLETED
    transfer.completed_at = utc_now()
    transfer.acked_chunks = transfer.total_chunks
    message = _transfer_message(transfer, SESSION_OP_UPLOAD_COMPLETE)
    message["sha256"] = remote_sha256
    return message, "session.file.transfer.completed"


def _apply_download_ready(
    session: Session,
    settings,
    transfer: FileTransfer,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    size_bytes = int(payload.get("size_bytes") or 0)
    chunk_size_bytes = int(payload.get("chunk_size_bytes") or transfer.chunk_size_bytes)
    sha256 = validate_sha256(str(payload.get("sha256") or ""), field_name="sha256")
    transfer.size_bytes = size_bytes
    transfer.sha256 = sha256
    transfer.chunk_size_bytes = chunk_size_bytes
    transfer.total_chunks = total_chunks_for_size(size_bytes, chunk_size_bytes)
    transfer.filename = transfer_filename(str(payload.get("path") or transfer.remote_path), transfer.filename)
    transfer.status = TRANSFER_STATUS_TRANSFERRING
    if transfer.total_chunks == 0:
        _complete_download(session, settings, transfer)
        message = _transfer_message(transfer, SESSION_OP_DOWNLOAD_COMPLETE)
        message["artifact_id"] = str(transfer.artifact_id) if transfer.artifact_id else None
        return message, "session.file.transfer.completed"
    message = _transfer_message(transfer, SESSION_OP_DOWNLOAD_READY)
    message["next_sequence"] = 0
    return message, "session.file.transfer.progress"


def _apply_download_chunk(
    session: Session,
    settings,
    transfer: FileTransfer,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    sequence = _payload_sequence(payload)
    chunk = _store_transfer_chunk(
        session,
        settings,
        transfer,
        sequence=sequence,
        data=decode_chunk_b64(str(payload.get("data_b64") or "")),
        chunk_sha256=str(payload.get("chunk_sha256") or ""),
    )
    chunk.acked_at = chunk.acked_at or utc_now()
    session.add(chunk)
    session.flush()
    transfer.staged_chunks = _count_staged_chunks(session, transfer.id)
    transfer.acked_chunks = transfer.staged_chunks
    if transfer.staged_chunks == transfer.total_chunks:
        _complete_download(session, settings, transfer)
        message = _transfer_message(transfer, SESSION_OP_DOWNLOAD_COMPLETE)
        message["artifact_id"] = str(transfer.artifact_id) if transfer.artifact_id else None
        return message, "session.file.transfer.completed"
    message = _transfer_message(transfer, SESSION_OP_DOWNLOAD_CHUNK)
    message["next_sequence"] = _next_missing_sequence(session, transfer)
    message["sequence"] = sequence
    return message, "session.file.transfer.progress"


def _complete_download(session: Session, settings, transfer: FileTransfer) -> None:
    chunks = (
        session.execute(
            select(FileTransferChunk)
            .where(FileTransferChunk.transfer_id == transfer.id)
            .order_by(FileTransferChunk.sequence)
        )
        .scalars()
        .all()
    )
    chunk_sequences = [chunk.sequence for chunk in chunks]
    if len(chunks) != transfer.total_chunks or chunk_sequences != list(range(transfer.total_chunks)):
        raise FileTransferError("Download is missing one or more chunks")
    content = b"".join(read_staged_chunk(settings, chunk) for chunk in chunks)
    digest = hashlib.sha256(content).hexdigest()
    if transfer.sha256 and digest != transfer.sha256:
        transfer.status = TRANSFER_STATUS_FAILED
        transfer.error_message = "Downloaded file hash did not match beacon source hash"
        raise FileTransferError(transfer.error_message)
    artifact = put_artifact(
        session,
        settings,
        namespace="file-transfers",
        owner_type="file_transfer",
        owner_id=transfer.id,
        filename=transfer.filename,
        content=content,
        content_type="application/octet-stream",
    )
    transfer.artifact_id = artifact.id
    transfer.status = TRANSFER_STATUS_COMPLETED
    transfer.completed_at = utc_now()
    session.add(transfer)
    session.flush()


def _fail_transfer(transfer: FileTransfer, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    transfer.status = TRANSFER_STATUS_FAILED
    transfer.error_message = str(payload.get("message") or payload.get("reason") or "File transfer failed")
    return _transfer_message(transfer, SESSION_OP_TRANSFER_ERROR), "session.file.transfer.failed"


def _payload_transfer_id(payload: dict[str, Any]) -> uuid.UUID:
    try:
        return uuid.UUID(str(payload.get("transfer_id") or ""))
    except ValueError as exc:
        raise FileTransferError("transfer_id must be a UUID") from exc


def _payload_sequence(payload: dict[str, Any]) -> int:
    sequence = payload.get("sequence")
    if not isinstance(sequence, int) or sequence < 0:
        raise FileTransferError("sequence must be a non-negative integer")
    return sequence


def _count_staged_chunks(session: Session, transfer_id: uuid.UUID) -> int:
    return int(
        session.execute(
            select(func.count()).select_from(FileTransferChunk).where(FileTransferChunk.transfer_id == transfer_id)
        ).scalar_one()
    )


def _count_acked_chunks(session: Session, transfer_id: uuid.UUID) -> int:
    return int(
        session.execute(
            select(func.count())
            .select_from(FileTransferChunk)
            .where(FileTransferChunk.transfer_id == transfer_id, FileTransferChunk.acked_at.is_not(None))
        ).scalar_one()
    )


def _mark_sequences_acked(session: Session, transfer: FileTransfer, sequences: list[Any]) -> None:
    for raw_sequence in sequences:
        if not isinstance(raw_sequence, int):
            continue
        chunk = (
            session.execute(
                select(FileTransferChunk).where(
                    FileTransferChunk.transfer_id == transfer.id,
                    FileTransferChunk.sequence == raw_sequence,
                )
            )
            .scalars()
            .one_or_none()
        )
        if chunk is not None:
            chunk.acked_at = chunk.acked_at or utc_now()
            session.add(chunk)
    session.flush()


def _next_unacked_sequence(session: Session, transfer: FileTransfer) -> int | None:
    acked = {
        sequence
        for sequence in session.execute(
            select(FileTransferChunk.sequence).where(
                FileTransferChunk.transfer_id == transfer.id,
                FileTransferChunk.acked_at.is_not(None),
            )
        ).scalars()
    }
    for sequence in range(transfer.total_chunks):
        if sequence not in acked:
            return sequence
    return None


def _next_missing_sequence(session: Session, transfer: FileTransfer) -> int | None:
    staged = {
        sequence
        for sequence in session.execute(
            select(FileTransferChunk.sequence).where(FileTransferChunk.transfer_id == transfer.id)
        ).scalars()
    }
    for sequence in range(transfer.total_chunks):
        if sequence not in staged:
            return sequence
    return None


def _transfer_message(transfer: FileTransfer, op: str) -> dict[str, Any]:
    return {
        **public_file_transfer(transfer),
        "ok": transfer.status != TRANSFER_STATUS_FAILED,
        "op": op,
        "progress": transfer.acked_chunks / transfer.total_chunks if transfer.total_chunks else 1,
        "transfer_id": str(transfer.id),
    }
