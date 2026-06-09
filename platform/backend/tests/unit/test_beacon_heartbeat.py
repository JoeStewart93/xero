from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from app.beacon_liveness import BEACON_STATUS_OFFLINE, mark_stale_beacons_offline
from app.config import get_settings
from app.database import clear_database_caches, get_engine, session_scope
from app.main import create_app
from app.models import Base, Beacon, BeaconEvent, utc_now
from fastapi.testclient import TestClient
from sqlalchemy import select


@pytest.fixture
def c2_client(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'heartbeat-c2.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("XERO_SERVICE_NAME", "xero-c2-core")
    monkeypatch.setenv("XERO_SERVICE_ROLE", "c2")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-with-enough-length")
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "c2_password")
    monkeypatch.setenv("BEACON_HEARTBEAT_CHECK_INTERVAL_SECONDS", "1")
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
        "machine_fingerprint_hash": f"heartbeat-fingerprint-{uuid.uuid4()}",
        "hostname": "heartbeat-host",
        "os": "Windows 11",
        "architecture": "x64",
        "internal_ip": "10.30.0.5",
        "external_ip": "198.51.100.30",
        "pid": 3030,
    }
    payload.update(overrides)
    return payload


def register_beacon(client: TestClient, **overrides) -> dict:
    response = client.post("/api/v1/beacons/register", json=register_payload(**overrides))
    assert response.status_code == 200
    return response.json()


def test_heartbeat_updates_last_seen_metadata_and_emits_heartbeat(c2_client):
    token = c2_token(c2_client)
    registered = register_beacon(c2_client)
    original_last_seen = registered["beacon"]["last_seen"]

    with c2_client.websocket_connect(f"/ws/operator?access_token={token}") as websocket:
        assert websocket.receive_json()["type"] == "realtime.connected"
        response = c2_client.post(
            f"/api/v1/beacons/{registered['beacon_id']}/heartbeat",
            headers={"Authorization": f"Bearer {registered['beacon_token']}"},
            json={"hostname": "heartbeat-renamed", "internal_ip": "10.30.0.6", "pid": 4040},
        )
        event = websocket.receive_json()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "online"
    assert payload["beacon"]["hostname"] == "heartbeat-renamed"
    assert payload["beacon"]["internal_ip"] == "10.30.0.6"
    assert payload["beacon"]["pid"] == 4040
    assert payload["beacon"]["last_seen"] > original_last_seen
    assert event["type"] == "beacon.heartbeat"
    assert event["scope"]["beacon_id"] == registered["beacon_id"]
    assert event["data"]["beacon"]["hostname"] == "heartbeat-renamed"


def test_heartbeat_unknown_id_returns_404(c2_client):
    response = c2_client.post(
        f"/api/v1/beacons/{uuid.uuid4()}/heartbeat",
        headers={"Authorization": "Bearer anything"},
        json={},
    )

    assert response.status_code == 404


def test_heartbeat_invalid_token_returns_401(c2_client):
    registered = register_beacon(c2_client)

    response = c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/heartbeat",
        headers={"Authorization": "Bearer not-the-token"},
        json={},
    )

    assert response.status_code == 401


def test_heartbeat_invalid_metadata_returns_422(c2_client):
    registered = register_beacon(c2_client)

    response = c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/heartbeat",
        headers={"Authorization": f"Bearer {registered['beacon_token']}"},
        json={"internal_ip": "10.0.0.999"},
    )

    assert response.status_code == 422


def test_status_filter_online_only(c2_client):
    online = register_beacon(c2_client, hostname="online-host")
    offline = register_beacon(c2_client, hostname="offline-host")
    token = c2_token(c2_client)

    with session_scope(get_settings()) as session:
        beacon = session.get(Beacon, uuid.UUID(offline["beacon_id"]))
        assert beacon is not None
        beacon.status = BEACON_STATUS_OFFLINE

    response = c2_client.get("/api/v1/beacons?status=online", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [online["beacon_id"]]


def test_stale_beacon_marked_offline_and_event_logged(c2_client):
    registered = register_beacon(c2_client)
    settings = get_settings().model_copy(update={"beacon_stale_threshold_seconds": 1})

    with session_scope(get_settings()) as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        beacon.last_seen = utc_now() - timedelta(seconds=5)
        stale = mark_stale_beacons_offline(session, settings)
        assert [item.id for item in stale] == [beacon.id]

    with session_scope(get_settings()) as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        event = session.execute(select(BeaconEvent).where(BeaconEvent.beacon_id == beacon.id)).scalar_one()
        assert beacon.status == BEACON_STATUS_OFFLINE
        assert event.old_status == "online"
        assert event.new_status == "offline"
        assert event.reason == "stale-threshold"


def test_offline_to_online_transition_emits_status_event(c2_client):
    token = c2_token(c2_client)
    registered = register_beacon(c2_client)

    with session_scope(get_settings()) as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        beacon.status = BEACON_STATUS_OFFLINE

    with c2_client.websocket_connect(f"/ws/operator?access_token={token}") as websocket:
        assert websocket.receive_json()["type"] == "realtime.connected"
        response = c2_client.post(
            f"/api/v1/beacons/{registered['beacon_id']}/heartbeat",
            headers={"Authorization": f"Bearer {registered['beacon_token']}"},
            json={},
        )
        status_event = websocket.receive_json()
        heartbeat_event = websocket.receive_json()

    assert response.status_code == 200
    assert status_event["type"] == "beacon.status.changed"
    assert status_event["data"]["beacon"]["status"] == "online"
    assert heartbeat_event["type"] == "beacon.heartbeat"

    with session_scope(get_settings()) as session:
        event = session.execute(
            select(BeaconEvent).where(BeaconEvent.beacon_id == uuid.UUID(registered["beacon_id"]))
        ).scalar_one()
        assert event.old_status == "offline"
        assert event.new_status == "online"
        assert event.reason == "heartbeat"
