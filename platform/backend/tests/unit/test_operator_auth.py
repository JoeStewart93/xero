from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app import dependencies as dependencies_module
from app import main as main_module
from app.auth import ensure_seed_operator
from app.config import DEV_OPERATOR_PASSWORD, get_settings
from app.database import clear_database_caches, get_engine, get_session_factory
from app.main import create_app
from app.models import Base, User
from app.redis_bus import RateLimitResult
from app.security import AuthTokenError, create_access_token, decode_access_token, hash_password, verify_password
from fastapi.testclient import TestClient
from sqlalchemy import select


@pytest.fixture
def auth_client(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'auth.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("OPERATOR_USERNAME", "operator")
    monkeypatch.setenv("OPERATOR_PASSWORD", DEV_OPERATOR_PASSWORD)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-with-enough-length")
    monkeypatch.setenv("JWT_EXPIRES_MINUTES", "60")
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    get_settings.cache_clear()
    clear_database_caches()

    Base.metadata.create_all(bind=get_engine(database_url))
    ensure_seed_operator(get_settings())

    with TestClient(create_app()) as client:
        yield client

    get_settings.cache_clear()
    clear_database_caches()


def login(client: TestClient, username: str = "operator", password: str = DEV_OPERATOR_PASSWORD) -> str:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_password_hash_and_verify_bcrypt_round_trip():
    password_hash = hash_password("correct horse battery staple", rounds=4)

    assert password_hash != "correct horse battery staple"
    assert password_hash.startswith("$2")
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong", password_hash)


def test_jwt_create_and_decode_with_expiration(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'jwt.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-with-enough-length")
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(database_url))
    settings = get_settings()
    ensure_seed_operator(settings)

    SessionFactory = get_session_factory(database_url)
    with SessionFactory() as session:
        user = session.execute(select(User).where(User.username == "operator")).scalar_one()
        token, expires_at = create_access_token(user, settings)

    claims = decode_access_token(token, settings)
    assert claims["sub"] == "operator"
    assert claims["role"] == "operator"
    assert claims["exp"] == int(expires_at.timestamp())

    with SessionFactory() as session:
        user = session.execute(select(User).where(User.username == "operator")).scalar_one()
        expired_token, _ = create_access_token(user, settings, now=datetime.now(UTC) - timedelta(minutes=61))

    with pytest.raises(AuthTokenError):
        decode_access_token(expired_token, settings)


def test_seed_creates_enabled_local_admin(auth_client):
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)

    with SessionFactory() as session:
        admin = session.execute(select(User).where(User.username == "admin")).scalar_one()

    assert admin.role == "admin"
    assert admin.is_enabled is True
    assert verify_password("admin", admin.password_hash)


def test_login_invalid_credentials_returns_401(auth_client):
    response = auth_client.post("/auth/login", json={"username": "operator", "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_valid_login_returns_jwt_with_expiration(auth_client):
    response = auth_client.post("/auth/login", json={"username": "operator", "password": DEV_OPERATOR_PASSWORD})

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["expires_at"]
    assert payload["operator"]["username"] == "operator"
    assert payload["operator"]["role"] == "operator"
    assert payload["operator"]["is_enabled"] is True
    assert "password" not in payload["operator"]


def test_default_local_admin_can_login(auth_client):
    response = auth_client.post("/auth/login", json={"username": "admin", "password": "admin"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["operator"]["username"] == "admin"
    assert payload["operator"]["role"] == "admin"
    assert payload["operator"]["is_enabled"] is True

    settings = get_settings()
    claims = decode_access_token(payload["access_token"], settings)
    assert claims["sub"] == "admin"
    assert claims["role"] == "admin"


def test_disabled_user_cannot_login(auth_client):
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        admin = session.execute(select(User).where(User.username == "admin")).scalar_one()
        admin.is_enabled = False
        session.add(admin)
        session.commit()

    response = auth_client.post("/auth/login", json={"username": "admin", "password": "admin"})

    assert response.status_code == 401


def test_protected_route_requires_token(auth_client):
    response = auth_client.get("/api/v1/beacons")

    assert response.status_code == 401


def test_valid_token_grants_access_to_protected_endpoint(auth_client):
    token = login(auth_client)

    response = auth_client.get("/api/v1/beacons", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_protected_route_returns_429_when_rate_limited(auth_client, monkeypatch):
    async def blocked_rate_limit(*_, **__):
        return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=17)

    monkeypatch.setattr(dependencies_module, "check_rate_limit", blocked_rate_limit)
    monkeypatch.setattr(dependencies_module, "get_redis_client", lambda _: object())
    token = login(auth_client)

    response = auth_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 429
    assert response.headers["retry-after"] == "17"
    assert response.json() == {"detail": "Rate limit exceeded"}


def test_valid_token_grants_access_to_protected_health_and_readiness(auth_client, monkeypatch):
    def healthy_readiness(_):
        return {
            "status": "ready",
            "service": "xero-core",
            "checks": {
                "postgres": {"status": "healthy"},
                "redis": {"status": "healthy"},
            },
        }

    monkeypatch.setattr(main_module, "check_readiness", healthy_readiness)
    token = login(auth_client)
    headers = {"Authorization": f"Bearer {token}"}

    health_response = auth_client.get("/api/v1/health", headers=headers)
    readiness_response = auth_client.get("/api/v1/ready", headers=headers)

    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"
    assert health_response.json()["service"] == "xero-core"
    assert readiness_response.status_code == 200
    assert readiness_response.json()["checks"]["postgres"]["status"] == "healthy"


def test_disabled_user_token_is_rejected(auth_client):
    token = login(auth_client, username="admin", password="admin")
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        admin = session.execute(select(User).where(User.username == "admin")).scalar_one()
        admin.is_enabled = False
        session.add(admin)
        session.commit()

    response = auth_client.get("/api/v1/beacons", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_password_change_updates_hash_without_plaintext(auth_client):
    token = login(auth_client)
    response = auth_client.post(
        "/api/v1/auth/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": DEV_OPERATOR_PASSWORD, "new_password": "new_operator_password"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    old_login = auth_client.post("/auth/login", json={"username": "operator", "password": DEV_OPERATOR_PASSWORD})
    new_login = auth_client.post("/auth/login", json={"username": "operator", "password": "new_operator_password"})
    assert old_login.status_code == 401
    assert new_login.status_code == 200

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        user = session.execute(select(User).where(User.username == "operator")).scalar_one()
        assert user.password_hash != "new_operator_password"
        assert verify_password("new_operator_password", user.password_hash)
