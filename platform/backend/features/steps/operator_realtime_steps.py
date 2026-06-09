from __future__ import annotations

import os
import tempfile
import uuid

from app.config import get_settings
from app.database import clear_database_caches, get_engine, session_scope
from app.main import create_app
from app.models import Base, Beacon
from behave import given, then, when
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def cleanup_realtime_context(context):
    context.client.__exit__(None, None, None)
    get_engine(os.environ["DATABASE_URL"]).dispose()
    clear_database_caches()
    context.temp_dir.cleanup()


@given("a C2 realtime test service")
def create_c2_realtime_service(context):
    context.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    os.environ["APP_ENV"] = "test"
    os.environ["XERO_SERVICE_NAME"] = "xero-c2-core"
    os.environ["XERO_SERVICE_ROLE"] = "c2"
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{context.temp_dir.name}/behave-c2.db"
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-with-enough-length"
    os.environ["C2_CONNECT_PASSWORD"] = "c2_password"
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(os.environ["DATABASE_URL"]))
    context.client = TestClient(create_app())
    context.client.__enter__()


@when("I authenticate to the C2 service")
def authenticate_to_c2(context):
    response = context.client.post("/api/v1/c2/connect", json={"password": "c2_password"})
    assert response.status_code == 200
    context.c2_token = response.json()["access_token"]


@when("I connect to the operator websocket")
def connect_operator_websocket(context):
    context.websocket_context = context.client.websocket_connect(f"/ws/operator?access_token={context.c2_token}")
    context.websocket = context.websocket_context.__enter__()


@when("I register a beacon through the C2 API")
def register_beacon(context):
    response = context.client.post(
        "/api/v1/beacons/register",
        json={
            "machine_fingerprint_hash": "behave-fingerprint-001",
            "hostname": "behave-host",
            "os": "Windows 11",
            "architecture": "x64",
            "internal_ip": "10.20.0.5",
            "external_ip": "198.51.100.20",
            "pid": 4444,
        },
    )
    assert response.status_code == 200
    context.registration_payload = response.json()
    context.beacon_id = context.registration_payload["beacon_id"]
    context.beacon_token = context.registration_payload["beacon_token"]


@when("I re-register the same beacon fingerprint with new metadata")
def re_register_beacon(context):
    response = context.client.post(
        "/api/v1/beacons/register",
        json={
            "machine_fingerprint_hash": "behave-fingerprint-001",
            "hostname": "behave-host-renamed",
            "os": "Windows Server 2022",
            "architecture": "x64",
            "internal_ip": "10.20.0.6",
            "external_ip": "198.51.100.21",
            "pid": 5555,
        },
    )
    assert response.status_code == 200
    context.updated_registration_payload = response.json()


@when("I mark the registered beacon offline")
def mark_registered_beacon_offline(context):
    with session_scope(get_settings()) as session:
        beacon = session.get(Beacon, uuid.UUID(context.beacon_id))
        assert beacon is not None
        beacon.status = "offline"


@when("I send a heartbeat with the registered beacon token")
def send_registered_beacon_heartbeat(context):
    response = context.client.post(
        f"/api/v1/beacons/{context.beacon_id}/heartbeat",
        headers={"Authorization": f"Bearer {context.beacon_token}"},
        json={},
    )
    assert response.status_code == 200
    context.heartbeat_payload = response.json()


@when("I connect to the operator websocket without a token")
def connect_operator_websocket_without_token(context):
    try:
        with context.client.websocket_connect("/ws/operator"):
            pass
    except WebSocketDisconnect as exc:
        context.websocket_close_code = exc.code


@then("the operator websocket receives a connected event")
def assert_connected_event(context):
    event = context.websocket.receive_json()
    assert event["type"] == "realtime.connected"
    context.websocket_context.__exit__(None, None, None)
    cleanup_realtime_context(context)


@then("the C2 beacon list includes the registered beacon")
def assert_beacon_list_includes_registered(context):
    response = context.client.get("/api/v1/beacons", headers={"Authorization": f"Bearer {context.c2_token}"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == context.beacon_id
    assert payload["items"][0]["hostname"] == "behave-host"
    assert "beacon_token" not in payload["items"][0]
    cleanup_realtime_context(context)


@then("the beacon registration response includes token material")
def assert_registration_response_includes_token_material(context):
    assert context.registration_payload["beacon_id"]
    assert context.registration_payload["beacon_token"]
    assert context.registration_payload["sleep"] == 30
    assert context.registration_payload["jitter"] == 0.1
    assert "beacon_token" not in context.registration_payload["beacon"]
    cleanup_realtime_context(context)


@then("the C2 beacon list contains one updated beacon")
def assert_c2_beacon_list_contains_one_updated_beacon(context):
    response = context.client.get("/api/v1/beacons", headers={"Authorization": f"Bearer {context.c2_token}"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == context.beacon_id
    assert payload["items"][0]["hostname"] == "behave-host-renamed"
    assert context.updated_registration_payload["beacon_id"] == context.beacon_id
    assert context.updated_registration_payload["beacon_token"] != context.beacon_token
    cleanup_realtime_context(context)


@then("the operator websocket receives beacon recovery and heartbeat events")
def assert_operator_websocket_receives_beacon_recovery_and_heartbeat_events(context):
    status_event = context.websocket.receive_json()
    if status_event["type"] == "realtime.connected":
        status_event = context.websocket.receive_json()
    heartbeat_event = context.websocket.receive_json()
    assert status_event["type"] == "beacon.status.changed"
    assert status_event["data"]["beacon"]["status"] == "online"
    assert heartbeat_event["type"] == "beacon.heartbeat"
    assert heartbeat_event["scope"]["beacon_id"] == context.beacon_id
    assert context.heartbeat_payload["beacon"]["status"] == "online"
    context.websocket_context.__exit__(None, None, None)
    cleanup_realtime_context(context)


@then("the online beacon filter includes the registered beacon")
def assert_online_beacon_filter_includes_registered_beacon(context):
    response = context.client.get(
        "/api/v1/beacons?status=online",
        headers={"Authorization": f"Bearer {context.c2_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["items"]] == [context.beacon_id]
    cleanup_realtime_context(context)


@then("the websocket is closed with code {close_code:d}")
def assert_websocket_close_code(context, close_code):
    assert context.websocket_close_code == close_code
    cleanup_realtime_context(context)
