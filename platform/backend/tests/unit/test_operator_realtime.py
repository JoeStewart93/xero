from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from app.config import get_settings
from app.database import clear_database_caches, get_engine, session_scope
from app.main import create_app
from app.models import Base, Beacon
from app.realtime import (
    WS_CLOSE_FORBIDDEN,
    WS_CLOSE_UNAUTHORIZED,
    decode_operator_event,
    operator_events_broadcast_channel,
)
from app.redis_bus import build_operator_event
from app.security import hash_beacon_token
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect


@pytest.fixture
def c2_client(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'c2.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("XERO_SERVICE_NAME", "xero-c2-core")
    monkeypatch.setenv("XERO_SERVICE_ROLE", "c2")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-with-enough-length")
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "c2_password")
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(database_url))

    with TestClient(create_app()) as client:
        yield client

    get_settings.cache_clear()
    clear_database_caches()


@pytest.fixture
def c2_client_custom_defaults(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'c2-custom.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("XERO_SERVICE_NAME", "xero-c2-core")
    monkeypatch.setenv("XERO_SERVICE_ROLE", "c2")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-with-enough-length")
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "c2_password")
    monkeypatch.setenv("BEACON_DEFAULT_SLEEP_SECONDS", "45")
    monkeypatch.setenv("BEACON_DEFAULT_JITTER", "0.25")
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(database_url))

    with TestClient(create_app()) as client:
        yield client

    get_settings.cache_clear()
    clear_database_caches()


@pytest.fixture
def bff_client(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'bff.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("XERO_SERVICE_NAME", "xero-core")
    monkeypatch.setenv("XERO_SERVICE_ROLE", "bff")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-with-enough-length")
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(database_url))

    with TestClient(create_app()) as client:
        yield client

    get_settings.cache_clear()
    clear_database_caches()


def c2_token(client: TestClient) -> str:
    response = client.post("/api/v1/c2/connect", json={"password": "c2_password"})
    assert response.status_code == 200
    return response.json()["access_token"]


def register_payload(**overrides):
    payload = {
        "machine_fingerprint_hash": "fingerprint-001",
        "hostname": "workstation-01",
        "os": "Windows 11",
        "architecture": "x64",
        "internal_ip": "10.0.0.5",
        "external_ip": "198.51.100.10",
        "pid": 4242,
    }
    payload.update(overrides)
    return payload


def test_ws_rejects_unauthenticated_connection(c2_client):
    with pytest.raises(WebSocketDisconnect) as exc:
        with c2_client.websocket_connect("/ws/operator"):
            pass

    assert exc.value.code == WS_CLOSE_UNAUTHORIZED


def test_ws_rejects_non_c2_service_role(bff_client):
    with pytest.raises(WebSocketDisconnect) as exc:
        with bff_client.websocket_connect("/ws/operator"):
            pass

    assert exc.value.code == WS_CLOSE_FORBIDDEN


def test_ws_accepts_valid_c2_jwt_query_param(c2_client):
    token = c2_token(c2_client)

    with c2_client.websocket_connect(f"/ws/operator?access_token={token}") as websocket:
        assert websocket.receive_json()["type"] == "realtime.connected"
        assert c2_client.app.state.operator_realtime_hub.registry.active_count == 1

    assert c2_client.app.state.operator_realtime_hub.registry.active_count == 0


def test_ws_accepts_valid_c2_jwt_header(c2_client):
    token = c2_token(c2_client)

    with c2_client.websocket_connect("/ws/operator", headers={"Authorization": f"Bearer {token}"}) as websocket:
        assert websocket.receive_json()["type"] == "realtime.connected"


def test_ws_rejects_expired_c2_token(c2_client):
    settings = get_settings()
    now = datetime.now(UTC)
    expired_token = jwt.encode(
        {
            "sub": "xero-ui-client",
            "kind": "c2-connect",
            "service": settings.service_name,
            "role": settings.service_role,
            "iat": now - timedelta(minutes=20),
            "exp": now - timedelta(minutes=10),
        },
        settings.jwt_secret_key,
        algorithm="HS256",
    )

    with pytest.raises(WebSocketDisconnect) as exc:
        with c2_client.websocket_connect(f"/ws/operator?access_token={expired_token}"):
            pass

    assert exc.value.code == WS_CLOSE_UNAUTHORIZED


@pytest.mark.parametrize(
    ("event_type", "data", "scope"),
    [
        ("beacon.status.changed", {"beacon": {"id": "beacon-1", "status": "online"}}, {"beacon_id": "beacon-1"}),
        ("task.result.completed", {"task_id": "task-1", "status": "completed"}, {"task_id": "task-1"}),
        ("session.output.received", {"session_id": "session-1", "chunk": "whoami"}, {"session_id": "session-1"}),
    ],
)
def test_operator_event_decoder_accepts_supported_event_envelopes(event_type, data, scope):
    settings = get_settings()
    event = build_operator_event(settings, event_type, data=data, scope=scope)

    assert operator_events_broadcast_channel() == "events:operator"
    assert decode_operator_event(json.dumps(event)) == event


def test_operator_event_decoder_drops_malformed_payloads():
    assert decode_operator_event("not-json") is None
    assert decode_operator_event('{"version":1}') is None


def test_register_new_beacon_creates_record_and_lists_for_c2(c2_client):
    token = c2_token(c2_client)

    register_response = c2_client.post("/api/v1/beacons/register", json=register_payload())

    assert register_response.status_code == 200
    payload = register_response.json()
    assert payload["beacon_id"]
    assert payload["beacon_token"]
    assert payload["sleep"] == 30
    assert payload["jitter"] == 0.1
    assert payload["beacon"]["hostname"] == "workstation-01"
    assert "beacon_token" not in payload["beacon"]

    list_response = c2_client.get("/api/v1/beacons", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    listed = list_response.json()["items"][0]
    assert len(list_response.json()["items"]) == 1
    assert listed["id"] == payload["beacon_id"]
    assert "beacon_token" not in listed
    assert "beacon_token_hash" not in listed

    with session_scope(get_settings()) as session:
        beacon = session.get(Beacon, uuid.UUID(payload["beacon_id"]))
        assert beacon is not None
        assert beacon.beacon_token_hash == hash_beacon_token(payload["beacon_token"])
        assert beacon.beacon_token_issued_at is not None


def test_register_duplicate_fingerprint_updates_existing(c2_client):
    first = c2_client.post("/api/v1/beacons/register", json=register_payload())
    second = c2_client.post(
        "/api/v1/beacons/register",
        json=register_payload(hostname="workstation-renamed", internal_ip="10.0.0.6"),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["beacon_id"] == first.json()["beacon_id"]
    assert second.json()["beacon_token"] != first.json()["beacon_token"]

    token = c2_token(c2_client)
    list_response = c2_client.get("/api/v1/beacons", headers={"Authorization": f"Bearer {token}"})

    assert len(list_response.json()["items"]) == 1
    assert list_response.json()["items"][0]["hostname"] == "workstation-renamed"
    assert list_response.json()["items"][0]["internal_ip"] == "10.0.0.6"

    with session_scope(get_settings()) as session:
        beacon = session.execute(
            select(Beacon).where(Beacon.machine_fingerprint_hash == "fingerprint-001")
        ).scalar_one()
        assert beacon.beacon_token_hash == hash_beacon_token(second.json()["beacon_token"])
        assert beacon.beacon_token_hash != hash_beacon_token(first.json()["beacon_token"])


def test_register_invalid_payload_returns_422(c2_client):
    response = c2_client.post(
        "/api/v1/beacons/register",
        json=register_payload(machine_fingerprint_hash="short", pid=-1),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [
        {"internal_ip": "10.0.0.999"},
        {"external_ip": "198.51.100.999"},
        {"hostname": "   "},
    ],
)
def test_register_invalid_metadata_returns_422(c2_client, overrides):
    response = c2_client.post("/api/v1/beacons/register", json=register_payload(**overrides))

    assert response.status_code == 422


def test_registration_response_uses_configured_communication_defaults(c2_client_custom_defaults):
    response = c2_client_custom_defaults.post("/api/v1/beacons/register", json=register_payload())

    assert response.status_code == 200
    assert response.json()["sleep"] == 45
    assert response.json()["jitter"] == 0.25
