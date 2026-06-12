from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from xero_common.readiness import check_readiness
from xero_common.redis_bus import close_redis, initialize_redis
from xero_common.security import create_access_token, verify_password

from xero_bff.auth import authenticate_operator, public_operator, update_operator_password
from xero_bff.config import get_settings
from xero_bff.dependencies import enforce_operator_rate_limit, get_current_operator, get_db_session
from xero_bff.models import User
from xero_bff.schemas import LoginRequest, OperatorResponse, PasswordChangeRequest, StatusResponse, TokenResponse

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


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await initialize_redis(app, settings)
        try:
            yield
        finally:
            await close_redis(app)

    app = FastAPI(title="Xero BFF API", version="0.1.0", lifespan=lifespan)

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
