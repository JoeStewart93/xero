from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import socket
import threading
import time
import uuid
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect, WebSocketState
from xero_c2.artifacts import ArtifactNotFound, artifact_store_for_settings
from xero_c2.beacon_liveness import BEACON_STATUS_OFFLINE, mark_stale_beacons_offline
from xero_c2.beacon_transport import WS_CLOSE_DUPLICATE, WS_CLOSE_OVERLOADED, BeaconTransportManager
from xero_c2.config import Settings, get_settings
from xero_c2.file_transfers import create_download_transfer
from xero_c2.infrastructure_workers import mark_stale_workers
from xero_c2.models import (
    Artifact,
    Base,
    Beacon,
    BeaconBuild,
    BeaconEvent,
    FileTransfer,
    FileTransferChunk,
    InfrastructureWorker,
    InteractiveSession,
    ProtocolFrameReceipt,
    ProtocolSecurityEvent,
    RegistryAuditEvent,
    RegistryConfirmation,
    ResultChunk,
    ScanJob,
    ScanResultChunk,
    Task,
    TaskAuditEvent,
    TaskResult,
    WorkerEvent,
)
from xero_c2.portscan import run_scan_job
from xero_c2.protocol import HEARTBEAT, REGISTER, SESSION_DATA, TASK_POLL, TASK_RESULT
from xero_c2.protocol.codec import public_key_bytes
from xero_c2.registry_sessions import (
    consume_registry_confirmation,
    create_registry_confirmation,
    parse_registry_request,
)
from xero_c2.serviceenum import FINGERPRINT_RULES, enumerate_service, parse_tls_certificate
from xero_c2.sessions import (
    DuplicateSessionAttachError,
    FileListingCache,
    SessionRelayManager,
    apply_beacon_session_data,
    close_detached_after_grace,
    expire_idle_sessions,
    parse_file_browser_request,
    terminal_data_b64,
)
from xero_c2.task_results import purge_expired_task_results
from xero_common.database import clear_database_caches, get_engine, get_session_factory
from xero_common.models import utc_now
from xero_common.security import hash_beacon_token

from tests.helpers.protocol_frames import (
    decode_protocol_response,
    encode_protocol_test_frame,
    protocol_client_private_key,
)


@pytest.fixture
def c2_client(monkeypatch, tmp_path, make_c2_client):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'c2.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("C2_DATABASE_URL", database_url)
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "connect-me")
    monkeypatch.setenv("C2_JWT_SECRET_KEY", "test-c2-jwt-secret-with-enough-length")
    monkeypatch.setenv("BEACON_DEFAULT_SLEEP_SECONDS", "5")
    monkeypatch.setenv("BEACON_DEFAULT_JITTER", "0.25")
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(database_url))
    return make_c2_client()


@pytest.fixture
def protocol_c2_client(monkeypatch, tmp_path, make_c2_client):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'protocol-c2.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("C2_DATABASE_URL", database_url)
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "connect-me")
    monkeypatch.setenv("C2_JWT_SECRET_KEY", "test-c2-jwt-secret-with-enough-length")
    monkeypatch.setenv("C2_PROTOCOL_FRAME_HARNESS_ENABLED", "true")
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(database_url))
    return make_c2_client()


@pytest.fixture
def result_c2_client(monkeypatch, tmp_path, make_c2_client):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'result-c2.db'}"
    artifact_dir = tmp_path / "result-artifacts"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("C2_DATABASE_URL", database_url)
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "connect-me")
    monkeypatch.setenv("C2_JWT_SECRET_KEY", "test-c2-jwt-secret-with-enough-length")
    monkeypatch.setenv("C2_PROTOCOL_FRAME_HARNESS_ENABLED", "true")
    monkeypatch.setenv("C2_ARTIFACT_STORAGE_BACKEND", "filesystem")
    monkeypatch.setenv("C2_ARTIFACT_FILESYSTEM_DIR", str(artifact_dir))
    monkeypatch.setenv("C2_TASK_RESULT_INLINE_MAX_BYTES", "1024")
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(database_url))
    return make_c2_client(
        C2_DATABASE_URL=database_url,
        C2_PROTOCOL_FRAME_HARNESS_ENABLED="true",
        C2_ARTIFACT_STORAGE_BACKEND="filesystem",
        C2_ARTIFACT_FILESYSTEM_DIR=str(artifact_dir),
        C2_TASK_RESULT_INLINE_MAX_BYTES="1024",
    )


@pytest.fixture
def longpoll_c2_client(monkeypatch, tmp_path, make_c2_client):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'longpoll-c2.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("C2_DATABASE_URL", database_url)
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "connect-me")
    monkeypatch.setenv("C2_JWT_SECRET_KEY", "test-c2-jwt-secret-with-enough-length")
    monkeypatch.setenv("C2_BEACON_LONGPOLL_TIMEOUT_SECONDS", "1")
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(database_url))
    return make_c2_client(
        C2_DATABASE_URL=database_url,
        C2_BEACON_LONGPOLL_TIMEOUT_SECONDS="1",
    )


@pytest.fixture
def beacon_build_c2_client(monkeypatch, tmp_path, make_c2_client):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'build-c2.db'}"
    artifact_dir = tmp_path / "artifacts"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("C2_DATABASE_URL", database_url)
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "connect-me")
    monkeypatch.setenv("C2_JWT_SECRET_KEY", "test-c2-jwt-secret-with-enough-length")
    monkeypatch.setenv("C2_BEACON_BUILDS_ENABLED", "true")
    monkeypatch.setenv("C2_ARTIFACT_STORAGE_BACKEND", "filesystem")
    monkeypatch.setenv("C2_ARTIFACT_FILESYSTEM_DIR", str(artifact_dir))
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(database_url))
    return make_c2_client(
        C2_DATABASE_URL=database_url,
        C2_BEACON_BUILDS_ENABLED="true",
        C2_ARTIFACT_STORAGE_BACKEND="filesystem",
        C2_ARTIFACT_FILESYSTEM_DIR=str(artifact_dir),
    )


def connect_c2(client) -> str:
    response = client.post("/api/v1/c2/connect", json={"password": "connect-me"})
    assert response.status_code == 200
    return response.json()["access_token"]


def register_payload(**overrides):
    payload = {
        "machine_fingerprint_hash": f"fingerprint-{uuid.uuid4()}",
        "hostname": "test-host",
        "os": "Windows 11",
        "architecture": "x64",
        "internal_ip": "10.20.0.5",
        "external_ip": "198.51.100.5",
        "pid": 2222,
    }
    payload.update(overrides)
    return payload


def register_beacon(client, **overrides) -> dict:
    response = client.post("/api/v1/beacons/register", json=register_payload(**overrides))
    assert response.status_code == 200
    return response.json()


def stub_dashboard_health(monkeypatch, *, status_value: str = "ready") -> None:
    redis_check = {"status": "healthy"} if status_value == "ready" else {
        "status": "unhealthy",
        "error": "redis unavailable",
    }
    checks = {
        "artifact_store": {"status": "healthy"},
        "postgres": {"status": "healthy"},
        "redis": redis_check,
    }
    monkeypatch.setattr(
        "xero_c2.main.c2_readiness_report",
        lambda _settings: {"checks": checks, "service": "xero-c2", "status": status_value},
    )


def traffic_profile_config(
    *,
    sleep_seconds: int = 11,
    jitter: float = 0.15,
    user_agent: str = "xero-profile-test",
    frame_path: str = "/cdn-cgi/xero/{beacon_id}/frame",
    poll_path: str = "/cdn-cgi/xero/{beacon_id}/collect",
    register_path: str = "/cdn-cgi/xero/register",
    websocket_path: str = "/cdn-cgi/xero/ws",
) -> dict:
    return {
        "headers": {"X-Profile": "enabled"},
        "jitter": jitter,
        "padding": {"enabled": True, "max_bytes": 24, "min_bytes": 8},
        "paths": {
            "frame": frame_path,
            "poll": poll_path,
            "register": register_path,
            "websocket": websocket_path,
        },
        "sleep_seconds": sleep_seconds,
        "user_agent": user_agent,
    }


def create_shell_task(client, token: str, beacon_id: str, *, command: str = "whoami", priority: str = "normal") -> dict:
    response = client.post(
        "/api/v1/tasks",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "beacon_id": beacon_id,
            "module": "shell",
            "args": {"command": command},
            "priority": priority,
        },
    )
    assert response.status_code == 200
    return response.json()


def attach_protocol_metadata(beacon_id: str) -> None:
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(beacon_id))
        assert beacon is not None
        beacon.protocol_session_id = str(uuid.uuid4())
        beacon.protocol_peer_public_key_b64 = base64.b64encode(
            public_key_bytes(protocol_client_private_key())
        ).decode("ascii")
        session.add(beacon)
        session.commit()


def test_c2_connect_and_session(c2_client):
    bad = c2_client.post("/api/v1/c2/connect", json={"password": "wrong"})
    token = connect_c2(c2_client)
    session = c2_client.get("/api/v1/c2/session", headers={"Authorization": f"Bearer {token}"})

    assert bad.status_code == 401
    assert session.status_code == 200
    assert session.json()["service_role"] == "c2"


def test_dashboard_summary_requires_c2_auth(c2_client):
    response = c2_client.get("/api/v1/dashboard/summary")

    assert response.status_code == 401


def test_dashboard_summary_api_response_shape(c2_client, monkeypatch):
    stub_dashboard_health(monkeypatch)
    token = connect_c2(c2_client)
    response = c2_client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["beacons"] == {"offline": 0, "online": 0, "total": 0}
    assert payload["recent_tasks"] == []
    assert payload["recent_activity"] == []
    assert payload["generated_at"]
    assert payload["c2_health"]["status"] in {"degraded", "ready"}
    assert "postgres" in payload["c2_health"]["checks"]
    assert "redis" in payload["c2_health"]["checks"]


def test_dashboard_summary_counts_tasks_and_activity(c2_client, monkeypatch):
    stub_dashboard_health(monkeypatch)
    token = connect_c2(c2_client)
    headers = {"Authorization": f"Bearer {token}"}
    online = register_beacon(c2_client, hostname="online-host")
    offline = register_beacon(c2_client, hostname="offline-host")
    first_task = create_shell_task(c2_client, token, online["beacon_id"], command="hostname")
    latest_task = create_shell_task(c2_client, token, offline["beacon_id"], command="whoami")

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        offline_beacon = session.get(Beacon, uuid.UUID(offline["beacon_id"]))
        assert offline_beacon is not None
        offline_beacon.status = BEACON_STATUS_OFFLINE
        session.add(
            BeaconEvent(
                beacon_id=offline_beacon.id,
                old_status="online",
                new_status=BEACON_STATUS_OFFLINE,
                reason="test-offline",
            )
        )
        session.add(offline_beacon)
        session.commit()

    response = c2_client.get("/api/v1/dashboard/summary", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["beacons"] == {"offline": 1, "online": 1, "total": 2}
    assert [task["id"] for task in payload["recent_tasks"]] == [latest_task["id"], first_task["id"]]
    activity_types = [item["type"] for item in payload["recent_activity"]]
    assert "beacon.status" in activity_types
    assert "task.queued" in activity_types
    offline_activity = next(item for item in payload["recent_activity"] if item["type"] == "beacon.status")
    assert offline_activity["beacon_id"] == offline["beacon_id"]
    assert offline_activity["status"] == "offline"
    assert "offline-host" in offline_activity["label"]


def test_dashboard_summary_caps_recent_tasks_and_activity(c2_client, monkeypatch):
    stub_dashboard_health(monkeypatch)
    token = connect_c2(c2_client)
    beacon = register_beacon(c2_client)

    task_ids = [
        create_shell_task(c2_client, token, beacon["beacon_id"], command=f"echo {index}")["id"]
        for index in range(12)
    ]

    response = c2_client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["recent_tasks"]) == 10
    assert len(payload["recent_activity"]) == 10
    assert payload["recent_tasks"][0]["id"] == task_ids[-1]
    assert payload["recent_tasks"][-1]["id"] == task_ids[-10]


def test_dashboard_summary_surfaces_degraded_health(c2_client, monkeypatch):
    token = connect_c2(c2_client)
    stub_dashboard_health(monkeypatch, status_value="degraded")

    response = c2_client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["c2_health"]["status"] == "degraded"
    assert payload["c2_health"]["checks"]["redis"]["status"] == "unhealthy"
    assert payload["c2_health"]["checks"]["redis"]["error"] == "redis unavailable"


def test_protocol_info_requires_c2_auth_and_exposes_public_metadata(c2_client):
    unauthenticated = c2_client.get("/api/v1/protocol")
    token = connect_c2(c2_client)
    response = c2_client.get("/api/v1/protocol", headers={"Authorization": f"Bearer {token}"})

    assert unauthenticated.status_code == 401
    assert response.status_code == 200
    payload = response.json()
    assert payload["current_version"] == 1
    assert payload["supported_versions"] == [1]
    assert payload["key_exchange"] == "X25519-HKDF-SHA256"
    assert payload["encryption"] == "AES-256-GCM"
    assert payload["integrity"] == "HMAC-SHA256"
    assert payload["frame_header_length"] == 72
    assert payload["c2_public_key_b64"]
    assert payload["frame_harness_enabled"] is False


def test_module_registry_exposes_builtin_portscan(c2_client):
    unauthenticated = c2_client.get("/api/v1/modules")
    token = connect_c2(c2_client)
    response = c2_client.get("/api/v1/modules", headers={"Authorization": f"Bearer {token}"})

    assert unauthenticated.status_code == 401
    assert response.status_code == 200
    modules = {item["id"]: item for item in response.json()["items"]}
    assert "shell" in modules
    assert modules["shell"]["execution_kind"] == "beacon-task"
    assert modules["shell"]["supported_execution_targets"] == ["beacon"]
    assert modules["shell"]["args_schema"]["required"] == ["command"]
    assert modules["shell"]["args_schema"]["properties"]["command"]["type"] == "string"
    assert modules["shell"]["author"] == "Xero"
    assert modules["shell"]["status"] == "enabled"
    assert "beacon-task" in modules["shell"]["tags"]
    assert "builtin.portscan" in modules
    assert modules["builtin.portscan"]["execution_kind"] == "scan-job"
    assert modules["builtin.portscan"]["supported_execution_targets"] == ["auto"]
    assert modules["builtin.portscan"]["args_schema"]["properties"]["execution_target"]["enum"] == ["auto"]
    assert modules["builtin.portscan"]["author"] == "Xero"
    assert modules["builtin.portscan"]["plugin_id"] is None
    assert modules["builtin.portscan"]["status"] == "enabled"
    assert "scan-job" in modules["builtin.portscan"]["tags"]


def test_portscan_args_validation_rejects_public_and_non_auto_targets(c2_client):
    token = connect_c2(c2_client)
    headers = {"Authorization": f"Bearer {token}"}

    public_target = c2_client.post(
        "/api/v1/scan-jobs",
        headers=headers,
        json={
            "module": "builtin.portscan",
            "args": {"execution_target": "auto", "port_range": "80", "targets": ["8.8.8.8"]},
        },
    )
    external_target = c2_client.post(
        "/api/v1/scan-jobs",
        headers=headers,
        json={
            "module": "builtin.portscan",
            "args": {"execution_target": "external", "port_range": "80", "targets": ["127.0.0.1"]},
        },
    )
    invalid_port = c2_client.post(
        "/api/v1/scan-jobs",
        headers=headers,
        json={
            "module": "builtin.portscan",
            "args": {"execution_target": "auto", "port_range": "70000", "targets": ["127.0.0.1"]},
        },
    )

    assert public_target.status_code == 422
    assert external_target.status_code == 422
    assert invalid_port.status_code == 422


def test_portscan_job_scans_loopback_and_records_chunks(c2_client, monkeypatch):
    monkeypatch.setattr("xero_c2.main.schedule_scan_execution", lambda *args, **kwargs: None)
    token = connect_c2(c2_client)
    headers = {"Authorization": f"Bearer {token}"}
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)
    open_port = listener.getsockname()[1]
    closed_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    closed_socket.bind(("127.0.0.1", 0))
    closed_port = closed_socket.getsockname()[1]
    closed_socket.close()
    stop_accepting = threading.Event()

    def accept_connections():
        listener.settimeout(0.1)
        while not stop_accepting.is_set():
            try:
                connection, _ = listener.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            connection.close()

    accept_thread = threading.Thread(target=accept_connections, daemon=True)
    accept_thread.start()
    try:
        created = c2_client.post(
            "/api/v1/scan-jobs",
            headers=headers,
            json={
                "module": "builtin.portscan",
                "args": {
                    "execution_target": "auto",
                    "max_threads": 2,
                    "port_range": f"{open_port},{closed_port}",
                    "targets": ["127.0.0.1"],
                    "timeout_ms": 500,
                },
            },
        )
        assert created.status_code == 200
        job = created.json()
        assert job["status"] == "queued"
        assert job["progress_total"] == 2

        settings = get_settings()
        asyncio.run(run_scan_job(c2_client.app, settings, uuid.UUID(job["id"])))
        fetched = c2_client.get(f"/api/v1/scan-jobs/{job['id']}", headers=headers)
        assert fetched.status_code == 200
        job = fetched.json()
        assert job["status"] == "completed"
        assert job["summary"]["ports_scanned"] == 2
        assert job["summary"]["open_count"] == 1
        results = {(item["host"], item["port"]): item for item in job["results"]}
        assert results[("127.0.0.1", open_port)]["state"] == "open"
        assert results[("127.0.0.1", closed_port)]["state"] in {"closed", "filtered"}

        chunks = c2_client.get(f"/api/v1/scan-jobs/{job['id']}/chunks", headers=headers)
        assert chunks.status_code == 200
        payload = chunks.json()["items"]
        assert [chunk["kind"] for chunk in payload] == ["progress", "summary"]
        assert payload[0]["probes_completed"] == 2

        SessionFactory = get_session_factory(settings.database_url)
        with SessionFactory() as session:
            stored_job = session.get(ScanJob, uuid.UUID(job["id"]))
            assert stored_job is not None
            stored_chunks = (
                session.execute(
                    select(ScanResultChunk).where(ScanResultChunk.scan_job_id == uuid.UUID(job["id"]))
                )
                .scalars()
                .all()
            )
            assert len(stored_chunks) == 2
    finally:
        stop_accepting.set()
        listener.close()
        accept_thread.join(timeout=1)


def test_portscan_progress_chunk_emission_for_large_scan(c2_client, monkeypatch):
    monkeypatch.setattr("xero_c2.main.schedule_scan_execution", lambda *args, **kwargs: None)

    async def fake_probe(host: str, port: int, *, timeout_ms: int) -> dict:
        return {"host": host, "latency_ms": 1.0, "port": port, "state": "open" if port == 443 else "closed"}

    monkeypatch.setattr("xero_c2.portscan.probe_tcp_connect", fake_probe)
    token = connect_c2(c2_client)
    headers = {"Authorization": f"Bearer {token}"}

    created = c2_client.post(
        "/api/v1/scan-jobs",
        headers=headers,
        json={
            "module": "builtin.portscan",
            "args": {
                "execution_target": "auto",
                "max_threads": 32,
                "port_range": "1-1000",
                "targets": ["127.0.0.1"],
                "timeout_ms": 500,
            },
        },
    )

    assert created.status_code == 200
    job_id = created.json()["id"]
    asyncio.run(run_scan_job(c2_client.app, get_settings(), uuid.UUID(job_id)))

    fetched = c2_client.get(f"/api/v1/scan-jobs/{job_id}", headers=headers)
    assert fetched.status_code == 200
    job = fetched.json()
    assert job["status"] == "completed"
    assert job["progress_completed"] == 1000
    assert job["summary"]["ports_scanned"] == 1000
    assert job["summary"]["open_count"] == 1

    chunks = c2_client.get(f"/api/v1/scan-jobs/{job_id}/chunks", headers=headers)
    assert chunks.status_code == 200
    chunk_items = chunks.json()["items"]
    progress_chunks = [chunk for chunk in chunk_items if chunk["kind"] == "progress"]
    assert len(progress_chunks) == 10
    assert [chunk["probes_completed"] for chunk in progress_chunks] == list(range(100, 1001, 100))
    assert chunk_items[-1]["kind"] == "summary"


def test_portscan_respects_max_threads(c2_client, monkeypatch):
    monkeypatch.setattr("xero_c2.main.schedule_scan_execution", lambda *args, **kwargs: None)
    active_probes = 0
    max_active_probes = 0

    async def fake_probe(host: str, port: int, *, timeout_ms: int) -> dict:
        nonlocal active_probes, max_active_probes
        active_probes += 1
        max_active_probes = max(max_active_probes, active_probes)
        await asyncio.sleep(0.001)
        active_probes -= 1
        return {"host": host, "latency_ms": 1.0, "port": port, "state": "closed"}

    monkeypatch.setattr("xero_c2.portscan.probe_tcp_connect", fake_probe)
    token = connect_c2(c2_client)
    headers = {"Authorization": f"Bearer {token}"}

    created = c2_client.post(
        "/api/v1/scan-jobs",
        headers=headers,
        json={
            "module": "builtin.portscan",
            "args": {
                "execution_target": "auto",
                "max_threads": 3,
                "port_range": "1-25",
                "targets": ["127.0.0.1"],
                "timeout_ms": 500,
            },
        },
    )

    assert created.status_code == 200
    asyncio.run(run_scan_job(c2_client.app, get_settings(), uuid.UUID(created.json()["id"])))
    assert max_active_probes <= 3
    assert max_active_probes > 1


def test_serviceenum_module_registry_and_args_validation(c2_client):
    token = connect_c2(c2_client)
    headers = {"Authorization": f"Bearer {token}"}
    modules_response = c2_client.get("/api/v1/modules", headers=headers)
    assert modules_response.status_code == 200
    modules = {item["id"]: item for item in modules_response.json()["items"]}
    assert "builtin.serviceenum" in modules
    assert modules["builtin.serviceenum"]["execution_kind"] == "scan-job"
    assert modules["builtin.serviceenum"]["required_capabilities"] == ["service-enumeration"]
    assert modules["builtin.serviceenum"]["status"] == "enabled"
    assert "service-enumeration" in modules["builtin.serviceenum"]["tags"]
    assert len(FINGERPRINT_RULES) >= 50

    public_target = c2_client.post(
        "/api/v1/scan-jobs",
        headers=headers,
        json={
            "module": "builtin.serviceenum",
            "args": {"execution_target": "auto", "host": "8.8.8.8", "ports": [443]},
        },
    )
    external_target = c2_client.post(
        "/api/v1/scan-jobs",
        headers=headers,
        json={
            "module": "builtin.serviceenum",
            "args": {"execution_target": "external", "host": "127.0.0.1", "ports": [443]},
        },
    )
    invalid_port = c2_client.post(
        "/api/v1/scan-jobs",
        headers=headers,
        json={
            "module": "builtin.serviceenum",
            "args": {"execution_target": "auto", "host": "127.0.0.1", "ports": [70000]},
        },
    )

    assert public_target.status_code == 422
    assert external_target.status_code == 422
    assert invalid_port.status_code == 422


def test_serviceenum_http_banner_and_ssh_fingerprint():
    class FixtureHandler(BaseHTTPRequestHandler):
        server_version = "XeroFixture/1.0"
        sys_version = ""

        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args):
            return

    http_server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    http_thread.start()

    ssh_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ssh_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ssh_listener.bind(("127.0.0.1", 0))
    ssh_listener.listen(4)
    ssh_stop = threading.Event()

    def serve_ssh_banner():
        ssh_listener.settimeout(0.1)
        while not ssh_stop.is_set():
            try:
                connection, _ = ssh_listener.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            with connection:
                connection.sendall(b"SSH-2.0-OpenSSH_9.9\r\n")

    ssh_thread = threading.Thread(target=serve_ssh_banner, daemon=True)
    ssh_thread.start()
    try:
        http_result = asyncio.run(enumerate_service("127.0.0.1", http_server.server_port, timeout_ms=500))
        ssh_result = asyncio.run(enumerate_service("127.0.0.1", ssh_listener.getsockname()[1], timeout_ms=500))
    finally:
        http_server.shutdown()
        http_server.server_close()
        http_thread.join(timeout=1)
        ssh_stop.set()
        ssh_listener.close()
        ssh_thread.join(timeout=1)

    assert http_result["status"] == "identified"
    assert http_result["service_guess"] == "http"
    assert any(item["type"] == "http.server" and "XeroFixture" in item["value"] for item in http_result["evidence"])
    assert ssh_result["status"] == "identified"
    assert ssh_result["service_guess"] == "ssh"
    assert "OpenSSH" in ssh_result["banner"]


def test_serviceenum_tls_cert_parse():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "lab.local")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(utc_now() - timedelta(minutes=1))
        .not_valid_after(utc_now() + timedelta(days=14))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("lab.local")]), critical=False)
        .sign(key, hashes.SHA256())
    )

    parsed = parse_tls_certificate(cert.public_bytes(serialization.Encoding.DER))

    assert parsed["subject_cn"] == "lab.local"
    assert parsed["issuer_cn"] == "lab.local"
    assert parsed["sans"] == ["lab.local"]
    assert parsed["not_after"]


def test_serviceenum_closed_port_skipped_without_crash():
    closed_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    closed_socket.bind(("127.0.0.1", 0))
    closed_port = closed_socket.getsockname()[1]
    closed_socket.close()

    result = asyncio.run(enumerate_service("127.0.0.1", closed_port, timeout_ms=200))

    assert result["status"] in {"skipped", "timeout"}
    assert result["service_guess"] == "unknown"
    assert result["error"] == "Port did not accept a TCP connection."


def test_serviceenum_job_records_results_and_chunks(c2_client, monkeypatch):
    monkeypatch.setattr("xero_c2.main.schedule_scan_execution", lambda *args, **kwargs: None)

    async def fake_enum(host: str, port: int, *, timeout_ms: int) -> dict:
        return {
            "banner": "SSH-2.0-OpenSSH_9.9",
            "confidence": 0.95,
            "error": None,
            "evidence": [{"type": "fingerprint", "value": "SSH protocol banner"}],
            "host": host,
            "latency_ms": 1.0,
            "port": port,
            "service_guess": "ssh",
            "status": "identified",
            "tls": None,
            "transport": "tcp",
        }

    monkeypatch.setattr("xero_c2.serviceenum.enumerate_service", fake_enum)
    token = connect_c2(c2_client)
    headers = {"Authorization": f"Bearer {token}"}
    source_scan_job_id = str(uuid.uuid4())
    created = c2_client.post(
        "/api/v1/scan-jobs",
        headers=headers,
        json={
            "module": "builtin.serviceenum",
            "args": {
                "execution_target": "auto",
                "host": "127.0.0.1",
                "max_threads": 2,
                "ports": [22, 2222],
                "probe_timeout_ms": 500,
                "source_scan_job_id": source_scan_job_id,
            },
        },
    )
    assert created.status_code == 200
    job = created.json()
    assert job["module"] == "builtin.serviceenum"
    assert job["progress_total"] == 2
    assert job["args"]["source_scan_job_id"] == source_scan_job_id

    asyncio.run(run_scan_job(c2_client.app, get_settings(), uuid.UUID(job["id"])))
    fetched = c2_client.get(f"/api/v1/scan-jobs/{job['id']}", headers=headers)
    assert fetched.status_code == 200
    job = fetched.json()
    assert job["status"] == "completed"
    assert job["summary"]["identified_count"] == 2
    assert job["summary"]["source_scan_job_id"] == source_scan_job_id
    assert {item["service_guess"] for item in job["results"]} == {"ssh"}

    chunks = c2_client.get(f"/api/v1/scan-jobs/{job['id']}/chunks", headers=headers)
    assert chunks.status_code == 200
    assert [chunk["kind"] for chunk in chunks.json()["items"]] == ["progress", "summary"]


def test_serviceenum_twenty_ports_complete_within_budget(c2_client, monkeypatch):
    monkeypatch.setattr("xero_c2.main.schedule_scan_execution", lambda *args, **kwargs: None)

    async def fake_enum(host: str, port: int, *, timeout_ms: int) -> dict:
        return {
            "banner": f"SSH-2.0-Fixture_{port}",
            "confidence": 0.95,
            "error": None,
            "evidence": [{"type": "fingerprint", "value": "SSH protocol banner"}],
            "host": host,
            "latency_ms": 1.0,
            "port": port,
            "service_guess": "ssh",
            "status": "identified",
            "tls": None,
            "transport": "tcp",
        }

    monkeypatch.setattr("xero_c2.serviceenum.enumerate_service", fake_enum)
    token = connect_c2(c2_client)
    headers = {"Authorization": f"Bearer {token}"}
    created = c2_client.post(
        "/api/v1/scan-jobs",
        headers=headers,
        json={
            "module": "builtin.serviceenum",
            "args": {
                "execution_target": "auto",
                "host": "127.0.0.1",
                "max_threads": 4,
                "ports": list(range(10_001, 10_021)),
                "probe_timeout_ms": 500,
            },
        },
    )
    assert created.status_code == 200
    started = time.perf_counter()
    asyncio.run(run_scan_job(c2_client.app, get_settings(), uuid.UUID(created.json()["id"])))
    elapsed = time.perf_counter() - started

    fetched = c2_client.get(f"/api/v1/scan-jobs/{created.json()['id']}", headers=headers)
    assert fetched.status_code == 200
    job = fetched.json()
    assert job["status"] == "completed"
    assert job["summary"]["ports_enumerated"] == 20
    assert job["summary"]["identified_count"] == 20
    assert elapsed < 30


def test_protocol_frame_harness_is_disabled_by_default(c2_client):
    token = connect_c2(c2_client)
    frame = encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1]))

    response = c2_client.post(
        "/api/v1/protocol/frames",
        content=frame,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 403


def test_traffic_profiles_can_version_assign_and_ack_effective_profile(c2_client):
    token = connect_c2(c2_client)
    auth = {"Authorization": f"Bearer {token}"}

    templates = c2_client.get("/api/v1/traffic-profiles", headers=auth)
    assert templates.status_code == 200
    template_names = {item["name"] for item in templates.json()["items"]}
    assert {"CloudFront CDN", "Google Analytics"}.issubset(template_names)

    created = c2_client.post(
        "/api/v1/traffic-profiles",
        headers=auth,
        json={
            "config": traffic_profile_config(sleep_seconds=13, jitter=0.2, user_agent="First UA"),
            "description": "Operator managed test profile.",
            "name": "Operator CDN",
            "template": "custom-cdn",
        },
    )
    assert created.status_code == 200
    profile = created.json()
    assert profile["current_version"] == 1

    updated = c2_client.patch(
        f"/api/v1/traffic-profiles/{profile['id']}",
        headers=auth,
        json={
            "config": traffic_profile_config(sleep_seconds=17, jitter=0.35, user_agent="Second UA"),
            "description": "Updated profile.",
            "name": "Operator CDN tuned",
        },
    )
    assert updated.status_code == 200
    profile = updated.json()
    assert profile["current_version"] == 2

    versions = c2_client.get(f"/api/v1/traffic-profiles/{profile['id']}/versions", headers=auth)
    assert versions.status_code == 200
    assert [item["version"] for item in versions.json()["items"]] == [2, 1]

    registered = register_beacon(c2_client)
    assigned = c2_client.put(
        f"/api/v1/beacons/{registered['beacon_id']}/profile",
        headers=auth,
        json={"profile_id": profile["id"]},
    )
    assert assigned.status_code == 200
    assigned_beacon = assigned.json()
    assert assigned_beacon["profile_id"] == profile["id"]
    assert assigned_beacon["profile_version"] == 2
    assert assigned_beacon["sleep_seconds"] == 17
    assert assigned_beacon["jitter"] == 0.35

    heartbeat = c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/heartbeat",
        headers={"Authorization": f"Bearer {registered['beacon_token']}"},
        json=register_payload(beacon_id=registered["beacon_id"]),
    )
    assert heartbeat.status_code == 200
    heartbeat_payload = heartbeat.json()
    assert heartbeat_payload["sleep"] == 17
    assert heartbeat_payload["jitter"] == 0.35
    assert heartbeat_payload["profile"]["id"] == profile["id"]
    assert heartbeat_payload["profile"]["current_version"] == 2
    assert heartbeat_payload["profile"]["config"]["user_agent"] == "Second UA"

    archive_assigned = c2_client.delete(f"/api/v1/traffic-profiles/{profile['id']}", headers=auth)
    assert archive_assigned.status_code == 409

    rollback = c2_client.post(
        f"/api/v1/traffic-profiles/{profile['id']}/rollback",
        headers=auth,
        json={"version": 1},
    )
    assert rollback.status_code == 200
    rolled_back = rollback.json()
    assert rolled_back["current_version"] == 3
    assert rolled_back["config"]["sleep_seconds"] == 13

    followup = c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/heartbeat",
        headers={"Authorization": f"Bearer {registered['beacon_token']}"},
        json=register_payload(beacon_id=registered["beacon_id"]),
    )
    assert followup.status_code == 200
    assert followup.json()["profile"]["current_version"] == 3
    assert followup.json()["sleep"] == 13

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))

    assert beacon is not None
    assert beacon.applied_profile_version == 3
    assert beacon.profile_applied_at is not None


def test_traffic_profile_protocol_ack_and_alias_routes(protocol_c2_client):
    token = connect_c2(protocol_c2_client)
    auth = {"Authorization": f"Bearer {token}"}
    created = protocol_c2_client.post(
        "/api/v1/traffic-profiles",
        headers=auth,
        json={
            "config": traffic_profile_config(sleep_seconds=19, jitter=0.1, user_agent="Alias UA"),
            "description": "Alias route profile.",
            "name": "Alias profile",
            "template": "alias",
        },
    )
    assert created.status_code == 200
    profile = created.json()
    registered = register_beacon(protocol_c2_client)
    assign = protocol_c2_client.put(
        f"/api/v1/beacons/{registered['beacon_id']}/profile",
        headers=auth,
        json={"profile_id": profile["id"]},
    )
    assert assign.status_code == 200

    response = protocol_c2_client.post(
        f"/cdn-cgi/xero/{registered['beacon_id']}/frame",
        content=encode_protocol_test_frame(HEARTBEAT, {"beacon_id": registered["beacon_id"]}),
        headers={"Authorization": f"Bearer {registered['beacon_token']}", "Content-Type": "application/octet-stream"},
    )
    ack = decode_protocol_response(response.content)

    assert response.status_code == 200
    assert ack["acknowledged_message_type"] == HEARTBEAT
    assert ack["sleep"] == 19
    assert ack["profile"]["id"] == profile["id"]
    assert ack["profile"]["config"]["paths"]["frame"] == "/cdn-cgi/xero/{beacon_id}/frame"


def test_beacon_build_targets_require_auth_and_list_supported_targets(c2_client):
    unauthenticated = c2_client.get("/api/v1/beacon-builds/targets")
    token = connect_c2(c2_client)
    response = c2_client.get("/api/v1/beacon-builds/targets", headers={"Authorization": f"Bearer {token}"})

    assert unauthenticated.status_code == 401
    assert response.status_code == 200
    assert response.json()["items"] == [
        {"os": "linux", "arch": "amd64", "extension": ".bin", "label": "Linux amd64"},
        {"os": "windows", "arch": "amd64", "extension": ".exe", "label": "Windows amd64"},
    ]


def test_beacon_build_creation_is_disabled_by_default(c2_client):
    token = connect_c2(c2_client)
    response = c2_client.post(
        "/api/v1/beacon-builds",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_os": "linux", "target_arch": "amd64", "c2_url": "http://c2.local:8001"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Beacon builds are disabled"


def test_filesystem_artifact_store_put_head_get_delete(tmp_path):
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'artifacts.db'}",
        artifact_storage_backend="filesystem",
        artifact_filesystem_dir=str(tmp_path / "artifacts"),
    )
    store = artifact_store_for_settings(settings)

    store.put("beacon-builds/build-one/xero-beacon.bin", b"payload", content_type="application/octet-stream")

    assert store.head("beacon-builds/build-one/xero-beacon.bin") is True
    assert store.get("beacon-builds/build-one/xero-beacon.bin") == b"payload"

    store.delete("beacon-builds/build-one/xero-beacon.bin")

    assert store.head("beacon-builds/build-one/xero-beacon.bin") is False
    with pytest.raises(ArtifactNotFound):
        store.get("beacon-builds/build-one/xero-beacon.bin")


def test_beacon_build_api_creates_fake_artifact_and_requires_auth_for_download(beacon_build_c2_client):
    token = connect_c2(beacon_build_c2_client)
    created = beacon_build_c2_client.post(
        "/api/v1/beacon-builds",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "target_os": "windows",
            "target_arch": "amd64",
            "c2_url": "http://c2.local:8001",
            "profile_name": "ops",
            "sleep_seconds": 15,
            "jitter": 0.2,
            "output_name": "ops-beacon",
        },
    )
    payload = created.json()
    unauthenticated_download = beacon_build_c2_client.get(f"/api/v1/beacon-builds/{payload['id']}/artifact")
    downloaded = beacon_build_c2_client.get(
        f"/api/v1/beacon-builds/{payload['id']}/artifact",
        headers={"Authorization": f"Bearer {token}"},
    )
    listed = beacon_build_c2_client.get("/api/v1/beacon-builds", headers={"Authorization": f"Bearer {token}"})

    assert created.status_code == 200
    assert payload["status"] == "succeeded"
    assert payload["artifact_filename"] == "ops-beacon.exe"
    assert payload["artifact_sha256"]
    assert payload["artifact_size"] > 0
    assert payload["artifact_available"] is True
    assert payload["config"]["profile_name"] == "ops"
    assert payload["config"]["c2_public_key_b64"]
    assert unauthenticated_download.status_code == 401
    assert downloaded.status_code == 200
    assert b"test fake beacon artifact" in downloaded.content
    assert listed.json()["items"][0]["id"] == payload["id"]
    assert listed.json()["items"][0]["artifact_available"] is True

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        build = session.get(BeaconBuild, uuid.UUID(payload["id"]))
        artifact = session.get(Artifact, build.artifact_id) if build is not None else None

    assert build is not None
    assert build.status == "succeeded"
    assert build.artifact_path is None
    assert artifact is not None
    assert artifact.namespace == "beacon-builds"
    assert artifact.owner_type == "beacon_build"
    assert artifact.object_key.endswith(f"/beacon-builds/{build.id}/ops-beacon.exe")
    assert artifact.sha256 == payload["artifact_sha256"]
    assert artifact.size_bytes == payload["artifact_size"]


def test_beacon_build_api_adds_linux_download_extension(beacon_build_c2_client):
    token = connect_c2(beacon_build_c2_client)
    created = beacon_build_c2_client.post(
        "/api/v1/beacon-builds",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "target_os": "linux",
            "target_arch": "amd64",
            "c2_url": "http://c2.local:8001",
            "output_name": "ops-beacon",
        },
    )
    payload = created.json()
    downloaded = beacon_build_c2_client.get(
        f"/api/v1/beacon-builds/{payload['id']}/artifact",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert created.status_code == 200
    assert payload["artifact_filename"] == "ops-beacon.bin"
    assert downloaded.status_code == 200
    assert 'filename="ops-beacon.bin"' in downloaded.headers["content-disposition"]


def test_beacon_build_api_reports_missing_artifact(beacon_build_c2_client):
    token = connect_c2(beacon_build_c2_client)
    created = beacon_build_c2_client.post(
        "/api/v1/beacon-builds",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_os": "linux", "target_arch": "amd64", "c2_url": "http://c2.local:8001"},
    )
    payload = created.json()

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        build = session.get(BeaconBuild, uuid.UUID(payload["id"]))
        assert build is not None
        assert build.artifact_id is not None
        artifact = session.get(Artifact, build.artifact_id)
        assert artifact is not None
        object_key = artifact.object_key
    artifact_store_for_settings(settings).delete(object_key)

    detail = beacon_build_c2_client.get(
        f"/api/v1/beacon-builds/{payload['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    listed = beacon_build_c2_client.get("/api/v1/beacon-builds", headers={"Authorization": f"Bearer {token}"})
    downloaded = beacon_build_c2_client.get(
        f"/api/v1/beacon-builds/{payload['id']}/artifact",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert detail.status_code == 200
    assert detail.json()["artifact_available"] is False
    assert listed.json()["items"][0]["artifact_available"] is False
    assert downloaded.status_code == 404
    assert downloaded.json()["detail"] == "Beacon build artifact not found"


def test_artifact_storage_rejects_default_minio_credentials_outside_local_modes():
    with pytest.raises(ValueError, match="C2_ARTIFACT_S3 credentials"):
        Settings(
            app_env="production",
            database_url="postgresql://user:pass@postgres:5432/db",
            redis_url="redis://redis:6379/0",
            jwt_secret_key="production-c2-jwt-secret-with-enough-length",
            c2_connect_password="production-c2-password",
            protocol_private_key_b64="production-protocol-private-key",
        )


def test_protocol_register_frame_updates_beacon_metadata_and_returns_ack(protocol_c2_client):
    token = connect_c2(protocol_c2_client)
    frame = encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1]))

    response = protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=frame,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    ack = decode_protocol_response(response.content)
    assert ack["acknowledged_message_type"] == "REGISTER"
    assert ack["selected_protocol_version"] == 1

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(ack["beacon_id"]))
        receipt = session.execute(select(ProtocolFrameReceipt)).scalar_one()

    assert beacon is not None
    assert beacon.protocol_version == 1
    assert beacon.protocol_session_id == receipt.session_id
    assert receipt.message_type == "REGISTER"


def test_protocol_task_result_frame_records_receipt(protocol_c2_client):
    token = connect_c2(protocol_c2_client)
    registered = register_beacon(protocol_c2_client)
    frame = encode_protocol_test_frame(
        TASK_RESULT,
        {
            "beacon_id": registered["beacon_id"],
            "output_digest": "sha256:abc123",
            "status": "completed",
            "task_id": "task-one",
        },
    )

    response = protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=frame,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 200
    ack = decode_protocol_response(response.content)
    assert ack["acknowledged_message_type"] == "TASK_RESULT"
    assert ack["receipt"] == "stored"

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        receipt = session.execute(select(ProtocolFrameReceipt)).scalar_one()

    assert receipt.beacon_id == uuid.UUID(registered["beacon_id"])
    assert receipt.message_type == "TASK_RESULT"


def test_task_api_creates_lists_and_cancels_queued_task(c2_client):
    registered = register_beacon(c2_client)
    token = connect_c2(c2_client)

    task = create_shell_task(c2_client, token, registered["beacon_id"], command="hostname", priority="high")
    listed = c2_client.get(
        f"/api/v1/tasks?beacon_id={registered['beacon_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    cancelled = c2_client.delete(f"/api/v1/tasks/{task['id']}", headers={"Authorization": f"Bearer {token}"})

    assert task["status"] == "queued"
    assert task["priority"] == "high"
    assert task["args"] == {"command": "hostname", "shell_type": "auto", "timeout_seconds": 60}
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [task["id"]]
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    audit = c2_client.get(f"/api/v1/tasks/{task['id']}/audit", headers={"Authorization": f"Bearer {token}"})
    audit_events = audit.json()["items"]
    assert audit.status_code == 200
    assert [event["event_type"] for event in audit_events] == ["task.cancelled", "task.queued"]
    assert {event["actor_subject"] for event in audit_events} == {"xero-ui-client"}


def test_task_api_filters_history_by_command(c2_client):
    registered = register_beacon(c2_client)
    token = connect_c2(c2_client)

    matching = create_shell_task(c2_client, token, registered["beacon_id"], command="whoami /groups")
    create_shell_task(c2_client, token, registered["beacon_id"], command="hostname")

    listed = c2_client.get(
        f"/api/v1/tasks?beacon_id={registered['beacon_id']}&command=whoami",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [matching["id"]]


def test_task_api_filters_history_by_failed_status(c2_client):
    registered = register_beacon(c2_client)
    token = connect_c2(c2_client)
    failed = create_shell_task(c2_client, token, registered["beacon_id"], command="bad-command")
    completed = create_shell_task(c2_client, token, registered["beacon_id"], command="hostname")

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    now = utc_now()
    with SessionFactory() as session:
        failed_task = session.get(Task, uuid.UUID(failed["id"]))
        completed_task = session.get(Task, uuid.UUID(completed["id"]))
        assert failed_task is not None
        assert completed_task is not None
        failed_task.status = "failed"
        failed_task.completed_at = now
        completed_task.status = "completed"
        completed_task.completed_at = now
        session.commit()

    listed = c2_client.get(
        f"/api/v1/tasks?beacon_id={registered['beacon_id']}&status=failed",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [failed["id"]]


def test_task_api_rejects_invalid_task_requests(c2_client):
    registered = register_beacon(c2_client)
    token = connect_c2(c2_client)

    blank = c2_client.post(
        "/api/v1/tasks",
        headers={"Authorization": f"Bearer {token}"},
        json={"beacon_id": registered["beacon_id"], "module": "shell", "args": {"command": "   "}},
    )
    excessive_timeout = c2_client.post(
        "/api/v1/tasks",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "beacon_id": registered["beacon_id"],
            "module": "shell",
            "args": {"command": "whoami", "timeout_seconds": 999999},
        },
    )
    unknown = c2_client.post(
        "/api/v1/tasks",
        headers={"Authorization": f"Bearer {token}"},
        json={"beacon_id": str(uuid.uuid4()), "module": "shell", "args": {"command": "whoami"}},
    )

    assert blank.status_code == 422
    assert excessive_timeout.status_code == 422
    assert unknown.status_code == 404


def test_protocol_task_poll_dispatches_highest_priority_task(protocol_c2_client):
    token = connect_c2(protocol_c2_client)
    register_response = protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )
    registered = decode_protocol_response(register_response.content)
    normal = create_shell_task(protocol_c2_client, token, registered["beacon_id"], command="normal", priority="normal")
    urgent = create_shell_task(protocol_c2_client, token, registered["beacon_id"], command="urgent", priority="urgent")

    poll_response = protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(TASK_POLL, {"beacon_id": registered["beacon_id"]}),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )
    ack = decode_protocol_response(poll_response.content)

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        normal_task = session.get(Task, uuid.UUID(normal["id"]))
        urgent_task = session.get(Task, uuid.UUID(urgent["id"]))
        audit_events = (
            session.execute(
                select(TaskAuditEvent)
                .where(TaskAuditEvent.task_id == uuid.UUID(urgent["id"]))
                .order_by(TaskAuditEvent.occurred_at)
            )
            .scalars()
            .all()
        )

    assert poll_response.status_code == 200
    assert ack["task"]["id"] == urgent["id"]
    assert ack["task"]["args"]["command"] == "urgent"
    assert normal_task is not None and normal_task.status == "queued"
    assert urgent_task is not None and urgent_task.status == "dispatched"
    assert urgent_task.dispatched_at is not None
    assert [event.event_type for event in audit_events] == ["task.queued", "task.dispatched"]


def test_task_result_updates_known_task_status(protocol_c2_client):
    token = connect_c2(protocol_c2_client)
    registered = decode_protocol_response(
        protocol_c2_client.post(
            "/api/v1/protocol/frames",
            content=encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
        ).content
    )
    task = create_shell_task(protocol_c2_client, token, registered["beacon_id"])
    protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(TASK_POLL, {"beacon_id": registered["beacon_id"]}),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )

    result_response = protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(
            TASK_RESULT,
            {
                "beacon_id": registered["beacon_id"],
                "exit_code": 0,
                "status": "completed",
                "stdout": "redacted",
                "task_id": task["id"],
                "timed_out": False,
                "truncated": False,
            },
        ),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )
    ack = decode_protocol_response(result_response.content)

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        stored = session.get(Task, uuid.UUID(task["id"]))
        result = session.execute(select(TaskResult).where(TaskResult.task_id == uuid.UUID(task["id"]))).scalar_one()
        audit_events = (
            session.execute(
                select(TaskAuditEvent)
                .where(TaskAuditEvent.task_id == uuid.UUID(task["id"]))
                .order_by(TaskAuditEvent.occurred_at)
            )
            .scalars()
            .all()
        )

    assert result_response.status_code == 200
    assert ack["receipt"] == "stored"
    assert ack["task"]["status"] == "completed"
    assert ack["task_result"]["task_id"] == task["id"]
    assert "stdout" not in ack["task_result"]
    assert "stdout" not in ack["task"]
    assert stored is not None
    assert stored.status == "completed"
    assert stored.completed_at is not None
    assert "stdout" not in stored.args
    assert result.stdout_text == "redacted"
    assert result.stderr_text == ""
    assert result.exit_code == 0
    assert [event.event_type for event in audit_events] == ["task.queued", "task.dispatched", "task.completed"]
    assert audit_events[-1].actor_subject == f"beacon:{registered['beacon_id']}"
    assert audit_events[-1].event_metadata == {"exit_code": 0, "timed_out": False, "truncated": False}

    fetched = protocol_c2_client.get(
        f"/api/v1/tasks/{task['id']}/result",
        headers={"Authorization": f"Bearer {token}"},
    )
    downloaded = protocol_c2_client.get(
        f"/api/v1/tasks/{task['id']}/result/download?stream=stdout",
        headers={"Authorization": f"Bearer {token}"},
    )
    history = protocol_c2_client.get("/api/v1/task-results", headers={"Authorization": f"Bearer {token}"})

    assert fetched.status_code == 200
    assert fetched.json()["stdout"] == "redacted"
    assert fetched.json()["stderr"] == ""
    assert downloaded.status_code == 200
    assert downloaded.content == b"redacted"
    assert 'filename="' in downloaded.headers["content-disposition"]
    assert history.status_code == 200
    assert history.json()["items"][0]["task_id"] == task["id"]


def test_task_result_completion_broadcasts_operator_event(protocol_c2_client):
    class BroadcastRecorder:
        def __init__(self) -> None:
            self.events: list[dict] = []

        async def broadcast(self, event: dict) -> None:
            self.events.append(event)

    recorder = BroadcastRecorder()
    protocol_c2_client.app.state.operator_realtime_hub = recorder
    token = connect_c2(protocol_c2_client)
    registered = decode_protocol_response(
        protocol_c2_client.post(
            "/api/v1/protocol/frames",
            content=encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
        ).content
    )
    task = create_shell_task(protocol_c2_client, token, registered["beacon_id"], command="broadcast-result")
    protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(TASK_POLL, {"beacon_id": registered["beacon_id"]}),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )

    protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(
            TASK_RESULT,
            {
                "beacon_id": registered["beacon_id"],
                "exit_code": 0,
                "status": "completed",
                "stdout": "broadcasted",
                "task_id": task["id"],
            },
        ),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )
    event_by_type = {event["type"]: event for event in recorder.events}
    task_event = event_by_type["task.completed"]
    result_event = event_by_type["task.result.completed"]

    assert task_event["type"] == "task.completed"
    assert result_event["type"] == "task.result.completed"
    assert result_event["scope"]["beacon_id"] == registered["beacon_id"]
    assert result_event["scope"]["task_id"] == task["id"]
    assert result_event["data"]["task_result"]["task_id"] == task["id"]
    assert "stdout" not in result_event["data"]["task_result"]


def test_task_result_chunk_broadcasts_operator_event(protocol_c2_client):
    class BroadcastRecorder:
        def __init__(self) -> None:
            self.events: list[dict] = []

        async def broadcast(self, event: dict) -> None:
            self.events.append(event)

    recorder = BroadcastRecorder()
    protocol_c2_client.app.state.operator_realtime_hub = recorder
    token = connect_c2(protocol_c2_client)
    registered = decode_protocol_response(
        protocol_c2_client.post(
            "/api/v1/protocol/frames",
            content=encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
        ).content
    )
    task = create_shell_task(protocol_c2_client, token, registered["beacon_id"], command="broadcast-chunk")
    protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(TASK_POLL, {"beacon_id": registered["beacon_id"]}),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )
    chunk_text = "first line\n"

    response = protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(
            TASK_RESULT,
            {
                "beacon_id": registered["beacon_id"],
                "task_id": task["id"],
                "status": "completed",
                "upload_id": "broadcast-upload",
                "stream": "stdout",
                "chunk_index": 0,
                "total_chunks": 2,
                "chunk": chunk_text,
                "chunk_sha256": hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
                "exit_code": 0,
            },
        ),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )
    ack = decode_protocol_response(response.content)
    event_by_type = {event["type"]: event for event in recorder.events}
    chunk_event = event_by_type["task.result.chunk"]

    assert response.status_code == 200
    assert ack["receipt"] == "chunk_stored"
    assert ack["task_result_chunk_event_type"] == "task.result.chunk"
    assert ack["task_result_chunk"]["chunk"] == chunk_text
    assert chunk_event["scope"]["beacon_id"] == registered["beacon_id"]
    assert chunk_event["scope"]["task_id"] == task["id"]
    assert chunk_event["data"]["task_result_chunk"]["task_id"] == task["id"]
    assert chunk_event["data"]["task_result_chunk"]["sequence"] == 0
    assert chunk_event["data"]["task_result_chunk"]["chunk"] == chunk_text
    assert "task.result.completed" not in event_by_type


def test_chunked_task_result_assembles_and_uses_artifact_storage(result_c2_client):
    token = connect_c2(result_c2_client)
    registered = decode_protocol_response(
        result_c2_client.post(
            "/api/v1/protocol/frames",
            content=encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
        ).content
    )
    task = create_shell_task(result_c2_client, token, registered["beacon_id"], command="chunked")
    result_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(TASK_POLL, {"beacon_id": registered["beacon_id"]}),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )

    chunks = ["a" * 600, "b" * 600]
    stdout = "".join(chunks)
    upload_id = f"upload-{uuid.uuid4()}"
    stream_sha = hashlib.sha256(stdout.encode("utf-8")).hexdigest()

    first = result_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(
            TASK_RESULT,
            {
                "beacon_id": registered["beacon_id"],
                "task_id": task["id"],
                "status": "completed",
                "upload_id": upload_id,
                "stream": "stdout",
                "chunk_index": 0,
                "total_chunks": 2,
                "chunk": chunks[0],
                "chunk_sha256": hashlib.sha256(chunks[0].encode("utf-8")).hexdigest(),
                "stream_sha256": stream_sha,
                "stream_size_bytes": len(stdout.encode("utf-8")),
                "exit_code": 0,
            },
        ),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )
    first_ack = decode_protocol_response(first.content)

    final = result_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(
            TASK_RESULT,
            {
                "beacon_id": registered["beacon_id"],
                "task_id": task["id"],
                "status": "completed",
                "upload_id": upload_id,
                "stream": "stdout",
                "chunk_index": 1,
                "total_chunks": 2,
                "chunk": chunks[1],
                "chunk_sha256": hashlib.sha256(chunks[1].encode("utf-8")).hexdigest(),
                "stream_sha256": stream_sha,
                "stream_size_bytes": len(stdout.encode("utf-8")),
                "result_final": True,
                "exit_code": 0,
                "stderr": "",
            },
        ),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )
    final_ack = decode_protocol_response(final.content)
    fetched = result_c2_client.get(
        f"/api/v1/tasks/{task['id']}/result",
        headers={"Authorization": f"Bearer {token}"},
    )
    downloaded = result_c2_client.get(
        f"/api/v1/tasks/{task['id']}/result/download?stream=combined",
        headers={"Authorization": f"Bearer {token}"},
    )

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        stored = session.get(Task, uuid.UUID(task["id"]))
        result = session.execute(select(TaskResult).where(TaskResult.task_id == uuid.UUID(task["id"]))).scalar_one()
        chunk_count = (
            session.execute(select(ResultChunk).where(ResultChunk.task_result_id == result.id)).scalars().all()
        )

    assert first.status_code == 200
    assert first_ack["receipt"] == "chunk_stored"
    assert first_ack["task_result_chunk_event_type"] == "task.result.chunk"
    assert first_ack["task_result_chunk"]["sequence"] == 0
    assert first_ack["task_result_chunk"]["chunk"] == chunks[0]
    assert "task" not in first_ack
    assert final.status_code == 200
    assert final_ack["receipt"] == "stored"
    assert final_ack["task"]["status"] == "completed"
    assert final_ack["task_result_chunk_event_type"] == "task.result.chunk"
    assert final_ack["task_result_chunk"]["sequence"] == 1
    assert final_ack["task_result_event_type"] == "task.result.completed"
    assert fetched.status_code == 200
    assert fetched.json()["stdout"] == stdout
    assert fetched.json()["artifacts"][0]["role"] == "stdout"
    assert fetched.json()["artifacts"][0]["available"] is True
    assert downloaded.content == stdout.encode("utf-8")
    assert stored is not None and stored.status == "completed"
    assert result.stdout_text is None
    assert len(chunk_count) == 2

    listed_chunks = result_c2_client.get(
        f"/api/v1/tasks/{task['id']}/result/chunks?stream=stdout",
        headers={"Authorization": f"Bearer {token}"},
    )
    resumed_chunks = result_c2_client.get(
        f"/api/v1/tasks/{task['id']}/result/chunks?stream=stdout&upload_id={upload_id}&after_sequence=0",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert listed_chunks.status_code == 200
    assert [item["sequence"] for item in listed_chunks.json()["items"]] == [0, 1]
    assert resumed_chunks.status_code == 200
    assert [item["sequence"] for item in resumed_chunks.json()["items"]] == [1]
    assert resumed_chunks.json()["items"][0]["chunk"] == chunks[1]


def test_chunked_task_result_rejects_missing_chunks(result_c2_client):
    token = connect_c2(result_c2_client)
    registered = decode_protocol_response(
        result_c2_client.post(
            "/api/v1/protocol/frames",
            content=encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
        ).content
    )
    task = create_shell_task(result_c2_client, token, registered["beacon_id"], command="missing-chunk")
    result_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(TASK_POLL, {"beacon_id": registered["beacon_id"]}),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )
    chunk = "tail"

    response = result_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(
            TASK_RESULT,
            {
                "beacon_id": registered["beacon_id"],
                "task_id": task["id"],
                "status": "completed",
                "upload_id": f"upload-{uuid.uuid4()}",
                "stream": "stdout",
                "chunk_index": 1,
                "total_chunks": 2,
                "chunk": chunk,
                "chunk_sha256": hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
                "stream_sha256": hashlib.sha256(b"headtail").hexdigest(),
                "stream_size_bytes": len(b"headtail"),
                "result_final": True,
            },
        ),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_PAYLOAD"

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        stored = session.get(Task, uuid.UUID(task["id"]))
        result = (
            session.execute(select(TaskResult).where(TaskResult.task_id == uuid.UUID(task["id"]))).scalar_one_or_none()
        )

    assert stored is not None and stored.status == "dispatched"
    assert result is None


def test_expired_task_result_purge_removes_artifacts(result_c2_client):
    token = connect_c2(result_c2_client)
    registered = decode_protocol_response(
        result_c2_client.post(
            "/api/v1/protocol/frames",
            content=encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
        ).content
    )
    task = create_shell_task(result_c2_client, token, registered["beacon_id"], command="expire-result")
    result_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(TASK_POLL, {"beacon_id": registered["beacon_id"]}),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )
    stdout = "x" * 1200
    result_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(
            TASK_RESULT,
            {
                "beacon_id": registered["beacon_id"],
                "exit_code": 0,
                "status": "completed",
                "stdout": stdout,
                "task_id": task["id"],
            },
        ),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )

    settings = get_settings()
    store = artifact_store_for_settings(settings)
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        result = session.execute(select(TaskResult).where(TaskResult.task_id == uuid.UUID(task["id"]))).scalar_one()
        artifact = (
            session.execute(
                select(Artifact).where(Artifact.owner_id == result.id, Artifact.owner_type == "task_result")
            )
            .scalars()
            .one()
        )
        object_key = artifact.object_key
        assert store.head(object_key)
        result.expires_at = utc_now() - timedelta(seconds=1)
        session.add(result)
        deleted = purge_expired_task_results(session, settings)
        session.commit()

    with SessionFactory() as session:
        result = (
            session.execute(select(TaskResult).where(TaskResult.task_id == uuid.UUID(task["id"]))).scalar_one_or_none()
        )
        artifact = session.execute(select(Artifact).where(Artifact.owner_type == "task_result")).scalar_one_or_none()

    assert deleted == 1
    assert result is None
    assert artifact is None
    assert not store.head(object_key)


def test_cancel_dispatched_task_returns_conflict(protocol_c2_client):
    token = connect_c2(protocol_c2_client)
    registered = decode_protocol_response(
        protocol_c2_client.post(
            "/api/v1/protocol/frames",
            content=encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
        ).content
    )
    task = create_shell_task(protocol_c2_client, token, registered["beacon_id"])
    protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(TASK_POLL, {"beacon_id": registered["beacon_id"]}),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )

    response = protocol_c2_client.delete(f"/api/v1/tasks/{task['id']}", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 409


def test_cancelled_queued_task_is_not_dispatched(protocol_c2_client):
    token = connect_c2(protocol_c2_client)
    registered = decode_protocol_response(
        protocol_c2_client.post(
            "/api/v1/protocol/frames",
            content=encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
        ).content
    )
    task = create_shell_task(protocol_c2_client, token, registered["beacon_id"])
    protocol_c2_client.delete(f"/api/v1/tasks/{task['id']}", headers={"Authorization": f"Bearer {token}"})

    response = protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(TASK_POLL, {"beacon_id": registered["beacon_id"]}),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )
    ack = decode_protocol_response(response.content)

    assert response.status_code == 200
    assert ack["task"] is None


def test_protocol_hmac_tamper_rejected_and_logged(protocol_c2_client):
    token = connect_c2(protocol_c2_client)
    frame = bytearray(encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])))
    frame[-1] ^= 0x01

    response = protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=bytes(frame),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "HMAC_MISMATCH"

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        event = session.execute(select(ProtocolSecurityEvent)).scalar_one()

    assert event.event_type == "protocol.hmac_mismatch"
    assert event.severity == "high"
    assert event.session_id
    assert event.nonce


def test_protocol_replay_nonce_rejected_and_logged(protocol_c2_client):
    token = connect_c2(protocol_c2_client)
    frame = encode_protocol_test_frame(
        REGISTER,
        register_payload(supported_versions=[1]),
        nonce=bytes.fromhex("0a0b0c0d0e0f101112131415"),
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"}

    first = protocol_c2_client.post("/api/v1/protocol/frames", content=frame, headers=headers)
    second = protocol_c2_client.post("/api/v1/protocol/frames", content=frame, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "REPLAY_DETECTED"

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        event = session.execute(select(ProtocolSecurityEvent)).scalar_one()

    assert event.event_type == "protocol.replay_detected"


def test_security_events_endpoint_lists_protocol_events(protocol_c2_client):
    token = connect_c2(protocol_c2_client)
    frame = bytearray(encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])))
    frame[-1] ^= 0x01
    protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=bytes(frame),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )

    response = protocol_c2_client.get("/api/v1/security/events", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["items"][0]["event_type"] == "protocol.hmac_mismatch"


def test_transport_status_requires_auth_and_reports_websocket_count(protocol_c2_client):
    unauthenticated = protocol_c2_client.get("/api/v1/transport")
    token = connect_c2(protocol_c2_client)

    assert unauthenticated.status_code == 401
    assert protocol_c2_client.get(
        "/api/v1/transport",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["active_websocket_connections"] == 0

    with protocol_c2_client.websocket_connect("/ws/beacon", subprotocols=["xero.beacon.v1"]) as websocket:
        websocket.send_bytes(encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])))
        ack = decode_protocol_response(websocket.receive_bytes())
        assert ack["transport"] == "websocket"

        connected = protocol_c2_client.get("/api/v1/transport", headers={"Authorization": f"Bearer {token}"})
        assert connected.json()["active_websocket_connections"] == 1

    disconnected = protocol_c2_client.get("/api/v1/transport", headers={"Authorization": f"Bearer {token}"})
    assert disconnected.json()["active_websocket_connections"] == 0


def test_longpoll_holds_reports_active_rejects_duplicate_and_times_out(longpoll_c2_client):
    c2_token = connect_c2(longpoll_c2_client)
    registered = register_beacon(longpoll_c2_client)
    beacon_headers = {"Authorization": f"Bearer {registered['beacon_token']}"}
    c2_headers = {"Authorization": f"Bearer {c2_token}"}
    result: dict[str, object] = {}

    def hold_poll() -> None:
        result["response"] = longpoll_c2_client.get(
            f"/api/v1/beacons/{registered['beacon_id']}/poll?timeout_seconds=1",
            headers=beacon_headers,
        )

    thread = threading.Thread(target=hold_poll)
    thread.start()
    try:
        deadline = time.monotonic() + 2
        active_status = None
        while time.monotonic() < deadline:
            active_status = longpoll_c2_client.get("/api/v1/transport", headers=c2_headers).json()
            if active_status["active_longpoll_requests"] == 1:
                break
            time.sleep(0.05)
        assert active_status is not None
        assert active_status["active_longpoll_requests"] == 1

        duplicate = longpoll_c2_client.get(
            f"/api/v1/beacons/{registered['beacon_id']}/poll?timeout_seconds=1",
            headers=beacon_headers,
        )
        assert duplicate.status_code == 409
    finally:
        thread.join(timeout=3)

    assert not thread.is_alive()
    response = result["response"]
    assert response.status_code == 204

    disconnected = longpoll_c2_client.get("/api/v1/transport", headers=c2_headers).json()
    assert disconnected["active_longpoll_requests"] == 0
    assert disconnected["transport_mode_counts"]["long-poll"] == 1

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))

    assert beacon is not None
    assert beacon.transport_mode == "long-poll"
    assert beacon.transport_connected is False


def test_longpoll_frame_post_decodes_shared_protocol_messages(longpoll_c2_client):
    registered = register_beacon(longpoll_c2_client)
    headers = {"Authorization": f"Bearer {registered['beacon_token']}", "Content-Type": "application/octet-stream"}
    heartbeat = encode_protocol_test_frame(
        HEARTBEAT,
        {"beacon_id": registered["beacon_id"], "hostname": "longpoll-heartbeat"},
    )
    poll = encode_protocol_test_frame(TASK_POLL, {"beacon_id": registered["beacon_id"]})
    result = encode_protocol_test_frame(
        TASK_RESULT,
        {
            "beacon_id": registered["beacon_id"],
            "output_digest": "sha256:longpoll",
            "status": "completed",
            "task_id": "lp-task",
        },
    )

    heartbeat_response = longpoll_c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/frame",
        content=heartbeat,
        headers=headers,
    )
    poll_response = longpoll_c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/frame",
        content=poll,
        headers=headers,
    )
    result_response = longpoll_c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/frame",
        content=result,
        headers=headers,
    )

    heartbeat_ack = decode_protocol_response(heartbeat_response.content)
    poll_ack = decode_protocol_response(poll_response.content)
    result_ack = decode_protocol_response(result_response.content)
    assert heartbeat_response.status_code == 200
    assert heartbeat_ack["acknowledged_message_type"] == "HEARTBEAT"
    assert heartbeat_ack["transport"] == "long-poll"
    assert poll_ack["task"] is None
    assert result_ack["receipt"] == "stored"

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        receipts = session.execute(select(ProtocolFrameReceipt)).scalars().all()

    assert beacon is not None
    assert beacon.hostname == "longpoll-heartbeat"
    assert beacon.transport_mode == "long-poll"
    assert beacon.transport_connected is False
    assert [receipt.message_type for receipt in receipts] == ["HEARTBEAT", "TASK_POLL", "TASK_RESULT"]


def test_longpoll_poll_returns_encrypted_queued_task(longpoll_c2_client):
    registered = register_beacon(longpoll_c2_client)
    token = connect_c2(longpoll_c2_client)
    headers = {"Authorization": f"Bearer {registered['beacon_token']}", "Content-Type": "application/octet-stream"}
    heartbeat_response = longpoll_c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/frame",
        content=encode_protocol_test_frame(HEARTBEAT, {"beacon_id": registered["beacon_id"]}),
        headers=headers,
    )
    task = create_shell_task(longpoll_c2_client, token, registered["beacon_id"], command="id", priority="urgent")

    poll_response = longpoll_c2_client.get(
        f"/api/v1/beacons/{registered['beacon_id']}/poll",
        headers={"Authorization": f"Bearer {registered['beacon_token']}"},
    )
    ack = decode_protocol_response(poll_response.content)

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        stored = session.get(Task, uuid.UUID(task["id"]))

    assert heartbeat_response.status_code == 200
    assert poll_response.status_code == 200
    assert ack["acknowledged_message_type"] == TASK_POLL
    assert ack["task"]["id"] == task["id"]
    assert stored is not None and stored.status == "dispatched"


def test_longpoll_frame_post_rejects_beacon_id_mismatch_with_encrypted_error(longpoll_c2_client):
    registered = register_beacon(longpoll_c2_client)
    frame = encode_protocol_test_frame(TASK_POLL, {"beacon_id": str(uuid.uuid4())})

    response = longpoll_c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/frame",
        content=frame,
        headers={"Authorization": f"Bearer {registered['beacon_token']}", "Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/octet-stream"
    error_payload = decode_protocol_response(response.content)
    assert error_payload["code"] == "BEACON_ID_MISMATCH"

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        event = session.execute(select(ProtocolSecurityEvent)).scalar_one()

    assert event.event_type == "protocol.beacon_id_mismatch"
    assert event.beacon_id == uuid.UUID(registered["beacon_id"])


def test_longpoll_frame_post_hmac_tamper_and_replay_are_logged(longpoll_c2_client):
    registered = register_beacon(longpoll_c2_client)
    headers = {"Authorization": f"Bearer {registered['beacon_token']}", "Content-Type": "application/octet-stream"}

    tampered = bytearray(encode_protocol_test_frame(TASK_POLL, {"beacon_id": registered["beacon_id"]}))
    tampered[-1] ^= 0x01
    tampered_response = longpoll_c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/frame",
        content=bytes(tampered),
        headers=headers,
    )

    replay = encode_protocol_test_frame(
        TASK_POLL,
        {"beacon_id": registered["beacon_id"]},
        nonce=bytes.fromhex("202122232425262728292a2b"),
    )
    frame_path = f"/api/v1/beacons/{registered['beacon_id']}/frame"
    first_replay = longpoll_c2_client.post(frame_path, content=replay, headers=headers)
    second_replay = longpoll_c2_client.post(frame_path, content=replay, headers=headers)

    assert tampered_response.status_code == 401
    assert tampered_response.json()["code"] == "HMAC_MISMATCH"
    assert first_replay.status_code == 200
    assert second_replay.status_code == 409
    assert second_replay.json()["code"] == "REPLAY_DETECTED"

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        event_types = {
            event.event_type
            for event in session.execute(
                select(ProtocolSecurityEvent).order_by(ProtocolSecurityEvent.occurred_at)
            ).scalars()
        }

    assert {"protocol.hmac_mismatch", "protocol.replay_detected"}.issubset(event_types)


def test_longpoll_frame_post_oversize_rejected_and_logged(monkeypatch, tmp_path, make_c2_client):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'tiny-longpoll.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("C2_DATABASE_URL", database_url)
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "connect-me")
    monkeypatch.setenv("C2_JWT_SECRET_KEY", "test-c2-jwt-secret-with-enough-length")
    monkeypatch.setenv("C2_BEACON_LONGPOLL_MAX_FRAME_BYTES", "256")
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(database_url))
    client = make_c2_client(C2_DATABASE_URL=database_url, C2_BEACON_LONGPOLL_MAX_FRAME_BYTES="256")
    registered = register_beacon(client)

    response = client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/frame",
        content=b"x" * 257,
        headers={"Authorization": f"Bearer {registered['beacon_token']}", "Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 413
    assert response.json()["code"] == "FRAME_TOO_LARGE"

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        event = session.execute(select(ProtocolSecurityEvent)).scalar_one()

    assert event.event_type == "protocol.frame_too_large"


def test_beacon_websocket_registers_and_returns_encrypted_ack(protocol_c2_client):
    frame = encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1]))

    with protocol_c2_client.websocket_connect("/ws/beacon", subprotocols=["xero.beacon.v1"]) as websocket:
        websocket.send_bytes(frame)
        ack = decode_protocol_response(websocket.receive_bytes())

        assert ack["acknowledged_message_type"] == "REGISTER"
        assert ack["beacon_id"]
        assert ack["beacon_token"]
        assert ack["selected_protocol_version"] == 1
        assert ack["transport"] == "websocket"

        settings = get_settings()
        SessionFactory = get_session_factory(settings.database_url)
        with SessionFactory() as session:
            beacon = session.get(Beacon, uuid.UUID(ack["beacon_id"]))
            receipt = session.execute(select(ProtocolFrameReceipt)).scalar_one()

        assert beacon is not None
        assert beacon.transport_mode == "websocket"
        assert beacon.transport_connected is True
        assert beacon.transport_last_seen is not None
        assert receipt.message_type == "REGISTER"


def test_beacon_websocket_task_poll_receives_queued_task(protocol_c2_client):
    token = connect_c2(protocol_c2_client)

    with protocol_c2_client.websocket_connect("/ws/beacon", subprotocols=["xero.beacon.v1"]) as websocket:
        websocket.send_bytes(encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])))
        registered = decode_protocol_response(websocket.receive_bytes())
        task = create_shell_task(protocol_c2_client, token, registered["beacon_id"], command="whoami", priority="high")

        websocket.send_bytes(encode_protocol_test_frame(TASK_POLL, {"beacon_id": registered["beacon_id"]}))
        ack = decode_protocol_response(websocket.receive_bytes())

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        stored = session.get(Task, uuid.UUID(task["id"]))

    assert ack["acknowledged_message_type"] == TASK_POLL
    assert ack["task"]["id"] == task["id"]
    assert ack["task"]["args"]["command"] == "whoami"
    assert stored is not None and stored.status == "dispatched"


def test_shell_session_open_sends_session_data_to_connected_beacon(protocol_c2_client, monkeypatch):
    token = connect_c2(protocol_c2_client)
    registered = register_beacon(protocol_c2_client)
    attach_protocol_metadata(registered["beacon_id"])
    sent_frames: list[bytes] = []

    async def capture_send(_, frame: bytes) -> bool:
        sent_frames.append(frame)
        return True

    monkeypatch.setattr(protocol_c2_client.app.state.beacon_transport_manager, "send_to_beacon", capture_send)

    created = protocol_c2_client.post(
        "/api/v1/sessions/shell",
        headers={"Authorization": f"Bearer {token}"},
        json={"beacon_id": registered["beacon_id"], "cols": 100, "rows": 28, "shell_type": "powershell"},
    )
    session_payload = created.json()
    open_frame = decode_protocol_response(sent_frames[0], expected_message_type=SESSION_DATA)

    assert created.status_code == 200
    assert session_payload["status"] == "opening"
    assert session_payload["shell_type"] == "powershell"
    assert open_frame["op"] == "open"
    assert open_frame["beacon_id"] == registered["beacon_id"]
    assert open_frame["session_id"] == session_payload["id"]
    assert open_frame["cols"] == 100
    assert open_frame["rows"] == 28

    ack_response = protocol_c2_client.post(
        "/api/v1/protocol/frames",
        content=encode_protocol_test_frame(
            SESSION_DATA,
            {
                "beacon_id": registered["beacon_id"],
                "op": "open_ack",
                "session_id": session_payload["id"],
            },
        ),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )
    ack = decode_protocol_response(ack_response.content)

    assert ack_response.status_code == 200
    assert ack["acknowledged_message_type"] == SESSION_DATA

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        stored = session.get(InteractiveSession, uuid.UUID(session_payload["id"]))

    assert stored is not None
    assert stored.status == "open"


def test_shell_session_close_sends_session_data_and_marks_closed(protocol_c2_client, monkeypatch):
    token = connect_c2(protocol_c2_client)
    registered = register_beacon(protocol_c2_client)
    attach_protocol_metadata(registered["beacon_id"])
    sent_frames: list[bytes] = []

    async def capture_send(_, frame: bytes) -> bool:
        sent_frames.append(frame)
        return True

    monkeypatch.setattr(protocol_c2_client.app.state.beacon_transport_manager, "send_to_beacon", capture_send)

    created = protocol_c2_client.post(
        "/api/v1/sessions/shell",
        headers={"Authorization": f"Bearer {token}"},
        json={"beacon_id": registered["beacon_id"], "cols": 100, "rows": 28, "shell_type": "powershell"},
    )
    session_payload = created.json()

    closed = protocol_c2_client.delete(
        f"/api/v1/sessions/{session_payload['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    close_frame = decode_protocol_response(sent_frames[-1], expected_message_type=SESSION_DATA)

    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert closed.json()["close_reason"] == "operator"
    assert close_frame["op"] == "close"
    assert close_frame["reason"] == "operator"
    assert close_frame["session_id"] == session_payload["id"]


def test_file_browser_session_open_sends_session_data_to_connected_beacon(protocol_c2_client, monkeypatch):
    token = connect_c2(protocol_c2_client)
    registered = register_beacon(protocol_c2_client)
    attach_protocol_metadata(registered["beacon_id"])
    sent_frames: list[bytes] = []

    async def capture_send(_, frame: bytes) -> bool:
        sent_frames.append(frame)
        return True

    monkeypatch.setattr(protocol_c2_client.app.state.beacon_transport_manager, "send_to_beacon", capture_send)

    created = protocol_c2_client.post(
        "/api/v1/sessions/file-browser",
        headers={"Authorization": f"Bearer {token}"},
        json={"beacon_id": registered["beacon_id"], "root_path": "/home"},
    )
    session_payload = created.json()
    open_frame = decode_protocol_response(sent_frames[0], expected_message_type=SESSION_DATA)

    assert created.status_code == 200
    assert session_payload["status"] == "opening"
    assert session_payload["session_type"] == "file_browser"
    assert open_frame["op"] == "open"
    assert open_frame["beacon_id"] == registered["beacon_id"]
    assert open_frame["session_id"] == session_payload["id"]
    assert open_frame["session_type"] == "file_browser"
    assert open_frame["root_path"] == "/home"


def test_registry_session_open_sends_session_data_to_connected_windows_beacon(protocol_c2_client, monkeypatch):
    token = connect_c2(protocol_c2_client)
    registered = register_beacon(protocol_c2_client, os="Windows 11")
    attach_protocol_metadata(registered["beacon_id"])
    sent_frames: list[bytes] = []

    async def capture_send(_, frame: bytes) -> bool:
        sent_frames.append(frame)
        return True

    monkeypatch.setattr(protocol_c2_client.app.state.beacon_transport_manager, "send_to_beacon", capture_send)

    created = protocol_c2_client.post(
        "/api/v1/sessions/registry",
        headers={"Authorization": f"Bearer {token}"},
        json={"beacon_id": registered["beacon_id"]},
    )
    session_payload = created.json()
    open_frame = decode_protocol_response(sent_frames[0], expected_message_type=SESSION_DATA)

    assert created.status_code == 200
    assert session_payload["status"] == "opening"
    assert session_payload["session_type"] == "registry"
    assert open_frame["op"] == "open"
    assert open_frame["beacon_id"] == registered["beacon_id"]
    assert open_frame["session_id"] == session_payload["id"]
    assert open_frame["session_type"] == "registry"


def test_registry_session_rejects_non_windows_beacon(protocol_c2_client):
    token = connect_c2(protocol_c2_client)
    registered = register_beacon(protocol_c2_client, os="Ubuntu 24.04")
    attach_protocol_metadata(registered["beacon_id"])

    response = protocol_c2_client.post(
        "/api/v1/sessions/registry",
        headers={"Authorization": f"Bearer {token}"},
        json={"beacon_id": registered["beacon_id"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Registry sessions require a Windows beacon"


def test_registry_request_rejects_key_delete_operations():
    with pytest.raises(ValueError, match="Registry message op is invalid"):
        parse_registry_request(
            json.dumps(
                {
                    "hive": "HKCU",
                    "key_path": "",
                    "op": "reg_delete_key",
                    "request_id": "delete-root",
                }
            )
        )


def test_file_browser_session_data_preserves_request_id_and_cache_payload(c2_client):
    registered = register_beacon(c2_client)

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        file_session = InteractiveSession(
            actor_subject="operator:test",
            beacon_id=beacon.id,
            session_type="file_browser",
            shell_type="none",
            status="open",
        )
        session.add(file_session)
        session.commit()
        outcome = apply_beacon_session_data(
            session,
            beacon_id=beacon.id,
            payload={
                "beacon_id": registered["beacon_id"],
                "entries": [
                    {
                        "modified_at": "2026-06-13T00:00:00Z",
                        "name": "notes.txt",
                        "path": "docs/notes.txt",
                        "permissions": "-rw-r--r--",
                        "size": 42,
                        "type": "file",
                    }
                ],
                "ok": True,
                "op": "list_dir",
                "path": "docs",
                "request_id": "seq-1",
                "session_id": str(file_session.id),
                "session_type": "file_browser",
            },
        )

    assert outcome.event_type == "session.file.response.received"
    assert outcome.operator_message is not None
    assert outcome.operator_message["op"] == "list_dir"
    assert outcome.operator_message["request_id"] == "seq-1"
    assert outcome.operator_message["path"] == "docs"
    assert outcome.operator_message["entries"][0]["name"] == "notes.txt"
    assert outcome.cache_listing is not None


def test_file_browser_cache_returns_cached_listing_with_new_request_id():
    async def scenario() -> dict | None:
        cache = FileListingCache(ttl_seconds=5)
        session_id = uuid.uuid4()
        await cache.store(
            session_id,
            {
                "entries": [{"name": "cached.txt", "path": "cached.txt", "type": "file"}],
                "ok": True,
                "op": "list_dir",
                "path": "",
                "request_id": "old-seq",
                "session_id": str(session_id),
            },
        )
        return await cache.get(session_id, "", request_id="new-seq")

    cached = asyncio.run(scenario())

    assert cached is not None
    assert cached["cached"] is True
    assert cached["request_id"] == "new-seq"
    assert cached["entries"][0]["name"] == "cached.txt"


def test_file_browser_access_error_keeps_session_open(c2_client):
    registered = register_beacon(c2_client)

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        file_session = InteractiveSession(
            actor_subject="operator:test",
            beacon_id=beacon.id,
            session_type="file_browser",
            shell_type="none",
            status="open",
        )
        session.add(file_session)
        session.commit()
        outcome = apply_beacon_session_data(
            session,
            beacon_id=beacon.id,
            payload={
                "beacon_id": registered["beacon_id"],
                "error_code": "access_denied",
                "message": "access denied",
                "ok": False,
                "op": "list_dir",
                "path": "root",
                "request_id": "seq-denied",
                "session_id": str(file_session.id),
                "session_type": "file_browser",
            },
        )
        session.refresh(file_session)

    assert outcome.event_type == "session.file.error"
    assert outcome.operator_message is not None
    assert outcome.operator_message["ok"] is False
    assert outcome.operator_message["error_code"] == "access_denied"
    assert outcome.operator_message["request_id"] == "seq-denied"
    assert file_session.status == "open"


def test_file_transfer_upload_stages_chunks_and_records_ack(result_c2_client, monkeypatch):
    token = connect_c2(result_c2_client)
    registered = register_beacon(result_c2_client)
    attach_protocol_metadata(registered["beacon_id"])

    async def capture_send(_, _frame: bytes) -> bool:
        return True

    monkeypatch.setattr(result_c2_client.app.state.beacon_transport_manager, "send_to_beacon", capture_send)
    created_session = result_c2_client.post(
        "/api/v1/sessions/file-browser",
        headers={"Authorization": f"Bearer {token}"},
        json={"beacon_id": registered["beacon_id"]},
    ).json()
    content = b"hello transfer"
    created = result_c2_client.post(
        "/api/v1/file-transfers/uploads",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "beacon_id": registered["beacon_id"],
            "filename": "payload.bin",
            "remote_path": "payload.bin",
            "session_id": created_session["id"],
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        },
    )
    transfer = created.json()
    staged = result_c2_client.put(
        f"/api/v1/file-transfers/{transfer['id']}/chunks/0",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "chunk_sha256": hashlib.sha256(content).hexdigest(),
            "data_b64": base64.b64encode(content).decode("ascii"),
        },
    )

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        stored = session.get(FileTransfer, uuid.UUID(transfer["id"]))
        assert stored is not None
        outcome = apply_beacon_session_data(
            session,
            beacon_id=uuid.UUID(registered["beacon_id"]),
            payload={
                "op": "upload_ack",
                "request_id": "upload-ack-0",
                "sequence": 0,
                "session_id": created_session["id"],
                "session_type": "file_browser",
                "transfer_id": transfer["id"],
            },
            settings=settings,
        )
        session.commit()
        chunks = (
            session.execute(select(FileTransferChunk).where(FileTransferChunk.transfer_id == stored.id))
            .scalars()
            .all()
        )
        session.refresh(stored)

    assert created.status_code == 200
    assert transfer["total_chunks"] == 1
    assert staged.status_code == 200
    assert staged.json()["staged_chunks"] == 1
    assert outcome.operator_message is not None
    json.dumps(outcome.operator_message)
    assert outcome.operator_message["op"] == "upload_ack"
    assert outcome.operator_message["next_sequence"] is None
    assert isinstance(outcome.operator_message["updated_at"], str)
    assert stored.acked_chunks == 1
    assert len(chunks) == 1
    assert chunks[0].acked_at is not None


def test_file_transfer_upload_rejects_hash_mismatch(result_c2_client, monkeypatch):
    token = connect_c2(result_c2_client)
    registered = register_beacon(result_c2_client)
    attach_protocol_metadata(registered["beacon_id"])

    async def capture_send(_, _frame: bytes) -> bool:
        return True

    monkeypatch.setattr(result_c2_client.app.state.beacon_transport_manager, "send_to_beacon", capture_send)
    created_session = result_c2_client.post(
        "/api/v1/sessions/file-browser",
        headers={"Authorization": f"Bearer {token}"},
        json={"beacon_id": registered["beacon_id"]},
    ).json()
    content = b"hello transfer"
    transfer = result_c2_client.post(
        "/api/v1/file-transfers/uploads",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "beacon_id": registered["beacon_id"],
            "filename": "payload.bin",
            "remote_path": "payload.bin",
            "session_id": created_session["id"],
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        },
    ).json()

    rejected = result_c2_client.put(
        f"/api/v1/file-transfers/{transfer['id']}/chunks/0",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "chunk_sha256": "0" * 64,
            "data_b64": base64.b64encode(content).decode("ascii"),
        },
    )

    assert rejected.status_code == 400
    assert "SHA-256" in rejected.json()["detail"]


def test_file_transfer_download_reassembles_artifact(result_c2_client):
    registered = register_beacon(result_c2_client)
    content = b"alpha-bravo"
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        file_session = InteractiveSession(
            actor_subject="operator:admin",
            beacon_id=beacon.id,
            session_type="file_browser",
            shell_type="none",
            status="open",
        )
        session.add(file_session)
        session.flush()
        transfer = create_download_transfer(
            session,
            actor_subject="operator:admin",
            beacon_id=beacon.id,
            session_id=file_session.id,
            remote_path="loot.bin",
            chunk_size_bytes=6,
        )
        session.commit()
        outcome_ready = apply_beacon_session_data(
            session,
            beacon_id=beacon.id,
            payload={
                "chunk_size_bytes": 6,
                "op": "download_ready",
                "path": "loot.bin",
                "request_id": "download-ready",
                "session_id": str(file_session.id),
                "session_type": "file_browser",
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
                "total_chunks": 2,
                "transfer_id": str(transfer.id),
            },
            settings=settings,
        )
        outcome_first = apply_beacon_session_data(
            session,
            beacon_id=beacon.id,
            payload={
                "chunk_sha256": hashlib.sha256(content[:6]).hexdigest(),
                "data_b64": base64.b64encode(content[:6]).decode("ascii"),
                "op": "download_chunk",
                "request_id": "download-chunk-0",
                "sequence": 0,
                "session_id": str(file_session.id),
                "session_type": "file_browser",
                "transfer_id": str(transfer.id),
            },
            settings=settings,
        )
        outcome_final = apply_beacon_session_data(
            session,
            beacon_id=beacon.id,
            payload={
                "chunk_sha256": hashlib.sha256(content[6:]).hexdigest(),
                "data_b64": base64.b64encode(content[6:]).decode("ascii"),
                "op": "download_chunk",
                "request_id": "download-chunk-1",
                "sequence": 1,
                "session_id": str(file_session.id),
                "session_type": "file_browser",
                "transfer_id": str(transfer.id),
            },
            settings=settings,
        )
        session.commit()
        session.refresh(transfer)
        artifact = session.get(Artifact, transfer.artifact_id)
        stored_bytes = artifact_store_for_settings(settings).get(artifact.object_key)

    assert outcome_ready.operator_message["next_sequence"] == 0
    assert outcome_first.operator_message["next_sequence"] == 1
    assert outcome_final.operator_message["op"] == "download_complete"
    assert outcome_final.operator_message["artifact_id"] == str(transfer.artifact_id)
    assert transfer.status == "completed"
    assert stored_bytes == content


def test_file_transfer_upload_rejects_max_size(result_c2_client, monkeypatch):
    token = connect_c2(result_c2_client)
    registered = register_beacon(result_c2_client)
    attach_protocol_metadata(registered["beacon_id"])

    async def capture_send(_, _frame: bytes) -> bool:
        return True

    monkeypatch.setattr(result_c2_client.app.state.beacon_transport_manager, "send_to_beacon", capture_send)
    created_session = result_c2_client.post(
        "/api/v1/sessions/file-browser",
        headers={"Authorization": f"Bearer {token}"},
        json={"beacon_id": registered["beacon_id"]},
    ).json()

    rejected = result_c2_client.post(
        "/api/v1/file-transfers/uploads",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "beacon_id": registered["beacon_id"],
            "filename": "too-large.bin",
            "remote_path": "too-large.bin",
            "session_id": created_session["id"],
            "sha256": hashlib.sha256(b"too-large").hexdigest(),
            "size_bytes": 101 * 1024 * 1024,
        },
    )

    assert rejected.status_code == 400
    assert "size limit" in rejected.json()["detail"]


def test_registry_confirmation_token_is_single_use_and_bound_to_value(c2_client):
    registered = register_beacon(c2_client)

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        registry_session = InteractiveSession(
            actor_subject="operator:test",
            beacon_id=beacon.id,
            session_type="registry",
            shell_type="none",
            status="open",
        )
        session.add(registry_session)
        session.commit()

        prepare = parse_registry_request(
            json.dumps(
                {
                    "hive": "HKCU",
                    "key_path": "Software\\XeroTest",
                    "op": "reg_prepare_write_value",
                    "request_id": "reg-prepare",
                    "value": "enabled",
                    "value_name": "Mode",
                    "value_type": "REG_SZ",
                }
            )
        )
        confirm = create_registry_confirmation(
            session,
            actor_subject="operator:test",
            registry_session=registry_session,
            request=prepare,
            ttl_seconds=120,
        )
        session.commit()

        write = parse_registry_request(
            json.dumps(
                {
                    "confirm_token": confirm["confirm_token"],
                    "hive": "HKCU",
                    "key_path": "Software\\XeroTest",
                    "op": "reg_write_value",
                    "request_id": "reg-write",
                    "value": "enabled",
                    "value_name": "Mode",
                    "value_type": "REG_SZ",
                }
            )
        )
        consume_registry_confirmation(
            session,
            actor_subject="operator:test",
            registry_session=registry_session,
            request=write,
        )
        session.commit()

        stored_confirmation = session.execute(select(RegistryConfirmation)).scalar_one()
        reused = parse_registry_request(
            json.dumps(
                {
                    "confirm_token": confirm["confirm_token"],
                    "hive": "HKCU",
                    "key_path": "Software\\XeroTest",
                    "op": "reg_write_value",
                    "request_id": "reg-write-again",
                    "value": "changed",
                    "value_name": "Mode",
                    "value_type": "REG_SZ",
                }
            )
        )
        with pytest.raises(ValueError, match="invalid or expired"):
            consume_registry_confirmation(
                session,
                actor_subject="operator:test",
                registry_session=registry_session,
                request=reused,
            )
        confirmation_used_at = stored_confirmation.used_at
        confirmation_digest = stored_confirmation.value_digest
        confirmation_length = stored_confirmation.value_length

    assert confirm["op"] == "reg_confirm_token"
    assert confirmation_used_at is not None
    assert confirmation_digest
    assert confirmation_length == len("enabled")


def test_registry_session_data_records_redacted_modification_audit(c2_client):
    registered = register_beacon(c2_client)

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        registry_session = InteractiveSession(
            actor_subject="operator:test",
            beacon_id=beacon.id,
            session_type="registry",
            shell_type="none",
            status="open",
        )
        session.add(registry_session)
        session.commit()
        outcome = apply_beacon_session_data(
            session,
            beacon_id=beacon.id,
            payload={
                "beacon_id": registered["beacon_id"],
                "hive": "HKCU",
                "key_path": "Software\\XeroTest",
                "ok": True,
                "op": "reg_write_value",
                "request_id": "reg-write",
                "session_id": str(registry_session.id),
                "session_type": "registry",
                "value": "secret-value",
                "value_name": "Mode",
                "value_type": "REG_SZ",
            },
        )
        session.commit()
        event = session.execute(select(RegistryAuditEvent)).scalar_one()

    assert outcome.event_type == "session.registry.response.received"
    assert outcome.operator_message is not None
    assert outcome.operator_message["op"] == "reg_write_value"
    assert event.operation == "write_value"
    assert event.result == "succeeded"
    assert event.value_digest
    assert event.value_length == len("secret-value")
    assert "secret-value" not in repr(event.__dict__)


def test_file_browser_request_rejects_traversal_above_root():
    with pytest.raises(ValueError, match="traverse"):
        parse_file_browser_request('{"op":"list_dir","request_id":"seq-1","path":"../secret"}')


def test_shell_session_data_builds_terminal_output_message(c2_client):
    registered = register_beacon(c2_client)

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        shell_session = InteractiveSession(
            actor_subject="operator:test",
            beacon_id=beacon.id,
            session_type="shell",
            shell_type="bash",
            status="open",
        )
        session.add(shell_session)
        session.commit()
        outcome = apply_beacon_session_data(
            session,
            beacon_id=beacon.id,
            payload={
                "beacon_id": registered["beacon_id"],
                "data_b64": terminal_data_b64("hello from beacon\n"),
                "op": "stdout",
                "session_id": str(shell_session.id),
            },
        )

    assert outcome.event_type == "session.output.received"
    assert outcome.operator_message is not None
    assert outcome.operator_message["op"] == "stdout"
    assert outcome.operator_message["data"] == "hello from beacon\n"


def test_shell_session_rejects_second_operator_attach():
    class FakeSessionWebSocket:
        application_state = WebSocketState.CONNECTED

        def __init__(self) -> None:
            self.closed_code: int | None = None
            self.sent: list[dict] = []

        async def send_json(self, payload: dict) -> None:
            self.sent.append(payload)

        async def close(self, *, code: int = 1000) -> None:
            self.closed_code = code
            self.application_state = WebSocketState.DISCONNECTED

    async def scenario() -> int | None:
        manager = SessionRelayManager(queue_size=2)
        session_id = uuid.uuid4()
        first = FakeSessionWebSocket()
        second = FakeSessionWebSocket()
        await manager.register(first, session_id)  # type: ignore[arg-type]
        with pytest.raises(DuplicateSessionAttachError):
            await manager.register(second, session_id)  # type: ignore[arg-type]
        await manager.close_all()
        return second.closed_code

    assert asyncio.run(scenario()) == 4409


def test_idle_timeout_closes_shell_session(c2_client):
    registered = register_beacon(c2_client)
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        shell_session = InteractiveSession(
            actor_subject="operator:test",
            beacon_id=beacon.id,
            last_activity_at=utc_now() - timedelta(seconds=settings.session_idle_timeout_seconds + 1),
            opened_at=utc_now() - timedelta(seconds=settings.session_idle_timeout_seconds + 2),
            session_type="shell",
            shell_type="bash",
            status="open",
        )
        session.add(shell_session)
        session.commit()
        expired = expire_idle_sessions(session, settings)
        session.commit()

    assert [item.id for item in expired] == [shell_session.id]
    assert expired[0].status == "closed"
    assert expired[0].close_reason == "idle_timeout"


def test_idle_timeout_keeps_recent_shell_session_open(c2_client):
    registered = register_beacon(c2_client)
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        shell_session = InteractiveSession(
            actor_subject="operator:test",
            beacon_id=beacon.id,
            last_activity_at=utc_now() - timedelta(minutes=5),
            opened_at=utc_now() - timedelta(minutes=5),
            session_type="shell",
            shell_type="bash",
            status="open",
        )
        session.add(shell_session)
        session.commit()
        expired = expire_idle_sessions(session, settings)
        session.commit()
        session.refresh(shell_session)

    assert expired == []
    assert shell_session.status == "open"


def test_detached_shell_session_cleanup_closes_after_grace(c2_client, monkeypatch):
    registered = register_beacon(c2_client)
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        shell_session = InteractiveSession(
            actor_subject="operator:test",
            beacon_id=beacon.id,
            detached_at=utc_now(),
            session_type="shell",
            shell_type="bash",
            status="detached",
        )
        session.add(shell_session)
        session.commit()
        session_id = shell_session.id

    class FakeBeaconTransportManager:
        async def send_to_beacon(self, *_):
            return False

    class FakeRealtimeHub:
        def __init__(self) -> None:
            self.events: list[dict] = []

        async def broadcast(self, event: dict) -> None:
            self.events.append(event)

    async def immediate_sleep(_seconds: int) -> None:
        return None

    realtime_hub = FakeRealtimeHub()
    app = SimpleNamespace(
        state=SimpleNamespace(
            beacon_transport_manager=FakeBeaconTransportManager(),
            operator_realtime_hub=realtime_hub,
            redis_client=None,
        ),
    )
    monkeypatch.setattr("xero_c2.sessions.asyncio.sleep", immediate_sleep)

    asyncio.run(close_detached_after_grace(app, settings, session_id))

    with SessionFactory() as session:
        stored = session.get(InteractiveSession, session_id)

    assert stored is not None
    assert stored.status == "closed"
    assert stored.close_reason == "operator_disconnected"
    assert any(event["type"] == "session.closed" for event in realtime_hub.events)


def test_beacon_websocket_existing_beacon_authenticates_with_token(protocol_c2_client):
    registered = register_beacon(protocol_c2_client)
    frame = encode_protocol_test_frame(HEARTBEAT, {"beacon_id": registered["beacon_id"], "hostname": "ws-heartbeat"})

    with protocol_c2_client.websocket_connect(
        f"/ws/beacon?beacon_id={registered['beacon_id']}",
        subprotocols=["xero.beacon.v1", f"bearer.{registered['beacon_token']}"],
    ) as websocket:
        websocket.send_bytes(frame)
        ack = decode_protocol_response(websocket.receive_bytes())

        assert ack["acknowledged_message_type"] == "HEARTBEAT"
        assert ack["transport"] == "websocket"

        settings = get_settings()
        SessionFactory = get_session_factory(settings.database_url)
        with SessionFactory() as session:
            beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))

        assert beacon is not None
        assert beacon.hostname == "ws-heartbeat"
        assert beacon.transport_mode == "websocket"
        assert beacon.transport_connected is True


def test_beacon_websocket_rejects_text_frame(protocol_c2_client):
    with protocol_c2_client.websocket_connect("/ws/beacon", subprotocols=["xero.beacon.v1"]) as websocket:
        websocket.send_text("not-binary")
        with pytest.raises(WebSocketDisconnect) as disconnect:
            websocket.receive_bytes()

    assert disconnect.value.code == 4400

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        event = session.execute(select(ProtocolSecurityEvent)).scalar_one()

    assert event.event_type == "protocol.text_frame_rejected"


def test_beacon_websocket_duplicate_connection_closes_prior(protocol_c2_client):
    with protocol_c2_client.websocket_connect("/ws/beacon", subprotocols=["xero.beacon.v1"]) as first:
        first.send_bytes(encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])))
        ack = decode_protocol_response(first.receive_bytes())

        with protocol_c2_client.websocket_connect(
            f"/ws/beacon?beacon_id={ack['beacon_id']}",
            subprotocols=["xero.beacon.v1", f"bearer.{ack['beacon_token']}"],
        ) as second:
            second.send_bytes(encode_protocol_test_frame(TASK_POLL, {"beacon_id": ack["beacon_id"]}))
            second_ack = decode_protocol_response(second.receive_bytes())
            assert second_ack["task"] is None

            with pytest.raises(WebSocketDisconnect) as disconnect:
                first.receive_bytes()

    assert disconnect.value.code == WS_CLOSE_DUPLICATE


def test_beacon_websocket_hmac_tamper_rejected_and_logged(protocol_c2_client):
    frame = bytearray(encode_protocol_test_frame(REGISTER, register_payload(supported_versions=[1])))
    frame[-1] ^= 0x01

    with protocol_c2_client.websocket_connect("/ws/beacon", subprotocols=["xero.beacon.v1"]) as websocket:
        websocket.send_bytes(bytes(frame))
        with pytest.raises(WebSocketDisconnect) as disconnect:
            websocket.receive_bytes()

    assert disconnect.value.code == 4400

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        event = session.execute(select(ProtocolSecurityEvent)).scalar_one()

    assert event.event_type == "protocol.hmac_mismatch"
    assert event.severity == "high"


def test_beacon_websocket_replay_nonce_rejected_and_logged(protocol_c2_client):
    frame = encode_protocol_test_frame(
        REGISTER,
        register_payload(supported_versions=[1]),
        nonce=bytes.fromhex("101112131415161718191a1b"),
    )

    with protocol_c2_client.websocket_connect("/ws/beacon", subprotocols=["xero.beacon.v1"]) as websocket:
        websocket.send_bytes(frame)
        decode_protocol_response(websocket.receive_bytes())
        websocket.send_bytes(frame)
        with pytest.raises(WebSocketDisconnect) as disconnect:
            websocket.receive_bytes()

    assert disconnect.value.code == 4400

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        event = session.execute(select(ProtocolSecurityEvent)).scalar_one()

    assert event.event_type == "protocol.replay_detected"


def test_beacon_websocket_oversize_frame_is_rejected_and_logged(monkeypatch, tmp_path, make_c2_client):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'tiny-ws.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("C2_DATABASE_URL", database_url)
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "connect-me")
    monkeypatch.setenv("C2_JWT_SECRET_KEY", "test-c2-jwt-secret-with-enough-length")
    monkeypatch.setenv("C2_BEACON_WS_MAX_MESSAGE_BYTES", "256")
    get_settings.cache_clear()
    clear_database_caches()
    Base.metadata.create_all(bind=get_engine(database_url))
    client = make_c2_client(C2_DATABASE_URL=database_url, C2_BEACON_WS_MAX_MESSAGE_BYTES="256")

    with client.websocket_connect("/ws/beacon", subprotocols=["xero.beacon.v1"]) as websocket:
        websocket.send_bytes(b"x" * 257)
        with pytest.raises(WebSocketDisconnect) as disconnect:
            websocket.receive_bytes()

    assert disconnect.value.code == 1009


def test_beacon_transport_send_queue_backpressure_disconnects():
    class SlowWebSocket:
        application_state = WebSocketState.CONNECTED

        def __init__(self) -> None:
            self.closed_code: int | None = None

        async def send_bytes(self, _: bytes) -> None:
            await asyncio.sleep(60)

        async def close(self, *, code: int = 1000) -> None:
            self.closed_code = code
            self.application_state = WebSocketState.DISCONNECTED

    async def scenario() -> int | None:
        manager = BeaconTransportManager(queue_size=1)
        websocket = SlowWebSocket()
        connection = await manager.register(websocket, uuid.uuid4())
        assert await connection.enqueue(b"one")
        assert not await connection.enqueue(b"two")
        await manager.close_all()
        return websocket.closed_code

    assert asyncio.run(scenario()) == WS_CLOSE_OVERLOADED


def test_register_returns_one_time_token_and_list_is_token_free(c2_client):
    token = connect_c2(c2_client)
    registered = register_beacon(c2_client)
    listed = c2_client.get("/api/v1/beacons", headers={"Authorization": f"Bearer {token}"})

    assert registered["beacon_token"]
    assert registered["sleep"] == 5
    assert registered["jitter"] == 0.25
    assert listed.status_code == 200
    assert listed.json()["items"][0]["hostname"] == "test-host"
    assert "beacon_token" not in listed.text
    assert "beacon_token_hash" not in listed.text


def test_duplicate_fingerprint_updates_one_row_and_rotates_token(c2_client):
    fingerprint = f"stable-{uuid.uuid4()}"
    first = register_beacon(c2_client, machine_fingerprint_hash=fingerprint, hostname="first-host")
    second = register_beacon(c2_client, machine_fingerprint_hash=fingerprint, hostname="second-host")

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacons = session.execute(select(Beacon).where(Beacon.machine_fingerprint_hash == fingerprint)).scalars().all()

    assert first["beacon_id"] == second["beacon_id"]
    assert first["beacon_token"] != second["beacon_token"]
    assert len(beacons) == 1
    assert beacons[0].hostname == "second-host"


def test_invalid_beacon_ip_returns_422(c2_client):
    response = c2_client.post("/api/v1/beacons/register", json=register_payload(internal_ip="10.0.0.999"))

    assert response.status_code == 422


def test_heartbeat_updates_last_seen_and_metadata(c2_client):
    registered = register_beacon(c2_client)
    response = c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/heartbeat",
        headers={"Authorization": f"Bearer {registered['beacon_token']}"},
        json={"hostname": "renamed-host", "internal_ip": "10.20.0.9", "pid": 3333},
    )

    assert response.status_code == 200
    assert response.json()["beacon"]["hostname"] == "renamed-host"
    assert response.json()["beacon"]["internal_ip"] == "10.20.0.9"


def test_heartbeat_rejects_unknown_or_invalid_token(c2_client):
    registered = register_beacon(c2_client)

    unknown = c2_client.post(
        f"/api/v1/beacons/{uuid.uuid4()}/heartbeat",
        headers={"Authorization": f"Bearer {registered['beacon_token']}"},
        json={},
    )
    invalid = c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/heartbeat",
        headers={"Authorization": "Bearer wrong"},
        json={},
    )

    assert unknown.status_code == 404
    assert invalid.status_code == 401


def test_list_beacons_filters_by_status(c2_client):
    token = connect_c2(c2_client)
    online = register_beacon(c2_client, hostname="online-host")
    offline = register_beacon(c2_client, hostname="offline-host")

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(offline["beacon_id"]))
        assert beacon is not None
        beacon.status = BEACON_STATUS_OFFLINE
        session.add(beacon)
        session.commit()

    response = c2_client.get("/api/v1/beacons?status=online", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    hostnames = {item["hostname"] for item in response.json()["items"]}
    assert hostnames == {online["beacon"]["hostname"]}


def test_kill_beacon_removes_from_active_list_and_keeps_history(c2_client):
    token = connect_c2(c2_client)
    registered = register_beacon(c2_client, hostname="kill-target")

    response = c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/kill",
        headers={"Authorization": f"Bearer {token}"},
    )
    list_default = c2_client.get("/api/v1/beacons", headers={"Authorization": f"Bearer {token}"})
    list_history = c2_client.get("/api/v1/beacons?include_removed=true", headers={"Authorization": f"Bearer {token}"})
    get_default = c2_client.get(
        f"/api/v1/beacons/{registered['beacon_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    get_history = c2_client.get(
        f"/api/v1/beacons/{registered['beacon_id']}?include_removed=true",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "removed"
    assert payload["beacon"]["removed_at"] is not None
    assert payload["beacon"]["removed_by"] == "xero-ui-client"
    assert list_default.json()["items"] == []
    assert [item["hostname"] for item in list_history.json()["items"]] == ["kill-target"]
    assert get_default.status_code == 404
    assert get_history.status_code == 200


def test_kill_beacon_closes_sessions_cancels_tasks_and_is_idempotent(c2_client):
    token = connect_c2(c2_client)
    registered = register_beacon(c2_client)
    queued_task = create_shell_task(c2_client, token, registered["beacon_id"], command="hostname")

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        shell_session = InteractiveSession(
            actor_subject="operator:test",
            beacon_id=beacon.id,
            opened_at=utc_now(),
            session_type="shell",
            shell_type="bash",
            status="open",
        )
        session.add(shell_session)
        session.commit()
        session_id = shell_session.id

    first = c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/kill",
        headers={"Authorization": f"Bearer {token}"},
    )
    second = c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/kill",
        headers={"Authorization": f"Bearer {token}"},
    )

    with SessionFactory() as session:
        task = session.get(Task, uuid.UUID(queued_task["id"]))
        stored_session = session.get(InteractiveSession, session_id)
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))

    assert first.status_code == 200
    assert first.json()["closed_sessions"] == 1
    assert first.json()["cancelled_tasks"] == 1
    assert second.status_code == 200
    assert second.json()["status"] == "already_removed"
    assert second.json()["closed_sessions"] == 0
    assert second.json()["cancelled_tasks"] == 0
    assert task is not None
    assert task.status == "cancelled"
    assert stored_session is not None
    assert stored_session.status == "closed"
    assert stored_session.close_reason == "beacon_killed"
    assert beacon is not None
    assert beacon.status == "offline"
    assert beacon.transport_connected is False


def test_removed_beacon_rejects_heartbeat_tasks_sessions_and_profile_changes(c2_client):
    token = connect_c2(c2_client)
    registered = register_beacon(c2_client)
    kill = c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/kill",
        headers={"Authorization": f"Bearer {token}"},
    )

    heartbeat = c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/heartbeat",
        headers={"Authorization": f"Bearer {registered['beacon_token']}"},
        json={},
    )
    task = c2_client.post(
        "/api/v1/tasks",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "beacon_id": registered["beacon_id"],
            "module": "shell",
            "args": {"command": "whoami"},
            "priority": "normal",
        },
    )
    shell = c2_client.post(
        "/api/v1/sessions/shell",
        headers={"Authorization": f"Bearer {token}"},
        json={"beacon_id": registered["beacon_id"], "shell_type": "auto"},
    )
    profile = c2_client.delete(
        f"/api/v1/beacons/{registered['beacon_id']}/profile",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert kill.status_code == 200
    assert heartbeat.status_code == 410
    assert task.status_code == 410
    assert shell.status_code == 410
    assert profile.status_code == 410


def test_beacon_activity_includes_lifecycle_task_and_session_events(c2_client):
    token = connect_c2(c2_client)
    registered = register_beacon(c2_client)
    queued_task = create_shell_task(c2_client, token, registered["beacon_id"], command="id")

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        session.add(
            InteractiveSession(
                actor_subject="operator:test",
                beacon_id=beacon.id,
                opened_at=utc_now(),
                session_type="shell",
                shell_type="bash",
                status="open",
            )
        )
        session.commit()

    kill = c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/kill",
        headers={"Authorization": f"Bearer {token}"},
    )
    activity = c2_client.get(
        f"/api/v1/beacons/{registered['beacon_id']}/activity",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert kill.status_code == 200
    assert queued_task["status"] == "queued"
    assert activity.status_code == 200
    labels = [item["label"] for item in activity.json()["items"]]
    assert "Beacon removed from active inventory" in labels
    assert any(label.startswith("Task id ") for label in labels)
    assert "Shell session closed" in labels


def test_stale_detector_marks_beacons_offline_and_logs_event(c2_client):
    registered = register_beacon(c2_client)
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        beacon.last_seen = utc_now() - timedelta(seconds=60)
        session.add(beacon)
        session.commit()

    with SessionFactory() as session:
        stale = mark_stale_beacons_offline(session, settings, now=utc_now())
        session.commit()

    with SessionFactory() as session:
        event = session.execute(select(BeaconEvent)).scalar_one()
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))

    assert [item.hostname for item in stale] == ["test-host"]
    assert beacon is not None
    assert beacon.status == "offline"
    assert event.new_status == "offline"


def test_heartbeat_recovers_offline_beacon_and_logs_event(c2_client):
    registered = register_beacon(c2_client)
    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        beacon = session.get(Beacon, uuid.UUID(registered["beacon_id"]))
        assert beacon is not None
        beacon.status = "offline"
        beacon.beacon_token_hash = hash_beacon_token(registered["beacon_token"])
        session.add(beacon)
        session.commit()

    response = c2_client.post(
        f"/api/v1/beacons/{registered['beacon_id']}/heartbeat",
        headers={"Authorization": f"Bearer {registered['beacon_token']}"},
        json={},
    )

    with SessionFactory() as session:
        event = session.execute(select(BeaconEvent).where(BeaconEvent.new_status == "online")).scalar_one()

    assert response.status_code == 200
    assert response.json()["beacon"]["status"] == "online"
    assert event.old_status == "offline"
    assert event.reason == "heartbeat"


def test_infrastructure_workers_list_seeds_embedded_workers(c2_client):
    token = connect_c2(c2_client)

    response = c2_client.get("/api/v1/infrastructure/workers", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    workers = response.json()["items"]
    assert {(worker["kind"], worker["origin"]) for worker in workers} == {
        ("beacon-handler", "embedded"),
        ("scanner", "embedded"),
    }
    assert all(worker["status"] == "online" for worker in workers)
    assert "worker_token" not in response.text
    assert "worker_token_hash" not in response.text


def test_worker_pairing_registration_and_heartbeat_are_token_safe(c2_client):
    token = connect_c2(c2_client)
    pairing = c2_client.post(
        "/api/v1/infrastructure/pairing-tokens",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "scanner", "name": "external scanner one"},
    )
    assert pairing.status_code == 200
    pairing_payload = pairing.json()
    assert pairing_payload["pairing_token"]
    assert "docker compose -f docker-compose.scanner.yml" in pairing_payload["command"]

    registered = c2_client.post(
        "/api/v1/infrastructure/workers/register",
        json={
            "kind": "scanner",
            "name": "external scanner one",
            "pairing_token": pairing_payload["pairing_token"],
            "endpoint": "http://scanner.local:8000",
            "capabilities": ["tcp-connect", "service-enumeration"],
            "capacity": 10,
            "current_load": 1,
            "version": "test",
        },
    )
    assert registered.status_code == 200
    registered_payload = registered.json()
    assert registered_payload["worker_token"]
    assert registered_payload["worker"]["origin"] == "external"
    assert registered_payload["worker"]["status"] == "online"

    reused = c2_client.post(
        "/api/v1/infrastructure/workers/register",
        json={
            "kind": "scanner",
            "name": "external scanner one",
            "pairing_token": pairing_payload["pairing_token"],
        },
    )
    assert reused.status_code == 401

    heartbeat = c2_client.post(
        f"/api/v1/infrastructure/workers/{registered_payload['worker_id']}/heartbeat",
        headers={"Authorization": f"Bearer {registered_payload['worker_token']}"},
        json={
            "endpoint": "http://scanner.local:8000",
            "capabilities": ["tcp-connect"],
            "capacity": 10,
            "current_load": 2,
            "version": "test2",
        },
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["worker"]["current_load"] == 2

    listed = c2_client.get("/api/v1/infrastructure/workers", headers={"Authorization": f"Bearer {token}"})
    assert listed.status_code == 200
    assert "worker_token" not in listed.text
    assert "worker_token_hash" not in listed.text


def test_worker_stale_detector_marks_external_worker_offline(c2_client):
    token = connect_c2(c2_client)
    pairing = c2_client.post(
        "/api/v1/infrastructure/pairing-tokens",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "beacon-handler", "name": "edge handler"},
    ).json()
    registered = c2_client.post(
        "/api/v1/infrastructure/workers/register",
        json={
            "kind": "beacon-handler",
            "name": "edge handler",
            "pairing_token": pairing["pairing_token"],
            "capacity": 5,
        },
    ).json()

    settings = get_settings()
    SessionFactory = get_session_factory(settings.database_url)
    with SessionFactory() as session:
        worker = session.get(InfrastructureWorker, uuid.UUID(registered["worker_id"]))
        assert worker is not None
        worker.last_seen = utc_now() - timedelta(seconds=120)
        session.add(worker)
        session.commit()

    with SessionFactory() as session:
        stale = mark_stale_workers(session, settings, now=utc_now())
        session.commit()

    with SessionFactory() as session:
        event = session.execute(
            select(WorkerEvent).where(WorkerEvent.event_type == "worker.status.changed")
        ).scalar_one()
        worker = session.get(InfrastructureWorker, uuid.UUID(registered["worker_id"]))

    assert [item.name for item in stale] == ["edge handler"]
    assert worker is not None
    assert worker.status == "offline"
    assert event.message.endswith("to offline.")


def test_launch_worker_requires_enabled_provisioning(c2_client):
    token = connect_c2(c2_client)

    response = c2_client.post(
        "/api/v1/infrastructure/workers/launch",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "scanner", "name": "managed scanner", "host_port": 18003},
    )

    assert response.status_code == 503
    assert "disabled" in response.json()["detail"]


def test_launch_worker_records_managed_worker_when_provisioning_succeeds(monkeypatch, tmp_path, make_c2_client):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'launch.db'}"
    Base.metadata.create_all(bind=get_engine(database_url))
    client = make_c2_client(
        C2_DATABASE_URL=database_url,
        C2_CONNECT_PASSWORD="connect-me",
        C2_JWT_SECRET_KEY="test-c2-jwt-secret-with-enough-length",
        C2_LOCAL_PROVISIONING_ENABLED="true",
    )
    token = connect_c2(client)

    def fake_launch_worker(settings, *, kind, name, worker_id, pairing_token, host_port):
        assert kind == "scanner"
        assert name == "managed scanner"
        assert pairing_token
        assert host_port == 18003
        return "xero-managed-scanner-test", "http://host.docker.internal:18003"

    monkeypatch.setattr("xero_c2.main.launch_worker", fake_launch_worker)

    response = client.post(
        "/api/v1/infrastructure/workers/launch",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "scanner", "name": "managed scanner", "host_port": 18003},
    )

    assert response.status_code == 200
    worker = response.json()["worker"]
    assert worker["origin"] == "c2-managed"
    assert worker["status"] == "starting"
    assert worker["managed_project"] == "xero-managed-scanner-test"
    assert worker["endpoint"] == "http://host.docker.internal:18003"
