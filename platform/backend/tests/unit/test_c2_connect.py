import pytest
from app.config import get_settings
from app.main import create_app
from app.security import AuthTokenError, decode_c2_access_token
from fastapi.testclient import TestClient


def c2_client(monkeypatch) -> TestClient:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("XERO_SERVICE_NAME", "xero-c2-core")
    monkeypatch.setenv("XERO_SERVICE_ROLE", "c2")
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "connect-me")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-c2-jwt-secret-with-enough-length")
    return TestClient(create_app())


def test_c2_connect_rejects_non_c2_service_role(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("XERO_SERVICE_NAME", "xero-bff")
    monkeypatch.setenv("XERO_SERVICE_ROLE", "bff")
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "connect-me")

    client = TestClient(create_app())
    response = client.post("/api/v1/c2/connect", json={"password": "connect-me"})

    assert response.status_code == 409
    assert response.json()["detail"] == "This Xero service is not running as a C2 backend"


def test_c2_connect_rejects_invalid_password(monkeypatch):
    client = c2_client(monkeypatch)

    response = client.post("/api/v1/c2/connect", json={"password": "wrong"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid C2 connection password"


def test_c2_connect_returns_c2_session_token(monkeypatch):
    client = c2_client(monkeypatch)

    response = client.post("/api/v1/c2/connect", json={"password": "connect-me"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["service"] == "xero-c2-core"
    assert payload["service_role"] == "c2"
    assert payload["status"] == "connected"

    claims = decode_c2_access_token(payload["access_token"], get_settings())
    assert claims["sub"] == "xero-ui-client"
    assert claims["kind"] == "c2-connect"


def test_c2_session_requires_valid_token(monkeypatch):
    client = c2_client(monkeypatch)

    missing = client.get("/api/v1/c2/session")
    assert missing.status_code == 401

    login = client.post("/api/v1/c2/connect", json={"password": "connect-me"})
    token = login.json()["access_token"]
    response = client.get("/api/v1/c2/session", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {
        "service": "xero-c2-core",
        "service_role": "c2",
        "status": "connected",
    }


def test_c2_token_decoder_rejects_operator_tokens(monkeypatch):
    c2_client(monkeypatch)

    with pytest.raises(AuthTokenError):
        decode_c2_access_token("not-a-token", get_settings())
