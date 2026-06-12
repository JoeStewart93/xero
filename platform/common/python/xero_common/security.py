from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from jwt import InvalidTokenError, PyJWTError

JWT_ALGORITHM = "HS256"
MAX_BCRYPT_PASSWORD_BYTES = 72
ALLOWED_TOKEN_ROLES = {"admin", "operator"}
C2_TOKEN_KIND = "c2-connect"
OPAQUE_TOKEN_HASH_PREFIX = "sha256:"


class AuthTokenError(ValueError):
    pass


def _password_bytes(password: str) -> bytes:
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_BCRYPT_PASSWORD_BYTES:
        raise ValueError("Password is too long for bcrypt")
    return encoded


def hash_password(password: str, *, rounds: int = 12) -> str:
    password_bytes = _password_bytes(password)
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=rounds)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        password_bytes = _password_bytes(password)
        return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user: Any, settings: Any, *, now: datetime | None = None) -> tuple[str, datetime]:
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.jwt_expires_minutes)
    payload: dict[str, Any] = {
        "sub": user.username,
        "operator_id": str(user.id),
        "role": user.role,
        "iat": issued_at,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)
    return token, expires_at


def decode_access_token(token: str, settings: Any) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "operator_id", "exp"]},
        )
    except (InvalidTokenError, PyJWTError) as exc:
        raise AuthTokenError("Invalid authentication token") from exc

    if claims.get("role") not in ALLOWED_TOKEN_ROLES:
        raise AuthTokenError("Invalid authentication token")

    return claims


def create_c2_access_token(settings: Any, *, now: datetime | None = None) -> tuple[str, datetime]:
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.c2_token_expires_minutes)
    payload: dict[str, Any] = {
        "sub": "xero-ui-client",
        "kind": C2_TOKEN_KIND,
        "service": settings.service_name,
        "role": settings.service_role,
        "iat": issued_at,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)
    return token, expires_at


def decode_c2_access_token(token: str, settings: Any) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "kind", "exp"]},
        )
    except (InvalidTokenError, PyJWTError) as exc:
        raise AuthTokenError("Invalid C2 authentication token") from exc

    if claims.get("kind") != C2_TOKEN_KIND:
        raise AuthTokenError("Invalid C2 authentication token")

    return claims


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_opaque_token(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{OPAQUE_TOKEN_HASH_PREFIX}{digest}"


def verify_opaque_token(token: str, token_hash: str) -> bool:
    return secrets.compare_digest(hash_opaque_token(token), token_hash)


def generate_beacon_token() -> str:
    return generate_opaque_token()


def hash_beacon_token(token: str) -> str:
    return hash_opaque_token(token)


def verify_beacon_token(token: str, token_hash: str) -> bool:
    return verify_opaque_token(token, token_hash)
