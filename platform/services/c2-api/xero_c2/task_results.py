from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from datetime import timedelta
from typing import Any

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session
from xero_common.models import utc_now

from xero_c2.artifacts import artifact_is_available, artifact_store_for_settings, put_artifact, read_artifact
from xero_c2.models import Artifact, ResultChunk, Task, TaskResult, TaskResultArtifact
from xero_c2.protocol import ProtocolError

RESULT_EVENT_CHUNK = "task.result.chunk"
RESULT_EVENT_COMPLETED = "task.result.completed"
RESULT_STREAMS = {"stdout", "stderr"}
TERMINAL_RESULT_STATUSES = {"completed", "failed", "ok", "error"}


def normalized_result_status(payload: dict[str, Any]) -> str | None:
    raw_status = payload.get("status")
    if not isinstance(raw_status, str):
        return None
    status_value = raw_status.lower()
    if status_value == "ok":
        return "completed"
    if status_value == "error":
        return "failed"
    return status_value


def is_chunk_payload(payload: dict[str, Any]) -> bool:
    return any(key in payload for key in ("chunk", "chunk_index", "chunk_sequence", "total_chunks", "result_final"))


def is_terminal_result_payload(payload: dict[str, Any]) -> bool:
    raw_status = payload.get("status")
    return isinstance(raw_status, str) and raw_status.lower() in TERMINAL_RESULT_STATUSES


def task_for_result_payload(session: Session, *, beacon_id: uuid.UUID, payload: dict[str, Any]) -> Task | None:
    raw_task_id = payload.get("task_id")
    if not isinstance(raw_task_id, str):
        return None
    try:
        task_id = uuid.UUID(raw_task_id)
    except ValueError:
        return None
    task = session.get(Task, task_id)
    if task is None:
        return None
    if task.beacon_id != beacon_id:
        raise ProtocolError(
            "TASK_BEACON_MISMATCH",
            "TASK_RESULT task_id does not belong to the beacon",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return task


def result_expires_at(settings):
    return utc_now() + timedelta(days=settings.task_retention_days)


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalize_digest(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized.startswith("sha256:"):
        normalized = normalized.removeprefix("sha256:")
    return normalized or None


def text_size(value: str) -> int:
    return len(value.encode("utf-8"))


def ensure_task_result(session: Session, settings, task: Task, *, status_value: str) -> TaskResult:
    result = session.execute(select(TaskResult).where(TaskResult.task_id == task.id)).scalar_one_or_none()
    if result is None:
        result = TaskResult(
            task_id=task.id,
            beacon_id=task.beacon_id,
            status=status_value,
            expires_at=result_expires_at(settings),
            result_metadata={},
        )
    result.status = status_value
    result.beacon_id = task.beacon_id
    result.expires_at = result_expires_at(settings)
    session.add(result)
    session.flush()
    return result


def delete_result_artifacts(session: Session, settings, result: TaskResult) -> None:
    references = (
        session.execute(select(TaskResultArtifact).where(TaskResultArtifact.task_result_id == result.id))
        .scalars()
        .all()
    )
    store = artifact_store_for_settings(settings)
    for reference in references:
        artifact = session.get(Artifact, reference.artifact_id)
        if artifact is not None:
            store.delete(artifact.object_key)
            session.delete(artifact)
        session.delete(reference)
    session.flush()


def clear_result_body(session: Session, settings, result: TaskResult) -> None:
    delete_result_artifacts(session, settings, result)
    result.stdout_text = None
    result.stderr_text = None


def result_artifacts(session: Session, result: TaskResult) -> list[tuple[str, Artifact]]:
    rows = (
        session.execute(
            select(TaskResultArtifact, Artifact)
            .join(Artifact, Artifact.id == TaskResultArtifact.artifact_id)
            .where(TaskResultArtifact.task_result_id == result.id)
            .order_by(TaskResultArtifact.role.asc(), Artifact.created_at.asc())
        )
        .all()
    )
    return [(reference.role, artifact) for reference, artifact in rows]


def store_stream(
    session: Session,
    settings,
    result: TaskResult,
    *,
    role: str,
    text: str,
) -> tuple[str | None, int, str]:
    content = text.encode("utf-8")
    digest = digest_bytes(content)
    if len(content) <= settings.task_result_inline_max_bytes:
        return text, len(content), digest

    artifact = put_artifact(
        session,
        settings,
        namespace="task-results",
        owner_type="task_result",
        owner_id=result.id,
        filename=f"{result.task_id}-{role}.txt",
        content=content,
        content_type="text/plain; charset=utf-8",
    )
    session.add(TaskResultArtifact(task_result_id=result.id, artifact_id=artifact.id, role=role))
    return None, len(content), digest


def store_completed_result(
    session: Session,
    settings,
    task: Task,
    payload: dict[str, Any],
    *,
    stdout: str,
    stderr: str,
) -> TaskResult:
    status_value = normalized_result_status(payload)
    if status_value not in {"completed", "failed"}:
        raise ProtocolError("INVALID_PAYLOAD", "TASK_RESULT terminal status must be completed or failed")

    result = ensure_task_result(session, settings, task, status_value=status_value)
    clear_result_body(session, settings, result)

    stdout_text, stdout_size, stdout_sha = store_stream(session, settings, result, role="stdout", text=stdout)
    stderr_text, stderr_size, stderr_sha = store_stream(session, settings, result, role="stderr", text=stderr)
    combined = stdout.encode("utf-8") + stderr.encode("utf-8")

    result.status = status_value
    result.exit_code = int(payload["exit_code"]) if isinstance(payload.get("exit_code"), int) else None
    result.error_message = (
        str(payload.get("error_message"))[:1024] if payload.get("error_message") is not None else None
    )
    result.timed_out = bool(payload.get("timed_out", False))
    result.truncated = bool(payload.get("truncated", False))
    result.stdout_text = stdout_text
    result.stderr_text = stderr_text
    result.stdout_size_bytes = stdout_size
    result.stderr_size_bytes = stderr_size
    result.output_size_bytes = len(combined)
    result.stdout_sha256 = stdout_sha
    result.stderr_sha256 = stderr_sha
    result.output_sha256 = digest_bytes(combined)
    result.result_metadata = {
        "result_id": payload.get("result_id"),
        "session_id": payload.get("session_id"),
        "upload_id": payload.get("upload_id"),
    }
    result.completed_at = utc_now()
    result.expires_at = result_expires_at(settings)
    session.add(result)
    session.flush()
    return result


def chunk_sequence(payload: dict[str, Any]) -> int:
    raw_sequence = payload.get("chunk_index", payload.get("chunk_sequence"))
    if not isinstance(raw_sequence, int) or raw_sequence < 0:
        raise ProtocolError("INVALID_PAYLOAD", "TASK_RESULT chunk_index must be a non-negative integer")
    return raw_sequence


def chunk_total(payload: dict[str, Any]) -> int:
    raw_total = payload.get("total_chunks")
    if not isinstance(raw_total, int) or raw_total < 1:
        raise ProtocolError("INVALID_PAYLOAD", "TASK_RESULT total_chunks must be a positive integer")
    return raw_total


def chunk_upload_id(payload: dict[str, Any]) -> str:
    raw_upload_id = payload.get("upload_id") or payload.get("result_id")
    if not isinstance(raw_upload_id, str) or not raw_upload_id.strip():
        raise ProtocolError("INVALID_PAYLOAD", "TASK_RESULT chunk upload_id is required")
    return raw_upload_id.strip()[:128]


def record_result_chunk(session: Session, result: TaskResult, task: Task, payload: dict[str, Any]) -> ResultChunk:
    stream = payload.get("stream")
    if stream not in RESULT_STREAMS:
        raise ProtocolError("INVALID_PAYLOAD", "TASK_RESULT chunk stream must be stdout or stderr")
    chunk_text = payload.get("chunk")
    if not isinstance(chunk_text, str):
        raise ProtocolError("INVALID_PAYLOAD", "TASK_RESULT chunk must be a string")
    sequence = chunk_sequence(payload)
    total_chunks = chunk_total(payload)
    if sequence >= total_chunks:
        raise ProtocolError("INVALID_PAYLOAD", "TASK_RESULT chunk_index must be less than total_chunks")

    chunk_sha256 = normalize_digest(payload.get("chunk_sha256")) or digest_text(chunk_text)
    actual_digest = digest_text(chunk_text)
    if chunk_sha256 != actual_digest:
        raise ProtocolError("INVALID_PAYLOAD", "TASK_RESULT chunk_sha256 does not match chunk content")

    upload_id = chunk_upload_id(payload)
    existing = session.execute(
        select(ResultChunk).where(
            ResultChunk.task_result_id == result.id,
            ResultChunk.stream == stream,
            ResultChunk.upload_id == upload_id,
            ResultChunk.sequence == sequence,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if (
            existing.chunk_sha256 != chunk_sha256
            or existing.chunk_text != chunk_text
            or existing.total_chunks != total_chunks
        ):
            raise ProtocolError("INVALID_PAYLOAD", "TASK_RESULT duplicate chunk conflicts with existing chunk")
        return existing

    chunk = ResultChunk(
        task_result_id=result.id,
        task_id=task.id,
        beacon_id=task.beacon_id,
        upload_id=upload_id,
        stream=stream,
        sequence=sequence,
        total_chunks=total_chunks,
        chunk_text=chunk_text,
        chunk_sha256=chunk_sha256,
        stream_sha256=normalize_digest(payload.get("stream_sha256")),
        stream_size_bytes=(
            payload.get("stream_size_bytes") if isinstance(payload.get("stream_size_bytes"), int) else None
        ),
        received_at=utc_now(),
    )
    session.add(chunk)
    session.flush()
    return chunk


def task_result_chunk_for_payload(session: Session, task: Task, payload: dict[str, Any]) -> ResultChunk | None:
    if not is_chunk_payload(payload):
        return None
    stream = payload.get("stream")
    if stream not in RESULT_STREAMS:
        return None
    sequence = chunk_sequence(payload)
    upload_id = chunk_upload_id(payload)
    return session.execute(
        select(ResultChunk).where(
            ResultChunk.task_id == task.id,
            ResultChunk.stream == stream,
            ResultChunk.upload_id == upload_id,
            ResultChunk.sequence == sequence,
        )
    ).scalar_one_or_none()


def public_task_result_chunk(chunk: ResultChunk) -> dict[str, Any]:
    return {
        "id": str(chunk.id),
        "task_result_id": str(chunk.task_result_id),
        "task_id": str(chunk.task_id),
        "beacon_id": str(chunk.beacon_id),
        "upload_id": chunk.upload_id,
        "stream": chunk.stream,
        "sequence": chunk.sequence,
        "total_chunks": chunk.total_chunks,
        "chunk": chunk.chunk_text,
        "chunk_sha256": chunk.chunk_sha256,
        "stream_sha256": chunk.stream_sha256,
        "stream_size_bytes": chunk.stream_size_bytes,
        "received_at": chunk.received_at.isoformat(),
        "created_at": chunk.created_at.isoformat(),
    }


def assembled_streams_from_chunks(session: Session, result: TaskResult, upload_id: str) -> dict[str, str]:
    chunks = (
        session.execute(
            select(ResultChunk)
            .where(ResultChunk.task_result_id == result.id, ResultChunk.upload_id == upload_id)
            .order_by(ResultChunk.stream.asc(), ResultChunk.sequence.asc())
        )
        .scalars()
        .all()
    )
    by_stream: dict[str, list[ResultChunk]] = defaultdict(list)
    for chunk in chunks:
        by_stream[chunk.stream].append(chunk)

    assembled: dict[str, str] = {}
    for stream, stream_chunks in by_stream.items():
        totals = {chunk.total_chunks for chunk in stream_chunks}
        if len(totals) != 1:
            raise ProtocolError("INVALID_PAYLOAD", f"TASK_RESULT {stream} chunks have inconsistent total_chunks")
        total = totals.pop()
        sequences = {chunk.sequence for chunk in stream_chunks}
        if sequences != set(range(total)):
            raise ProtocolError("INVALID_PAYLOAD", f"TASK_RESULT {stream} chunks are incomplete")
        text = "".join(chunk.chunk_text for chunk in sorted(stream_chunks, key=lambda item: item.sequence))
        expected_sha = next((chunk.stream_sha256 for chunk in stream_chunks if chunk.stream_sha256), None)
        if expected_sha and expected_sha != digest_text(text):
            raise ProtocolError(
                "INVALID_PAYLOAD",
                f"TASK_RESULT {stream} stream_sha256 does not match assembled content",
            )
        expected_size = next(
            (chunk.stream_size_bytes for chunk in stream_chunks if chunk.stream_size_bytes is not None),
            None,
        )
        if expected_size is not None and expected_size != text_size(text):
            raise ProtocolError(
                "INVALID_PAYLOAD",
                f"TASK_RESULT {stream} stream_size_bytes does not match assembled content",
            )
        assembled[stream] = text
    return assembled


def ingest_chunked_task_result(session: Session, settings, task: Task, payload: dict[str, Any]) -> TaskResult | None:
    status_value = normalized_result_status(payload)
    if status_value not in {"completed", "failed"}:
        raise ProtocolError("INVALID_PAYLOAD", "Chunked TASK_RESULT requires completed or failed status")

    result = ensure_task_result(session, settings, task, status_value="assembling")
    chunk = record_result_chunk(session, result, task, payload)
    if payload.get("result_final") is not True:
        return None

    assembled = assembled_streams_from_chunks(session, result, chunk.upload_id)
    stdout = assembled.get("stdout", payload.get("stdout") if isinstance(payload.get("stdout"), str) else "")
    stderr = assembled.get("stderr", payload.get("stderr") if isinstance(payload.get("stderr"), str) else "")
    payload_with_upload = dict(payload)
    payload_with_upload["upload_id"] = chunk.upload_id
    return store_completed_result(session, settings, task, payload_with_upload, stdout=stdout, stderr=stderr)


def ingest_task_result_payload(session: Session, settings, task: Task, payload: dict[str, Any]) -> TaskResult | None:
    if normalized_result_status(payload) == "running":
        return None
    if is_chunk_payload(payload):
        return ingest_chunked_task_result(session, settings, task, payload)
    if not is_terminal_result_payload(payload):
        return None
    stdout = payload.get("stdout") if isinstance(payload.get("stdout"), str) else ""
    stderr = payload.get("stderr") if isinstance(payload.get("stderr"), str) else ""
    return store_completed_result(session, settings, task, payload, stdout=stdout, stderr=stderr)


def stream_artifact(session: Session, result: TaskResult, role: str) -> Artifact | None:
    return (
        session.execute(
            select(Artifact)
            .join(TaskResultArtifact, TaskResultArtifact.artifact_id == Artifact.id)
            .where(TaskResultArtifact.task_result_id == result.id, TaskResultArtifact.role == role)
        )
        .scalars()
        .first()
    )


def result_stream_text(session: Session, settings, result: TaskResult, role: str) -> str:
    if role == "stdout" and result.stdout_text is not None:
        return result.stdout_text
    if role == "stderr" and result.stderr_text is not None:
        return result.stderr_text
    artifact = stream_artifact(session, result, role)
    if artifact is None:
        return ""
    return read_artifact(settings, artifact).decode("utf-8", errors="replace")


def public_task_result(
    session: Session,
    settings,
    result: TaskResult,
    *,
    include_output: bool = False,
    include_availability: bool = False,
) -> dict[str, Any]:
    artifacts = []
    for role, artifact in result_artifacts(session, result):
        artifact_payload = {
            "id": str(artifact.id),
            "role": role,
            "filename": artifact.filename,
            "content_type": artifact.content_type,
            "size_bytes": artifact.size_bytes,
            "sha256": artifact.sha256,
        }
        if include_availability:
            artifact_payload["available"] = artifact_is_available(settings, artifact)
        artifacts.append(artifact_payload)

    payload: dict[str, Any] = {
        "id": str(result.id),
        "task_id": str(result.task_id),
        "beacon_id": str(result.beacon_id),
        "status": result.status,
        "exit_code": result.exit_code,
        "error_message": result.error_message,
        "timed_out": result.timed_out,
        "truncated": result.truncated,
        "stdout_size_bytes": result.stdout_size_bytes,
        "stderr_size_bytes": result.stderr_size_bytes,
        "output_size_bytes": result.output_size_bytes,
        "stdout_sha256": result.stdout_sha256,
        "stderr_sha256": result.stderr_sha256,
        "output_sha256": result.output_sha256,
        "metadata": result.result_metadata or {},
        "artifacts": artifacts,
        "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        "expires_at": result.expires_at.isoformat(),
        "created_at": result.created_at.isoformat(),
        "updated_at": result.updated_at.isoformat(),
    }
    if include_output:
        payload["stdout"] = result_stream_text(session, settings, result, "stdout")
        payload["stderr"] = result_stream_text(session, settings, result, "stderr")
    return payload


def task_result_event_payload(session: Session, settings, result: TaskResult) -> dict[str, Any]:
    return public_task_result(session, settings, result, include_output=False, include_availability=False)


def download_text_for_result(session: Session, settings, result: TaskResult, stream: str) -> tuple[str, str]:
    if stream == "combined":
        content = result_stream_text(session, settings, result, "stdout") + result_stream_text(
            session,
            settings,
            result,
            "stderr",
        )
        return content, f"{result.task_id}-combined.txt"
    if stream not in RESULT_STREAMS:
        raise ProtocolError("INVALID_PAYLOAD", "Result download stream must be combined, stdout, or stderr")
    return result_stream_text(session, settings, result, stream), f"{result.task_id}-{stream}.txt"


def purge_expired_task_results(session: Session, settings, *, now=None) -> int:
    now = now or utc_now()
    expired = session.execute(select(TaskResult).where(TaskResult.expires_at <= now)).scalars().all()
    count = 0
    for result in expired:
        delete_result_artifacts(session, settings, result)
        session.delete(result)
        count += 1
    session.flush()
    return count


async def run_task_result_retention_monitor(app, settings) -> None:
    import asyncio

    from xero_common.database import session_factory_for_settings

    SessionFactory = session_factory_for_settings(settings)
    while True:
        await asyncio.sleep(settings.task_result_cleanup_interval_seconds)
        with SessionFactory() as session:
            purge_expired_task_results(session, settings)
            session.commit()
