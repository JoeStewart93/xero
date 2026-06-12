from __future__ import annotations

import base64
import uuid
from collections import defaultdict
from collections.abc import MutableMapping
from typing import Any

import redis.asyncio as redis
from fastapi import HTTPException, status
from redis.exceptions import RedisError
from sqlalchemy.orm import Session
from xero_common.models import utc_now

from xero_c2.models import Beacon, Task
from xero_c2.protocol import ACK, TASK_POLL, ProtocolError, encode_frame, load_private_key
from xero_c2.task_audit import TASK_AUDIT_ACTOR_C2, record_task_audit_event

TASK_STATUS_QUEUED = "queued"
TASK_STATUS_DISPATCHED = "dispatched"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_CANCELLED = "cancelled"
TASK_STATUSES = {
    TASK_STATUS_QUEUED,
    TASK_STATUS_DISPATCHED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_CANCELLED,
}

TASK_PRIORITY_LOW = "low"
TASK_PRIORITY_NORMAL = "normal"
TASK_PRIORITY_HIGH = "high"
TASK_PRIORITY_URGENT = "urgent"
TASK_PRIORITIES = {TASK_PRIORITY_LOW, TASK_PRIORITY_NORMAL, TASK_PRIORITY_HIGH, TASK_PRIORITY_URGENT}
TASK_PRIORITY_DISPATCH_ORDER = (TASK_PRIORITY_URGENT, TASK_PRIORITY_HIGH, TASK_PRIORITY_NORMAL, TASK_PRIORITY_LOW)

RESULT_STATUS_MAP = {
    "completed": TASK_STATUS_COMPLETED,
    "failed": TASK_STATUS_FAILED,
    "ok": TASK_STATUS_COMPLETED,
    "running": TASK_STATUS_RUNNING,
    "error": TASK_STATUS_FAILED,
}

class TaskQueueUnavailable(RuntimeError):
    pass


class TaskQueueService:
    def __init__(self, *, app_env: str) -> None:
        self.app_env = app_env.lower()
        self._memory_queues: MutableMapping[str, list[str]] = defaultdict(list)

    @property
    def uses_memory(self) -> bool:
        return self.app_env == "test"

    async def enqueue(self, client: redis.Redis | None, task: Task) -> None:
        key = task_queue_key(task.beacon_id, task.priority)
        if self.uses_memory:
            self._memory_queues[key].append(str(task.id))
            return
        if client is None:
            raise TaskQueueUnavailable("Task queue Redis backend is unavailable")
        try:
            await client.rpush(key, str(task.id))
        except RedisError as exc:
            raise TaskQueueUnavailable("Task queue Redis backend is unavailable") from exc

    async def dequeue(self, client: redis.Redis | None, beacon_id: uuid.UUID, priority: str) -> str | None:
        key = task_queue_key(beacon_id, priority)
        if self.uses_memory:
            queue = self._memory_queues[key]
            if not queue:
                return None
            return queue.pop(0)
        if client is None:
            raise TaskQueueUnavailable("Task queue Redis backend is unavailable")
        try:
            value = await client.lpop(key)
        except RedisError as exc:
            raise TaskQueueUnavailable("Task queue Redis backend is unavailable") from exc
        return str(value) if value is not None else None

    async def remove(self, client: redis.Redis | None, task: Task) -> None:
        key = task_queue_key(task.beacon_id, task.priority)
        task_id = str(task.id)
        if self.uses_memory:
            self._memory_queues[key] = [candidate for candidate in self._memory_queues[key] if candidate != task_id]
            return
        if client is None:
            return
        try:
            await client.lrem(key, 0, task_id)
        except RedisError:
            return


def task_queue_key(beacon_id: uuid.UUID, priority: str) -> str:
    return f"queue:beacon:{beacon_id}:{priority}"


def task_queue_unavailable_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Task queue is unavailable")


def validate_task_timeout(settings, args: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(args)
    timeout = normalized.get("timeout_seconds")
    if timeout is None:
        normalized["timeout_seconds"] = settings.task_default_timeout_seconds
        return normalized
    if not isinstance(timeout, int) or timeout < 1 or timeout > settings.task_max_timeout_seconds:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"timeout_seconds must be between 1 and {settings.task_max_timeout_seconds}",
        )
    return normalized


def public_task(task: Task) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "beacon_id": str(task.beacon_id),
        "module": task.module,
        "args": task.args or {},
        "status": task.status,
        "priority": task.priority,
        "queued_at": task.queued_at.isoformat(),
        "dispatched_at": task.dispatched_at.isoformat() if task.dispatched_at else None,
        "running_at": task.running_at.isoformat() if task.running_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "cancelled_at": task.cancelled_at.isoformat() if task.cancelled_at else None,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


def task_delivery_payload(task: Task) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "beacon_id": str(task.beacon_id),
        "module": task.module,
        "args": task.args or {},
        "priority": task.priority,
        "status": task.status,
    }


async def dispatch_next_task(
    session: Session,
    settings,
    queue: TaskQueueService,
    client: redis.Redis | None,
    *,
    beacon_id: uuid.UUID,
) -> Task | None:
    for priority in TASK_PRIORITY_DISPATCH_ORDER:
        while True:
            raw_task_id = await queue.dequeue(client, beacon_id, priority)
            if raw_task_id is None:
                break
            try:
                task_id = uuid.UUID(raw_task_id)
            except ValueError:
                continue
            task = session.get(Task, task_id)
            if task is None:
                continue
            if task.beacon_id != beacon_id or task.priority != priority or task.status != TASK_STATUS_QUEUED:
                continue
            now = utc_now()
            task.status = TASK_STATUS_DISPATCHED
            task.dispatched_at = now
            session.add(task)
            record_task_audit_event(
                session,
                task,
                actor_subject=TASK_AUDIT_ACTOR_C2,
                event_type="task.dispatched",
                message="Task dispatched to beacon.",
            )
            session.flush()
            return task
    return None


async def requeue_dispatched_task(
    session: Session,
    queue: TaskQueueService,
    client: redis.Redis | None,
    task: Task,
) -> None:
    task.status = TASK_STATUS_QUEUED
    task.dispatched_at = None
    session.add(task)
    record_task_audit_event(
        session,
        task,
        actor_subject=TASK_AUDIT_ACTOR_C2,
        event_type="task.requeued",
        message="Task requeued after delivery failed.",
    )
    session.flush()
    await queue.enqueue(client, task)


async def cancel_task(
    session: Session,
    queue: TaskQueueService,
    client: redis.Redis | None,
    task: Task,
    *,
    actor_subject: str = TASK_AUDIT_ACTOR_C2,
) -> Task:
    if task.status != TASK_STATUS_QUEUED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only queued tasks can be cancelled")
    task.status = TASK_STATUS_CANCELLED
    task.cancelled_at = utc_now()
    session.add(task)
    record_task_audit_event(
        session,
        task,
        actor_subject=actor_subject,
        event_type="task.cancelled",
        message="Task cancelled before dispatch.",
    )
    session.flush()
    await queue.remove(client, task)
    return task


def apply_task_result(session: Session, *, beacon_id: uuid.UUID, payload: dict[str, Any]) -> Task | None:
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
            status_code=403,
        )

    raw_status = payload.get("status")
    if not isinstance(raw_status, str) or raw_status.lower() not in RESULT_STATUS_MAP:
        raise ProtocolError("INVALID_PAYLOAD", "TASK_RESULT status must be running, completed, failed, ok, or error")

    next_status = RESULT_STATUS_MAP[raw_status.lower()]
    now = utc_now()
    task.status = next_status
    if next_status == TASK_STATUS_RUNNING:
        task.running_at = now
    if next_status in {TASK_STATUS_COMPLETED, TASK_STATUS_FAILED}:
        task.completed_at = now
    session.add(task)
    record_task_audit_event(
        session,
        task,
        actor_subject=f"beacon:{beacon_id}",
        event_type=task_event_type(task.status),
        message="Beacon reported task lifecycle update.",
        metadata={
            "exit_code": payload.get("exit_code"),
            "timed_out": payload.get("timed_out"),
            "truncated": payload.get("truncated"),
        },
    )
    return task


def task_event_type(status_value: str) -> str:
    return f"task.{status_value}"


def encode_task_ack_frame(settings, beacon: Beacon, task: Task | None, *, transport: str) -> bytes:
    if not beacon.protocol_session_id or not beacon.protocol_peer_public_key_b64:
        raise ProtocolError("PROTOCOL_METADATA_REQUIRED", "Beacon protocol metadata is required for task delivery")
    try:
        session_id = uuid.UUID(beacon.protocol_session_id)
        peer_public_key = base64.b64decode(beacon.protocol_peer_public_key_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise ProtocolError("PROTOCOL_METADATA_INVALID", "Beacon protocol metadata is invalid") from exc
    payload = {
        "status": "ok",
        "acknowledged_message_type": TASK_POLL,
        "session_id": str(session_id),
        "transport": transport,
        "task": task_delivery_payload(task) if task is not None else None,
    }
    private_key = load_private_key(settings.protocol_private_key_b64)
    return encode_frame(
        private_key=private_key,
        peer_public_key=peer_public_key,
        message_type=ACK,
        payload=payload,
        session_id=session_id,
        max_frame_bytes=settings.protocol_max_frame_bytes,
    )
