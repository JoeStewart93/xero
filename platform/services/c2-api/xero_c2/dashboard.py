from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from xero_common.models import utc_now

from xero_c2.models import Beacon, BeaconEvent, Task, TaskAuditEvent
from xero_c2.task_queue import public_task


def beacon_counts(session: Session) -> dict[str, int]:
    total = session.scalar(select(func.count()).select_from(Beacon)) or 0
    online = session.scalar(select(func.count()).select_from(Beacon).where(Beacon.status == "online")) or 0
    offline = session.scalar(select(func.count()).select_from(Beacon).where(Beacon.status == "offline")) or 0
    return {"total": int(total), "online": int(online), "offline": int(offline)}


def beacon_activity_label(event: BeaconEvent, beacon: Beacon | None) -> str:
    name = beacon.hostname if beacon else "Beacon"
    if event.old_status == event.new_status:
        return f"{name} reported {event.new_status}"
    return f"{name} changed from {event.old_status} to {event.new_status}"


def task_activity_label(event: TaskAuditEvent) -> str:
    command = f" `{event.command}`" if event.command else ""
    status = event.task_status or "updated"
    return f"Task{command} {status}"


def public_beacon_activity(session: Session, event: BeaconEvent) -> dict[str, Any]:
    beacon = session.get(Beacon, event.beacon_id)
    return {
        "id": f"beacon-{event.id}",
        "type": "beacon.status",
        "label": beacon_activity_label(event, beacon),
        "occurred_at": event.occurred_at,
        "beacon_id": str(event.beacon_id),
        "task_id": None,
        "status": event.new_status,
        "detail": event.reason,
    }


def public_task_activity(event: TaskAuditEvent) -> dict[str, Any]:
    return {
        "id": f"task-{event.id}",
        "type": event.event_type,
        "label": task_activity_label(event),
        "occurred_at": event.occurred_at,
        "beacon_id": str(event.beacon_id),
        "task_id": str(event.task_id),
        "status": event.task_status,
        "detail": event.message,
    }


def recent_activity(session: Session, *, limit: int = 10) -> list[dict[str, Any]]:
    beacon_events = (
        session.execute(select(BeaconEvent).order_by(BeaconEvent.occurred_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    task_events = (
        session.execute(select(TaskAuditEvent).order_by(TaskAuditEvent.occurred_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    items = [public_beacon_activity(session, event) for event in beacon_events]
    items.extend(public_task_activity(event) for event in task_events)
    items.sort(key=lambda item: item["occurred_at"] if isinstance(item["occurred_at"], datetime) else utc_now(), reverse=True)
    return items[:limit]


def recent_tasks(session: Session, *, limit: int = 10) -> list[dict[str, Any]]:
    tasks = session.execute(select(Task).order_by(Task.updated_at.desc(), Task.created_at.desc()).limit(limit)).scalars().all()
    return [public_task(task) for task in tasks]


def public_dashboard_summary(session: Session, *, c2_health: dict, activity_limit: int = 10) -> dict[str, Any]:
    return {
        "generated_at": utc_now(),
        "beacons": beacon_counts(session),
        "recent_tasks": recent_tasks(session, limit=10),
        "recent_activity": recent_activity(session, limit=activity_limit),
        "c2_health": c2_health,
    }
