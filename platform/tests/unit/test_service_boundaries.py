from __future__ import annotations

from fastapi.testclient import TestClient
from xero_beacon_handler.main import create_app as create_handler_app
from xero_scanner.main import create_app as create_scanner_app


def test_bff_openapi_contains_only_bff_routes(make_bff_client):
    client = make_bff_client()

    paths = client.get("/openapi.json").json()["paths"]

    assert "/health" in paths
    assert "/ready" in paths
    assert "/auth/login" in paths
    assert "/api/v1/health" in paths
    assert "/api/v1/ready" in paths
    assert "/api/v1/me" in paths
    assert "/api/v1/auth/password" in paths
    assert "/api/v1/c2/connect" not in paths
    assert "/api/v1/c2/session" not in paths
    assert "/api/v1/beacons" not in paths
    assert "/api/v1/beacons/register" not in paths


def test_c2_openapi_contains_only_c2_routes(make_c2_client):
    client = make_c2_client()

    paths = client.get("/openapi.json").json()["paths"]

    assert "/health" in paths
    assert "/ready" in paths
    assert "/api/v1/c2/connect" in paths
    assert "/api/v1/c2/session" in paths
    assert "/api/v1/transport" in paths
    assert "/api/v1/beacons" in paths
    assert "/api/v1/beacons/register" in paths
    assert "/api/v1/beacons/{beacon_id}" in paths
    assert "/api/v1/beacons/{beacon_id}/heartbeat" in paths
    assert "/auth/login" not in paths
    assert "/api/v1/me" not in paths
    assert "/api/v1/auth/password" not in paths


def test_bff_rejects_c2_paths_and_c2_rejects_bff_paths(make_bff_client, make_c2_client):
    bff = make_bff_client()
    c2 = make_c2_client()

    assert bff.post("/api/v1/c2/connect", json={"password": "c2_password"}).status_code == 404
    assert bff.get("/api/v1/beacons").status_code == 404
    assert c2.post("/auth/login", json={"username": "admin", "password": "admin"}).status_code == 404
    assert c2.get("/api/v1/me").status_code == 404


def test_scaffold_services_expose_only_health_and_readiness():
    handler = TestClient(create_handler_app())
    scanner = TestClient(create_scanner_app())

    for client in (handler, scanner):
        paths = client.get("/openapi.json").json()["paths"]
        assert set(paths) == {"/health", "/ready"}
        assert client.get("/health").status_code == 200
        assert client.get("/ready").json()["status"] == "ready"
