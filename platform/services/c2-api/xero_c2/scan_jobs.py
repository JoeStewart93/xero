from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from xero_common.database import session_factory_for_settings
from xero_common.models import utc_now
from xero_common.redis_bus import publish_operator_event

from xero_c2.infrastructure_workers import WORKER_KIND_SCANNER, WORKER_ORIGIN_EMBEDDED
from xero_c2.models import InfrastructureWorker, ScanJob, ScanResultChunk

SCAN_STATUS_QUEUED = "queued"
SCAN_STATUS_RUNNING = "running"
SCAN_STATUS_COMPLETED = "completed"
SCAN_STATUS_FAILED = "failed"
SCAN_TERMINAL_STATUSES = {SCAN_STATUS_COMPLETED, SCAN_STATUS_FAILED}
SCAN_PROGRESS_BATCH_SIZE = 100


@dataclass(frozen=True)
class ScanExecutionResult:
    results: list[dict[str, Any]]
    summary: dict[str, Any]
    state_counts: dict[str, int]
    probes_completed: int
    probes_total: int
    next_sequence: int


def find_embedded_scanner(session: Session) -> InfrastructureWorker | None:
    return session.execute(
        select(InfrastructureWorker).where(
            InfrastructureWorker.kind == WORKER_KIND_SCANNER,
            InfrastructureWorker.origin == WORKER_ORIGIN_EMBEDDED,
        )
    ).scalar_one_or_none()


def public_scan_job(job: ScanJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "module": job.module,
        "args": job.args or {},
        "status": job.status,
        "actor_subject": job.actor_subject,
        "execution_target_requested": job.execution_target_requested,
        "execution_target_resolved": job.execution_target_resolved,
        "worker_id": str(job.worker_id) if job.worker_id else None,
        "progress_completed": job.progress_completed,
        "progress_total": job.progress_total,
        "state_counts": job.state_counts or {},
        "summary": job.summary or {},
        "results": job.results or [],
        "error_message": job.error_message,
        "queued_at": job.queued_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


def public_scan_chunk(chunk: ScanResultChunk) -> dict[str, Any]:
    return {
        "id": str(chunk.id),
        "scan_job_id": str(chunk.scan_job_id),
        "sequence": chunk.sequence,
        "kind": chunk.kind,
        "payload": chunk.payload or {},
        "probes_completed": chunk.probes_completed,
        "probes_total": chunk.probes_total,
        "emitted_at": chunk.emitted_at.isoformat(),
        "created_at": chunk.created_at.isoformat(),
    }


async def publish_scan_event(
    app: Any,
    settings,
    event_type: str,
    job_payload: dict[str, Any],
    chunk_payload: dict[str, Any] | None = None,
) -> None:
    data: dict[str, Any] = {"scan_job": job_payload}
    if chunk_payload is not None:
        data["scan_chunk"] = chunk_payload
    redis_client = getattr(app.state, "redis_client", None)
    event = await publish_operator_event(
        redis_client,
        settings,
        event_type,
        data=data,
        scope={"scan_job_id": job_payload["id"], "module": job_payload["module"]},
    )
    if redis_client is None:
        await app.state.operator_realtime_hub.broadcast(event)


def create_scan_job(
    session: Session,
    *,
    actor_subject: str,
    module: str,
    raw_args: dict[str, Any],
) -> ScanJob:
    args = normalize_scan_args(module, raw_args)
    worker = find_embedded_scanner(session)
    if worker is None:
        raise ValueError("Embedded scanner is not available")
    job = ScanJob(
        actor_subject=actor_subject,
        args=args,
        execution_target_requested=args["execution_target"],
        execution_target_resolved="embedded-c2",
        module=module,
        progress_completed=0,
        progress_total=estimate_scan_progress_total(module, args),
        state_counts=initial_scan_state_counts(module),
        status=SCAN_STATUS_QUEUED,
        worker_id=worker.id,
    )
    session.add(job)
    return job


def normalize_scan_args(module: str, raw_args: dict[str, Any]) -> dict[str, Any]:
    from xero_c2.portscan import PORTSCAN_MODULE_ID, normalized_portscan_args
    from xero_c2.serviceenum import SERVICEENUM_MODULE_ID, normalized_serviceenum_args

    if module == PORTSCAN_MODULE_ID:
        return normalized_portscan_args(raw_args)
    if module == SERVICEENUM_MODULE_ID:
        return normalized_serviceenum_args(raw_args)
    raise ValueError("Unsupported scan module")


def estimate_scan_progress_total(module: str, args: dict[str, Any]) -> int:
    from xero_c2.portscan import PORTSCAN_MODULE_ID, estimate_portscan_progress_total
    from xero_c2.serviceenum import SERVICEENUM_MODULE_ID, estimate_serviceenum_progress_total

    if module == PORTSCAN_MODULE_ID:
        return estimate_portscan_progress_total(args)
    if module == SERVICEENUM_MODULE_ID:
        return estimate_serviceenum_progress_total(args)
    raise ValueError("Unsupported scan module")


def initial_scan_state_counts(module: str) -> dict[str, int]:
    from xero_c2.portscan import PORTSCAN_MODULE_ID, portscan_initial_state_counts
    from xero_c2.serviceenum import SERVICEENUM_MODULE_ID, serviceenum_initial_state_counts

    if module == PORTSCAN_MODULE_ID:
        return portscan_initial_state_counts()
    if module == SERVICEENUM_MODULE_ID:
        return serviceenum_initial_state_counts()
    raise ValueError("Unsupported scan module")


async def run_scan_job(app: Any, settings, scan_job_id: uuid.UUID) -> None:
    SessionFactory = session_factory_for_settings(settings)
    started_at = time.perf_counter()
    try:
        with SessionFactory() as session:
            job = session.get(ScanJob, scan_job_id)
            if job is None or job.status in SCAN_TERMINAL_STATUSES:
                return
            job.status = SCAN_STATUS_RUNNING
            job.started_at = utc_now()
            session.add(job)
            session.commit()
            session.refresh(job)
            await publish_scan_event(app, settings, "scan.job.running", public_scan_job(job))
            module = job.module
            args = dict(job.args or {})

        result = await execute_scan_module(app, settings, scan_job_id, module, args, started_at)
        with SessionFactory() as session:
            job = session.get(ScanJob, scan_job_id)
            if job is None:
                return
            job.status = SCAN_STATUS_COMPLETED
            job.progress_completed = result.probes_completed
            job.progress_total = result.probes_total
            job.state_counts = dict(result.state_counts)
            job.summary = result.summary
            job.results = result.results
            job.completed_at = utc_now()
            session.add(job)
            session.flush()
            summary_chunk = ScanResultChunk(
                scan_job_id=job.id,
                sequence=result.next_sequence,
                kind="summary",
                payload={"results": result.results, "summary": result.summary},
                probes_completed=result.probes_completed,
                probes_total=result.probes_total,
                emitted_at=utc_now(),
            )
            session.add(summary_chunk)
            session.commit()
            session.refresh(job)
            session.refresh(summary_chunk)
            await publish_scan_event(
                app,
                settings,
                "scan.result.completed",
                public_scan_job(job),
                public_scan_chunk(summary_chunk),
            )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        with suppress(Exception):
            await mark_scan_failed(app, settings, scan_job_id, str(exc))


async def execute_scan_module(
    app: Any,
    settings,
    scan_job_id: uuid.UUID,
    module: str,
    args: dict[str, Any],
    started_at: float,
) -> ScanExecutionResult:
    from xero_c2.portscan import PORTSCAN_MODULE_ID, run_portscan_scan_job
    from xero_c2.serviceenum import SERVICEENUM_MODULE_ID, run_serviceenum_scan_job

    if module == PORTSCAN_MODULE_ID:
        return await run_portscan_scan_job(app, settings, scan_job_id, args, started_at)
    if module == SERVICEENUM_MODULE_ID:
        return await run_serviceenum_scan_job(app, settings, scan_job_id, args, started_at)
    raise ValueError("Unsupported scan module")


async def persist_scan_progress(
    app: Any,
    settings,
    scan_job_id: uuid.UUID,
    *,
    sequence: int,
    kind: str,
    results: list[dict[str, Any]],
    completed: int,
    total: int,
    state_counts: dict[str, int],
) -> None:
    SessionFactory = session_factory_for_settings(settings)
    with SessionFactory() as session:
        job = session.get(ScanJob, scan_job_id)
        if job is None:
            return
        job.progress_completed = completed
        job.progress_total = total
        job.state_counts = dict(state_counts)
        chunk = ScanResultChunk(
            scan_job_id=job.id,
            sequence=sequence,
            kind=kind,
            payload={"results": list(results), "state_counts": dict(state_counts)},
            probes_completed=completed,
            probes_total=total,
            emitted_at=utc_now(),
        )
        session.add(job)
        session.add(chunk)
        session.commit()
        session.refresh(job)
        session.refresh(chunk)
        await publish_scan_event(app, settings, "scan.result.chunk", public_scan_job(job), public_scan_chunk(chunk))


async def mark_scan_failed(app: Any, settings, scan_job_id: uuid.UUID, error_message: str) -> None:
    SessionFactory = session_factory_for_settings(settings)
    with SessionFactory() as session:
        job = session.get(ScanJob, scan_job_id)
        if job is None:
            return
        job.status = SCAN_STATUS_FAILED
        job.error_message = error_message[:1024]
        job.completed_at = utc_now()
        session.add(job)
        session.commit()
        session.refresh(job)
        await publish_scan_event(app, settings, "scan.result.failed", public_scan_job(job))


def mark_abandoned_scan_jobs(session: Session) -> list[ScanJob]:
    jobs = session.execute(select(ScanJob).where(ScanJob.status.in_([SCAN_STATUS_QUEUED, SCAN_STATUS_RUNNING]))).scalars()
    failed: list[ScanJob] = []
    for job in jobs:
        job.status = SCAN_STATUS_FAILED
        job.error_message = "Embedded scan job was interrupted by service restart."
        job.completed_at = utc_now()
        session.add(job)
        failed.append(job)
    return failed
