from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from xero_common.security import verify_beacon_token

from xero_c2.models import Beacon


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


def find_authenticated_beacon(session: Session, beacon_id: uuid.UUID, token: str | None) -> Beacon | None:
    if not token:
        return None
    beacon = session.get(Beacon, beacon_id)
    if beacon is None or not verify_beacon_token(token, beacon.beacon_token_hash):
        return None
    if beacon.removed_at is not None:
        return None
    return beacon
