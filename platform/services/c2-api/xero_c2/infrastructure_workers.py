from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from xero_common.database import session_factory_for_settings
from xero_common.models import utc_now
from xero_common.redis_bus import publish_operator_event
from xero_common.security import generate_opaque_token, hash_opaque_token, verify_opaque_token

from xero_c2.config import Settings
from xero_c2.models import InfrastructureWorker, WorkerEvent, WorkerPairingToken

WORKER_KIND_HANDLER = "beacon-handler"
WORKER_KIND_SCANNER = "scanner"
WORKER_KINDS = {WORKER_KIND_HANDLER, WORKER_KIND_SCANNER}
WORKER_ORIGIN_EMBEDDED = "embedded"
WORKER_ORIGIN_EXTERNAL = "external"
WORKER_ORIGIN_C2_MANAGED = "c2-managed"
WORKER_STATUS_FAILED = "failed"
WORKER_STATUS_OFFLINE = "offline"
WORKER_STATUS_ONLINE = "online"
WORKER_STATUS_PENDING = "pending"
WORKER_STATUS_STARTING = "starting"
WORKER_STATUS_STOPPING = "stopping"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def embedded_defaults(settings: Settings) -> list[dict[str, Any]]:
    return [
        {
            "kind": WORKER_KIND_HANDLER,
            "name": "Embedded C2 beacon handler",
            "endpoint": settings.worker_connect_url,
            "capabilities": ["embedded-handler", "direct-beacon-registration", "heartbeat"],
        },
        {
            "kind": WORKER_KIND_SCANNER,
            "name": "Embedded C2 scanner",
            "endpoint": settings.worker_connect_url,
            "capabilities": ["embedded-scanner", "recon-ready"],
        },
    ]


def record_worker_event(
    session: Session,
    worker: InfrastructureWorker | None,
    *,
    kind: str,
    event_type: str,
    message: str,
    occurred_at: datetime | None = None,
) -> WorkerEvent:
    event = WorkerEvent(
        worker_id=worker.id if worker is not None else None,
        kind=kind,
        event_type=event_type,
        message=message,
        occurred_at=occurred_at or utc_now(),
    )
    session.add(event)
    return event


def ensure_embedded_workers(session: Session, settings: Settings) -> list[InfrastructureWorker]:
    now = utc_now()
    workers: list[InfrastructureWorker] = []
    for defaults in embedded_defaults(settings):
        worker = session.execute(
            select(InfrastructureWorker).where(
                InfrastructureWorker.kind == defaults["kind"],
                InfrastructureWorker.origin == WORKER_ORIGIN_EMBEDDED,
            )
        ).scalar_one_or_none()
        if worker is None:
            worker = InfrastructureWorker(
                kind=defaults["kind"],
                name=defaults["name"],
                origin=WORKER_ORIGIN_EMBEDDED,
                status=WORKER_STATUS_ONLINE,
                endpoint=defaults["endpoint"],
                capabilities=defaults["capabilities"],
                capacity=1,
                current_load=0,
                version="embedded",
                last_seen=now,
            )
            session.add(worker)
            record_worker_event(
                session,
                worker,
                kind=worker.kind,
                event_type="worker.embedded.ready",
                message=f"{worker.name} is available inside the C2 API.",
                occurred_at=now,
            )
        else:
            worker.status = WORKER_STATUS_ONLINE
            worker.endpoint = defaults["endpoint"]
            worker.capabilities = defaults["capabilities"]
            worker.last_seen = now
        workers.append(worker)
    return workers


def issue_pairing_token(
    session: Session,
    settings: Settings,
    *,
    kind: str,
    name: str,
    worker: InfrastructureWorker | None = None,
) -> tuple[WorkerPairingToken, str]:
    token = generate_opaque_token()
    issued = WorkerPairingToken(
        kind=kind,
        name=name,
        token_hash=hash_opaque_token(token),
        expires_at=utc_now() + timedelta(minutes=settings.worker_pairing_token_expires_minutes),
        worker_id=worker.id if worker is not None else None,
    )
    session.add(issued)
    return issued, token


def find_valid_pairing_token(session: Session, token: str, *, now: datetime | None = None) -> WorkerPairingToken | None:
    checked_at = now or utc_now()
    tokens = session.execute(select(WorkerPairingToken).where(WorkerPairingToken.used_at.is_(None))).scalars().all()
    for pairing_token in tokens:
        if _aware(pairing_token.expires_at) <= checked_at:
            continue
        if verify_opaque_token(token, pairing_token.token_hash):
            return pairing_token
    return None


def find_authenticated_worker(session: Session, worker_id: Any, worker_token: str) -> InfrastructureWorker | None:
    worker = session.get(InfrastructureWorker, worker_id)
    if worker is None or not worker.worker_token_hash:
        return None
    if not verify_opaque_token(worker_token, worker.worker_token_hash):
        return None
    return worker


def mark_stale_workers(
    session: Session,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> list[InfrastructureWorker]:
    checked_at = now or utc_now()
    stale_workers: list[InfrastructureWorker] = []
    workers = session.execute(
        select(InfrastructureWorker).where(InfrastructureWorker.origin != WORKER_ORIGIN_EMBEDDED)
    ).scalars()
    for worker in workers:
        if worker.status not in {WORKER_STATUS_ONLINE, WORKER_STATUS_STARTING}:
            continue
        if worker.last_seen is None:
            elapsed = checked_at - _aware(worker.created_at)
        else:
            elapsed = checked_at - _aware(worker.last_seen)
        if elapsed <= timedelta(seconds=settings.worker_stale_threshold_seconds):
            continue
        old_status = worker.status
        worker.status = WORKER_STATUS_FAILED if old_status == WORKER_STATUS_STARTING else WORKER_STATUS_OFFLINE
        worker.last_error = "Worker heartbeat threshold exceeded"
        record_worker_event(
            session,
            worker,
            kind=worker.kind,
            event_type="worker.status.changed",
            message=f"{worker.name} changed from {old_status} to {worker.status}.",
            occurred_at=checked_at,
        )
        session.add(worker)
        stale_workers.append(worker)
    return stale_workers


async def publish_worker_event(app: Any, settings: Settings, event_type: str, worker_payload: dict) -> None:
    redis_client = getattr(app.state, "redis_client", None)
    event = await publish_operator_event(
        redis_client,
        settings,
        event_type,
        data={"worker": worker_payload},
        scope={"worker_id": worker_payload["id"], "kind": worker_payload["kind"]},
    )
    if redis_client is None:
        await app.state.operator_realtime_hub.broadcast(event)


async def run_worker_stale_monitor(app: Any, settings: Settings, public_worker) -> None:
    while True:
        await asyncio.sleep(settings.worker_heartbeat_interval_seconds)
        try:
            stale_payloads: list[dict] = []
            SessionFactory = session_factory_for_settings(settings)
            with SessionFactory() as session:
                stale_workers = mark_stale_workers(session, settings)
                stale_payloads = [public_worker(worker) for worker in stale_workers]
                session.commit()
            for worker_payload in stale_payloads:
                await publish_worker_event(app, settings, "worker.status.changed", worker_payload)
        except asyncio.CancelledError:
            raise
        except Exception:
            with suppress(Exception):
                continue
