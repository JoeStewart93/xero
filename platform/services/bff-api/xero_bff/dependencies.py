from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from xero_common.database import session_factory_for_settings
from xero_common.redis_bus import check_rate_limit, get_redis_client, rate_limit_key
from xero_common.security import AuthTokenError, decode_access_token

from xero_bff.config import get_settings
from xero_bff.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
AuthToken = Annotated[str | None, Depends(oauth2_scheme)]


def get_db_session():
    settings = get_settings()
    SessionFactory = session_factory_for_settings(settings)
    with SessionFactory() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db_session)]


def auth_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_operator(
    token: AuthToken,
    session: DbSession,
) -> User:
    if not token:
        raise auth_exception()

    settings = get_settings()
    try:
        claims = decode_access_token(token, settings)
        operator_id = uuid.UUID(str(claims["operator_id"]))
    except (AuthTokenError, KeyError, ValueError):
        raise auth_exception() from None

    user = session.get(User, operator_id)
    if user is None or user.username != claims.get("sub") or not user.is_enabled:
        raise auth_exception()
    return user


async def enforce_operator_rate_limit(
    request: Request,
    user: Annotated[User, Depends(get_current_operator)],
) -> None:
    settings = get_settings()
    if not settings.redis_rate_limit_enabled:
        return

    route = request.scope.get("route")
    route_family = getattr(route, "path", request.url.path)
    result = await check_rate_limit(
        get_redis_client(request),
        key=rate_limit_key(user.id, route_family),
        limit=settings.redis_rate_limit_requests,
        window_seconds=settings.redis_rate_limit_window_seconds,
    )
    if result.allowed:
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded",
        headers={"Retry-After": str(result.retry_after_seconds)},
    )
