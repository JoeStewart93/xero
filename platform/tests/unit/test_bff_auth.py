from __future__ import annotations

import pytest
from sqlalchemy import select
from xero_bff import dependencies as dependencies_module
from xero_bff.auth import ensure_seed_users
from xero_bff.config import DEV_OPERATOR_PASSWORD, get_settings
from xero_bff.models import Base, User
from xero_common.database import clear_database_caches, get_engine, get_session_factory
from xero_common.redis_bus import RateLimitResult
from xero_common.security import decode_access_token, verify_password


@pytest.fixture
def auth_client(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'bff-auth.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("OPERATOR_USERNAME", "operator")
    monkeypatch.setenv("OPERATOR_PASSWORD", DEV_OPERATOR_PASSWORD)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-with-enough-length")
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    get_settings.cache_clear()
    clear_database_caches()

    Base.metadata.create_all(bind=get_engine(database_url))
    ensure_seed_users(get_settings())
    return None


def login(client, username: str = "operator", password: str = DEV_OPERATOR_PASSWORD) -> str:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_default_admin_and_operator_can_login(auth_client, make_bff_client):
    client = make_bff_client()

    operator = client.post("/auth/login", json={"username": "operator", "password": DEV_OPERATOR_PASSWORD})
    admin = client.post("/auth/login", json={"username": "admin", "password": "admin"})

    assert operator.status_code == 200
    assert operator.json()["operator"]["role"] == "operator"
    assert admin.status_code == 200
    assert admin.json()["operator"]["role"] == "admin"


def test_login_rejects_invalid_or_disabled_users(auth_client, make_bff_client):
    client = make_bff_client()
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        admin = session.execute(select(User).where(User.username == "admin")).scalar_one()
        admin.is_enabled = False
        session.add(admin)
        session.commit()

    assert client.post("/auth/login", json={"username": "operator", "password": "wrong"}).status_code == 401
    assert client.post("/auth/login", json={"username": "admin", "password": "admin"}).status_code == 401


def test_valid_token_grants_access_to_me_and_health(auth_client, make_bff_client, monkeypatch):
    client = make_bff_client()
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    def healthy_readiness(_):
        return {
            "status": "ready",
            "service": "xero-bff",
            "checks": {
                "postgres": {"status": "healthy"},
                "redis": {"status": "healthy"},
            },
        }

    monkeypatch.setattr("xero_bff.main.check_readiness", healthy_readiness)

    me = client.get("/api/v1/me", headers=headers)
    health = client.get("/api/v1/health", headers=headers)
    ready = client.get("/api/v1/ready", headers=headers)

    assert me.status_code == 200
    assert me.json()["username"] == "operator"
    assert health.status_code == 200
    assert health.json()["role"] == "bff"
    assert ready.status_code == 200


def test_password_change_updates_hash(auth_client, make_bff_client):
    client = make_bff_client()
    token = login(client)
    response = client.post(
        "/api/v1/auth/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": DEV_OPERATOR_PASSWORD, "new_password": "new_operator_password"},
    )

    assert response.status_code == 200
    old_login = client.post("/auth/login", json={"username": "operator", "password": DEV_OPERATOR_PASSWORD})
    new_login = client.post("/auth/login", json={"username": "operator", "password": "new_operator_password"})

    assert old_login.status_code == 401
    assert new_login.status_code == 200

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        user = session.execute(select(User).where(User.username == "operator")).scalar_one()
        assert verify_password("new_operator_password", user.password_hash)


def test_rate_limited_operator_route_returns_429(auth_client, make_bff_client, monkeypatch):
    async def blocked_rate_limit(*_, **__):
        return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=17)

    monkeypatch.setattr(dependencies_module, "check_rate_limit", blocked_rate_limit)
    monkeypatch.setattr(dependencies_module, "get_redis_client", lambda _: object())
    client = make_bff_client()
    token = login(client)

    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 429
    assert response.headers["retry-after"] == "17"


def test_bff_jwt_contains_operator_claims(auth_client, make_bff_client):
    client = make_bff_client()
    token = login(client, username="admin", password="admin")

    claims = decode_access_token(token, get_settings())

    assert claims["sub"] == "admin"
    assert claims["role"] == "admin"
    assert claims["operator_id"]
