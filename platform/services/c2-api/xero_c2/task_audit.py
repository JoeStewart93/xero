from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session
from xero_common.models import utc_now

from xero_c2.models import Task, TaskAuditEvent

TASK_AUDIT_ACTOR_C2 = "c2-system"


def task_command(task: Task) -> str | None:
    command = (task.args or {}).get("command")
    return command if isinstance(command, str) else None


def record_task_audit_event(
    session: Session,
    task: Task,
    *,
    actor_subject: str,
    event_type: str,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> TaskAuditEvent:
    event = TaskAuditEvent(
        task_id=task.id,
        beacon_id=task.beacon_id,
        module=task.module,
        command=task_command(task),
        actor_subject=actor_subject or TASK_AUDIT_ACTOR_C2,
        event_type=event_type,
        task_status=task.status,
        message=message,
        event_metadata=metadata or {},
        occurred_at=utc_now(),
    )
    session.add(event)
    return event


def public_task_audit_event(event: TaskAuditEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "task_id": str(event.task_id),
        "beacon_id": str(event.beacon_id),
        "module": event.module,
        "command": event.command,
        "actor_subject": event.actor_subject,
        "event_type": event.event_type,
        "task_status": event.task_status,
        "message": event.message,
        "metadata": event.event_metadata or {},
        "occurred_at": event.occurred_at.isoformat(),
        "created_at": event.created_at.isoformat(),
        "updated_at": event.updated_at.isoformat(),
    }
