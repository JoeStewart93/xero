from __future__ import annotations

import asyncio
import ipaddress
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from xero_common.database import session_factory_for_settings
from xero_common.models import utc_now
from xero_common.redis_bus import publish_operator_event

from xero_c2.infrastructure_workers import WORKER_KIND_SCANNER, WORKER_ORIGIN_EMBEDDED, WORKER_STATUS_ONLINE
from xero_c2.models import InfrastructureWorker, ScanJob, ScanResultChunk

PORTSCAN_MODULE_ID = "builtin.portscan"
SCAN_STATUS_QUEUED = "queued"
SCAN_STATUS_RUNNING = "running"
SCAN_STATUS_COMPLETED = "completed"
SCAN_STATUS_FAILED = "failed"
SCAN_TERMINAL_STATUSES = {SCAN_STATUS_COMPLETED, SCAN_STATUS_FAILED}
SCAN_PROGRESS_BATCH_SIZE = 100
MAX_TARGET_ENTRIES = 10
MAX_EXPANDED_HOSTS = 256
MAX_TOTAL_PROBES = 65_535
IpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IpNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


class PortScanArgs(BaseModel):
    targets: list[str] = Field(min_length=1, max_length=MAX_TARGET_ENTRIES)
    port_range: str = Field(min_length=1, max_length=512)
    timeout_ms: int = Field(default=1000, ge=50, le=60_000)
    max_threads: int = Field(default=64, ge=1, le=256)
    execution_target: str = "auto"

    @field_validator("execution_target")
    @classmethod
    def validate_execution_target(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized != "auto":
            raise ValueError("F0022 supports execution_target=auto only")
        return normalized

    @field_validator("targets")
    @classmethod
    def normalize_targets(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if not normalized:
            raise ValueError("At least one target is required")
        if len(normalized) > MAX_TARGET_ENTRIES:
            raise ValueError(f"At most {MAX_TARGET_ENTRIES} target entries are allowed")
        return normalized

    @field_validator("port_range")
    @classmethod
    def normalize_port_range(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("port_range cannot be blank")
        parse_ports(normalized)
        return normalized

    @model_validator(mode="after")
    def validate_probe_budget(self) -> PortScanArgs:
        hosts = expand_targets(self.targets)
        ports = parse_ports(self.port_range)
        total = len(hosts) * len(ports)
        if total > MAX_TOTAL_PROBES:
            raise ValueError(f"Scan probe budget exceeds {MAX_TOTAL_PROBES}")
        return self


@dataclass(frozen=True)
class Probe:
    host: str
    port: int


def parse_ports(value: str) -> list[int]:
    ports: set[int] = set()
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            raw_start, raw_end = part.split("-", 1)
            try:
                start = int(raw_start.strip())
                end = int(raw_end.strip())
            except ValueError as exc:
                raise ValueError("port_range contains an invalid range") from exc
            if end < start:
                raise ValueError("port_range cannot contain descending ranges")
            for port in range(start, end + 1):
                _validate_port(port)
                ports.add(port)
        else:
            try:
                port = int(part)
            except ValueError as exc:
                raise ValueError("port_range contains an invalid port") from exc
            _validate_port(port)
            ports.add(port)
    if not ports:
        raise ValueError("port_range must include at least one port")
    return sorted(ports)


def _validate_port(port: int) -> None:
    if port < 1 or port > 65_535:
        raise ValueError("Ports must be between 1 and 65535")


def expand_targets(targets: list[str]) -> list[str]:
    expanded: list[str] = []
    for target in targets:
        expanded.extend(_expand_target(target))
        if len(expanded) > MAX_EXPANDED_HOSTS:
            raise ValueError(f"Target expansion exceeds {MAX_EXPANDED_HOSTS} hosts")
    seen: set[str] = set()
    unique: list[str] = []
    for host in expanded:
        if host not in seen:
            seen.add(host)
            unique.append(host)
    return unique


def _expand_target(target: str) -> list[str]:
    normalized = target.strip().lower()
    if normalized == "localhost":
        return ["127.0.0.1"]
    try:
        network = ipaddress.ip_network(normalized, strict=False)
    except ValueError:
        try:
            address = ipaddress.ip_address(normalized)
        except ValueError as exc:
            raise ValueError("Targets must be loopback/private/link-local IPs, CIDRs, or localhost") from exc
        _validate_scoped_address(address)
        return [str(address)]
    _validate_scoped_network(network)
    if network.prefixlen == network.max_prefixlen:
        return [str(network.network_address)]
    return [str(address) for address in network.hosts()]


def _validate_scoped_network(network: IpNetwork) -> None:
    for address in (network.network_address, network.broadcast_address):
        _validate_scoped_address(address)


def _validate_scoped_address(address: IpAddress) -> None:
    if address.is_loopback or address.is_private or address.is_link_local:
        return
    raise ValueError("Public targets are rejected until backend project scope enforcement exists")


def normalized_portscan_args(raw_args: dict[str, Any]) -> dict[str, Any]:
    args = PortScanArgs.model_validate(raw_args)
    return args.model_dump()


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


async def publish_scan_event(app: Any, settings, event_type: str, job_payload: dict[str, Any], chunk_payload: dict[str, Any] | None = None) -> None:
    data: dict[str, Any] = {"scan_job": job_payload}
    if chunk_payload is not None:
        data["scan_chunk"] = chunk_payload
    redis_client = getattr(app.state, "redis_client", None)
    event = await publish_operator_event(
        redis_client,
        settings,
        event_type,
        data=data,
        scope={"scan_job_id": job_payload["id"]},
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
    if module != PORTSCAN_MODULE_ID:
        raise ValueError("Unsupported scan module")
    args = normalized_portscan_args(raw_args)
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
        progress_total=len(expand_targets(args["targets"])) * len(parse_ports(args["port_range"])),
        state_counts={"closed": 0, "filtered": 0, "open": 0},
        status=SCAN_STATUS_QUEUED,
        worker_id=worker.id,
    )
    session.add(job)
    return job


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
            args = PortScanArgs.model_validate(job.args)

        hosts = expand_targets(args.targets)
        ports = parse_ports(args.port_range)
        probes = [Probe(host, port) for host in hosts for port in ports]
        state_counts = {"closed": 0, "filtered": 0, "open": 0}
        all_results: list[dict[str, Any]] = []
        pending_results: list[dict[str, Any]] = []
        completed = 0
        sequence = 0
        semaphore = asyncio.Semaphore(args.max_threads)

        async def bounded_probe(probe: Probe) -> dict[str, Any]:
            async with semaphore:
                return await probe_tcp_connect(probe.host, probe.port, timeout_ms=args.timeout_ms)

        for future in asyncio.as_completed([bounded_probe(probe) for probe in probes]):
            result = await future
            completed += 1
            state_counts[result["state"]] += 1
            all_results.append(result)
            pending_results.append(result)
            if len(pending_results) >= SCAN_PROGRESS_BATCH_SIZE:
                sequence += 1
                await persist_scan_progress(
                    app,
                    settings,
                    scan_job_id,
                    sequence=sequence,
                    kind="progress",
                    results=pending_results,
                    completed=completed,
                    total=len(probes),
                    state_counts=state_counts,
                )
                pending_results = []

        if pending_results:
            sequence += 1
            await persist_scan_progress(
                app,
                settings,
                scan_job_id,
                sequence=sequence,
                kind="progress",
                results=pending_results,
                completed=completed,
                total=len(probes),
                state_counts=state_counts,
            )

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        summary = {
            "duration_ms": duration_ms,
            "hosts_scanned": len(hosts),
            "open_count": state_counts["open"],
            "ports_scanned": len(probes),
            "state_counts": state_counts,
        }
        all_results.sort(key=lambda item: (item["host"], item["port"]))
        with SessionFactory() as session:
            job = session.get(ScanJob, scan_job_id)
            if job is None:
                return
            job.status = SCAN_STATUS_COMPLETED
            job.progress_completed = len(probes)
            job.progress_total = len(probes)
            job.state_counts = dict(state_counts)
            job.summary = summary
            job.results = all_results
            job.completed_at = utc_now()
            session.add(job)
            session.flush()
            summary_chunk = ScanResultChunk(
                scan_job_id=job.id,
                sequence=sequence + 1,
                kind="summary",
                payload={"results": all_results, "summary": summary},
                probes_completed=len(probes),
                probes_total=len(probes),
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


async def probe_tcp_connect(host: str, port: int, *, timeout_ms: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout_ms / 1000)
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()
        state = "open"
    except TimeoutError:
        state = "filtered"
    except (ConnectionRefusedError, ConnectionResetError):
        state = "closed"
    except OSError as exc:
        state = "closed" if _is_refused_error(exc) else "filtered"
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    return {"host": host, "latency_ms": latency_ms, "port": port, "state": state}


def _is_refused_error(exc: OSError) -> bool:
    refused_codes = {10061, 111, 61}
    errno = getattr(exc, "errno", None)
    winerror = getattr(exc, "winerror", None)
    return errno in refused_codes or winerror in refused_codes


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
