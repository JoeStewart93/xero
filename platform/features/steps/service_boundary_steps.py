from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from behave import given, then, when
from fastapi.testclient import TestClient
from xero_bff.config import get_settings as get_bff_settings
from xero_bff.main import create_app as create_bff_app
from xero_c2.config import get_settings as get_c2_settings
from xero_c2.main import create_app as create_c2_app
from xero_c2.models import Base as C2Base
from xero_common.database import clear_database_caches, get_engine


def reset_state() -> None:
    get_bff_settings.cache_clear()
    get_c2_settings.cache_clear()
    clear_database_caches()


@given("a test BFF service")
def given_test_bff_service(context):
    reset_state()
    context.client = TestClient(create_bff_app())


@then("the BFF health endpoint reports the bff role")
def then_bff_health_reports_role(context):
    response = context.client.get("/health")

    assert response.status_code == 200
    assert response.json()["role"] == "bff"


@then("the BFF does not expose C2 beacon routes")
def then_bff_does_not_expose_c2_routes(context):
    assert context.client.post("/api/v1/c2/connect", json={"password": "c2_password"}).status_code == 404
    assert context.client.get("/api/v1/beacons").status_code == 404


@given("a test C2 service")
def given_test_c2_service(context):
    reset_state()
    temp_dir = Path(tempfile.mkdtemp())
    database_url = f"sqlite+pysqlite:///{temp_dir / 'c2-behave.db'}"
    context.database_url = database_url
    context._old_env = {}
    for key, value in {
        "APP_ENV": "test",
        "C2_DATABASE_URL": database_url,
        "C2_CONNECT_PASSWORD": "c2_password",
        "C2_JWT_SECRET_KEY": "test-c2-jwt-secret-with-enough-length",
    }.items():
        context._old_env[key] = os.environ.get(key)
        os.environ[key] = value
    reset_state()
    C2Base.metadata.create_all(bind=get_engine(database_url))
    context.client = TestClient(create_c2_app())


@when("I connect to the C2 service")
def when_i_connect_to_c2(context):
    response = context.client.post("/api/v1/c2/connect", json={"password": "c2_password"})

    assert response.status_code == 200
    context.c2_token = response.json()["access_token"]


@when("I register and heartbeat a beacon")
def when_i_register_and_heartbeat_beacon(context):
    response = context.client.post(
        "/api/v1/beacons/register",
        json={
            "machine_fingerprint_hash": f"behave-{uuid.uuid4()}",
            "hostname": "behave-host",
            "os": "Windows 11",
            "architecture": "x64",
            "internal_ip": "10.40.0.10",
            "external_ip": "198.51.100.10",
            "pid": 4444,
        },
    )
    assert response.status_code == 200
    context.beacon_id = response.json()["beacon_id"]
    context.beacon_token = response.json()["beacon_token"]

    heartbeat = context.client.post(
        f"/api/v1/beacons/{context.beacon_id}/heartbeat",
        headers={"Authorization": f"Bearer {context.beacon_token}"},
        json={},
    )
    assert heartbeat.status_code == 200


@then("the C2 service lists the beacon as online")
def then_c2_lists_beacon_online(context):
    response = context.client.get("/api/v1/beacons", headers={"Authorization": f"Bearer {context.c2_token}"})

    assert response.status_code == 200
    assert response.json()["items"][0]["hostname"] == "behave-host"
    assert response.json()["items"][0]["status"] == "online"


@then("the C2 service does not expose BFF login routes")
def then_c2_does_not_expose_bff_routes(context):
    assert context.client.post("/auth/login", json={"username": "admin", "password": "admin"}).status_code == 404
    assert context.client.get("/api/v1/me").status_code == 404
