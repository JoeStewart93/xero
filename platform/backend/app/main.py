import asyncio
import uuid
from contextlib import asynccontextmanager, suppress
from secrets import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import authenticate_operator, public_operator, update_operator_password
from app.beacon_liveness import (
    BEACON_EVENT_REASON_HEARTBEAT,
    BEACON_STATUS_ONLINE,
    apply_runtime_metadata,
    publish_beacon_event,
    record_status_transition,
    run_beacon_stale_monitor,
)
from app.config import get_settings
from app.database import get_db_session, session_scope
from app.dependencies import auth_exception, enforce_operator_rate_limit, get_current_operator
from app.models import Beacon, User, utc_now
from app.readiness import check_readiness
from app.realtime import (
    OperatorRealtimeHub,
    authenticate_websocket,
    close_forbidden,
    close_unauthorized,
    run_operator_websocket,
    websocket_origin_allowed,
)
from app.redis_bus import close_redis, get_redis_client, initialize_redis, publish_operator_event
from app.schemas import (
    BeaconHeartbeatRequest,
    BeaconHeartbeatResponse,
    BeaconListResponse,
    BeaconRegistrationRequest,
    BeaconRegistrationResponse,
    BeaconResponse,
    C2ConnectRequest,
    C2ConnectResponse,
    C2SessionResponse,
    LoginRequest,
    OperatorResponse,
    PasswordChangeRequest,
    StatusResponse,
    TokenResponse,
)
from app.security import (
    AuthTokenError,
    create_access_token,
    create_c2_access_token,
    decode_access_token,
    decode_c2_access_token,
    generate_beacon_token,
    hash_beacon_token,
    verify_beacon_token,
    verify_password,
)

DbSession = Annotated[Session, Depends(get_db_session)]
CurrentOperator = Annotated[User, Depends(get_current_operator)]


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
        "first_seen": beacon.first_seen.isoformat(),
        "last_seen": beacon.last_seen.isoformat(),
    }


def require_c2_role(settings) -> None:
    if settings.service_role != "c2":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Xero service is not running as a C2 backend",
        )


def authorize_beacon_read(
    settings,
    authorization: str | None,
    session: Session,
) -> None:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise auth_exception()

    if settings.service_role == "c2":
        try:
            decode_c2_access_token(token, settings)
            return
        except AuthTokenError:
            raise auth_exception() from None

    try:
        claims = decode_access_token(token, settings)
        user = session.get(User, uuid.UUID(str(claims["operator_id"])))
    except (AuthTokenError, KeyError, ValueError):
        raise auth_exception() from None
    if user is None or user.username != claims.get("sub") or not user.is_enabled:
        raise auth_exception()


def beacon_auth_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing beacon token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def bearer_token(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise beacon_auth_exception()
    return token


def create_app() -> FastAPI:
    settings = get_settings()
    realtime_hub = OperatorRealtimeHub(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await initialize_redis(app, settings)
        app.state.operator_realtime_hub = realtime_hub
        stale_monitor_task: asyncio.Task[None] | None = None
        if settings.service_role == "c2" and settings.app_env.lower() != "test":
            await realtime_hub.start(getattr(app.state, "redis_client", None))
            stale_monitor_task = asyncio.create_task(run_beacon_stale_monitor(app, settings, public_beacon))
        try:
            yield
        finally:
            if stale_monitor_task is not None:
                stale_monitor_task.cancel()
                with suppress(asyncio.CancelledError):
                    await stale_monitor_task
            await realtime_hub.stop()
            await close_redis(app)

    app = FastAPI(title="Xero Core", version="0.1.0", lifespan=lifespan)
    app.state.operator_realtime_hub = realtime_hub

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

    @app.post("/auth/login", response_model=TokenResponse, tags=["auth"])
    def login(payload: LoginRequest, session: DbSession) -> TokenResponse:
        user = authenticate_operator(session, payload.username, payload.password)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token, expires_at = create_access_token(user, settings)
        return TokenResponse(
            access_token=token,
            expires_at=expires_at,
            operator=OperatorResponse(**public_operator(user)),
        )

    api_router = APIRouter(prefix=settings.api_v1_prefix)

    @app.websocket("/ws/operator")
    async def operator_websocket(websocket: WebSocket) -> None:
        if settings.service_role != "c2":
            await close_forbidden(websocket)
            return
        if not websocket_origin_allowed(websocket, settings):
            await close_forbidden(websocket)
            return

        with session_scope(settings) as session:
            authenticated = authenticate_websocket(websocket, settings, session)
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

    @api_router.post("/c2/connect", response_model=C2ConnectResponse, tags=["c2"])
    def connect_c2(payload: C2ConnectRequest) -> C2ConnectResponse:
        if settings.service_role != "c2":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Xero service is not running as a C2 backend",
            )
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
        require_c2_role(settings)
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing C2 authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            decode_c2_access_token(token, settings)
        except AuthTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing C2 authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None

        return C2SessionResponse(
            service=settings.service_name,
            service_role=settings.service_role,
            status="connected",
        )

    @api_router.post("/beacons/register", response_model=BeaconRegistrationResponse, tags=["beacons"])
    async def register_beacon(
        payload: BeaconRegistrationRequest,
        request: Request,
        session: DbSession,
    ) -> BeaconRegistrationResponse:
        require_c2_role(settings)
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
        require_c2_role(settings)
        beacon = session.get(Beacon, beacon_id)
        if beacon is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")

        if not verify_beacon_token(bearer_token(authorization), beacon.beacon_token_hash):
            raise beacon_auth_exception()

        now = utc_now()
        old_status = beacon.status
        apply_runtime_metadata(beacon, payload)
        beacon.status = BEACON_STATUS_ONLINE
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

    @api_router.get("/beacons", response_model=BeaconListResponse, tags=["beacons"])
    def list_beacons(
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
        status_filter: Annotated[str | None, Query(alias="status", pattern="^(online|offline)$")] = None,
    ) -> BeaconListResponse:
        authorize_beacon_read(settings, authorization, session)
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
        authorize_beacon_read(settings, authorization, session)
        beacon = session.get(Beacon, beacon_id)
        if beacon is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beacon not found")
        return BeaconResponse(**public_beacon(beacon))

    app.include_router(api_router)

    protected_router = APIRouter(
        prefix=settings.api_v1_prefix,
        tags=["operator"],
        dependencies=[Depends(enforce_operator_rate_limit)],
        responses={429: {"description": "Rate limit exceeded"}},
    )

    @protected_router.get("/health", tags=["health"])
    def api_health(_: CurrentOperator) -> dict[str, str]:
        return liveness_payload()

    @protected_router.get("/ready", tags=["health"])
    def api_ready(_: CurrentOperator) -> JSONResponse:
        report = check_readiness(settings)
        status_code = 200 if report["status"] == "ready" else 503
        return JSONResponse(status_code=status_code, content=report)

    @protected_router.get("/me", response_model=OperatorResponse)
    def current_operator(user: CurrentOperator) -> OperatorResponse:
        return OperatorResponse(**public_operator(user))

    @protected_router.post("/auth/password", response_model=StatusResponse)
    def change_password(
        payload: PasswordChangeRequest,
        user: CurrentOperator,
        session: DbSession,
    ) -> StatusResponse:
        if not verify_password(payload.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        managed_user = session.get(User, user.id)
        if managed_user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Operator no longer exists")

        update_operator_password(session, managed_user, payload.new_password, settings)
        return StatusResponse(status="ok")

    app.include_router(protected_router)
    return app


app = create_app()
