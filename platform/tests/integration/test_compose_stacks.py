from __future__ import annotations

import json
import os
import subprocess
import time
from base64 import b64decode
from pathlib import Path

import httpx
import pytest
from websockets.sync.client import connect as ws_connect
from xero_c2.protocol import HEARTBEAT, REGISTER, TASK_POLL, TASK_RESULT

from tests.helpers.protocol_frames import decode_protocol_ack, encode_protocol_test_frame

PLATFORM_ROOT = Path(__file__).resolve().parents[2]
BFF_URL = os.getenv("XERO_BACKEND_URL", "http://localhost:8000")
C2_URL = os.getenv("XERO_C2_BACKEND_URL", "http://localhost:8001")
C2_CONNECT_PASSWORD = os.getenv("C2_CONNECT_PASSWORD", "c2_password")
C2_POSTGRES_DB = os.getenv("C2_POSTGRES_DB", "xero_c2")
C2_POSTGRES_USER = os.getenv("C2_POSTGRES_USER", "xero_c2")


def run_compose(compose_file: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "-f", compose_file, *args],
        cwd=PLATFORM_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def compose_ps(compose_file: str) -> list[dict]:
    output = run_compose(compose_file, "ps", "--format", "json").stdout.strip()
    if not output:
        return []
    try:
        parsed = json.loads(output)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        return [json.loads(line) for line in output.splitlines()]


def wait_for_service_health(compose_file: str, service: str, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matching = [item for item in compose_ps(compose_file) if item.get("Service") == service]
        if matching and matching[0].get("Health") == "healthy":
            return
        time.sleep(2)
    raise AssertionError(f"{service} did not become healthy within {timeout}s")


def require_url(url: str, label: str) -> None:
    try:
        response = httpx.get(f"{url}/health", timeout=2)
    except httpx.HTTPError as exc:
        pytest.skip(f"{label} stack is not available: {exc}")
    if response.status_code != 200:
        pytest.skip(f"{label} stack is not healthy: HTTP {response.status_code}")


def c2_access_token() -> str:
    connect = httpx.post(f"{C2_URL}/api/v1/c2/connect", json={"password": C2_CONNECT_PASSWORD}, timeout=10)
    connect.raise_for_status()
    return str(connect.json()["access_token"])


def c2_auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def websocket_url(path: str) -> str:
    if C2_URL.startswith("https://"):
        return f"wss://{C2_URL.removeprefix('https://').rstrip('/')}{path}"
    return f"ws://{C2_URL.removeprefix('http://').rstrip('/')}{path}"


def protocol_metadata(token: str) -> dict:
    response = httpx.get(f"{C2_URL}/api/v1/protocol", headers=c2_auth_headers(token), timeout=10)
    response.raise_for_status()
    return response.json()


def transport_status(token: str) -> dict:
    response = httpx.get(f"{C2_URL}/api/v1/transport", headers=c2_auth_headers(token), timeout=10)
    response.raise_for_status()
    return response.json()


def create_c2_task(token: str, beacon_id: str, *, command: str, priority: str = "normal") -> dict:
    response = httpx.post(
        f"{C2_URL}/api/v1/tasks",
        headers=c2_auth_headers(token),
        json={
            "beacon_id": beacon_id,
            "module": "shell",
            "args": {"command": command},
            "priority": priority,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def list_c2_tasks(token: str, beacon_id: str) -> list[dict]:
    response = httpx.get(
        f"{C2_URL}/api/v1/tasks?beacon_id={beacon_id}",
        headers=c2_auth_headers(token),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["items"]


def c2_url_for_docker() -> str:
    parsed = C2_URL.rstrip("/")
    for host in ("localhost", "127.0.0.1"):
        parsed = parsed.replace(f"://{host}:", "://host.docker.internal:")
    return parsed


def run_go_beacon_once(tmp_path: Path, *, protocol: dict, fingerprint: str) -> subprocess.CompletedProcess[str]:
    state_dir = tmp_path / "go-beacon-state"
    state_dir.mkdir(exist_ok=True)
    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--add-host=host.docker.internal:host-gateway",
            "-v",
            f"{PLATFORM_ROOT}:/workspace/platform",
            "-v",
            f"{state_dir}:/state",
            "-w",
            "/workspace/platform/beacons/go",
            "-e",
            f"XERO_BEACON_C2_URL={c2_url_for_docker()}",
            "-e",
            f"XERO_BEACON_C2_PUBLIC_KEY_B64={protocol['c2_public_key_b64']}",
            "-e",
            "XERO_BEACON_STATE_PATH=/state/beacon-state.json",
            "-e",
            f"XERO_BEACON_MACHINE_FINGERPRINT_HASH={fingerprint}",
            "-e",
            "XERO_BEACON_SLEEP_SECONDS=1",
            "golang:1.26",
            "go",
            "run",
            ".",
            "-once",
        ],
        cwd=PLATFORM_ROOT,
        check=True,
        text=True,
        capture_output=True,
        timeout=180,
    )


def register_c2_beacon(hostname: str) -> dict:
    response = httpx.post(
        f"{C2_URL}/api/v1/beacons/register",
        json={
            "machine_fingerprint_hash": f"integration-{hostname}-{time.time_ns()}",
            "hostname": hostname,
            "os": "Windows 11",
            "architecture": "x64",
            "internal_ip": "10.54.0.10",
            "external_ip": "198.51.100.54",
            "pid": 5454,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def encode_protocol_frame(
    metadata: dict,
    message_type: str,
    payload: dict,
    *,
    max_frame_bytes: int | None = None,
) -> bytes:
    return encode_protocol_test_frame(
        message_type,
        payload,
        peer_public_key=b64decode(metadata["c2_public_key_b64"]),
        max_frame_bytes=max_frame_bytes or int(metadata["max_frame_bytes"]),
    )


def protocol_receipt_count(beacon_id: str, message_types: tuple[str, ...]) -> int:
    quoted_types = ", ".join(f"'{message_type}'" for message_type in message_types)
    sql = (
        "SELECT COUNT(*) FROM protocol_frame_receipts "
        f"WHERE beacon_id = '{beacon_id}' AND message_type IN ({quoted_types})"
    )
    output = run_compose(
        "docker-compose.c2.yml",
        "exec",
        "-T",
        "c2-postgres",
        "psql",
        "-U",
        C2_POSTGRES_USER,
        "-d",
        C2_POSTGRES_DB,
        "-At",
        "-c",
        sql,
    ).stdout.strip()
    return int(output)


def test_split_compose_configs_are_valid():
    for compose_file in (
        "docker-compose.bff.yml",
        "docker-compose.c2.yml",
        "docker-compose.handler.yml",
        "docker-compose.scanner.yml",
    ):
        output = run_compose(compose_file, "config").stdout
        assert "services:" in output


def test_bff_stack_is_healthy_and_login_works():
    require_url(BFF_URL, "BFF")
    wait_for_service_health("docker-compose.bff.yml", "bff-api")

    docs = httpx.get(f"{BFF_URL}/docs", timeout=10)
    login = httpx.post(f"{BFF_URL}/auth/login", json={"username": "admin", "password": "admin"}, timeout=10)

    assert docs.status_code == 200
    assert "swagger-ui" in docs.text.lower()
    assert login.status_code == 200
    assert login.json()["operator"]["role"] == "admin"


def test_c2_stack_registers_and_heartbeats_beacon():
    require_url(C2_URL, "C2")
    wait_for_service_health("docker-compose.c2.yml", "c2-api")

    c2_token = c2_access_token()

    register = httpx.post(
        f"{C2_URL}/api/v1/beacons/register",
        json={
            "machine_fingerprint_hash": f"integration-{time.time_ns()}",
            "hostname": "integration-split-host",
            "os": "Windows 11",
            "architecture": "x64",
            "internal_ip": "10.50.0.10",
            "external_ip": "198.51.100.50",
            "pid": 5050,
        },
        timeout=10,
    )
    register.raise_for_status()
    payload = register.json()

    heartbeat = httpx.post(
        f"{C2_URL}/api/v1/beacons/{payload['beacon_id']}/heartbeat",
        headers={"Authorization": f"Bearer {payload['beacon_token']}"},
        json={},
        timeout=10,
    )
    heartbeat.raise_for_status()

    listed = httpx.get(f"{C2_URL}/api/v1/beacons", headers={"Authorization": f"Bearer {c2_token}"}, timeout=10)
    listed.raise_for_status()
    hostnames = {item["hostname"] for item in listed.json()["items"]}

    assert "integration-split-host" in hostnames


def test_c2_stack_pairs_and_heartbeats_scanner_worker():
    require_url(C2_URL, "C2")
    wait_for_service_health("docker-compose.c2.yml", "c2-api")

    c2_token = c2_access_token()
    auth_headers = c2_auth_headers(c2_token)

    workers = httpx.get(f"{C2_URL}/api/v1/infrastructure/workers", headers=auth_headers, timeout=10)
    workers.raise_for_status()
    embedded = {(item["kind"], item["origin"]) for item in workers.json()["items"]}
    assert ("beacon-handler", "embedded") in embedded
    assert ("scanner", "embedded") in embedded

    worker_name = f"integration-scanner-{time.time_ns()}"
    pairing = httpx.post(
        f"{C2_URL}/api/v1/infrastructure/pairing-tokens",
        headers=auth_headers,
        json={"kind": "scanner", "name": worker_name},
        timeout=10,
    )
    pairing.raise_for_status()
    pairing_payload = pairing.json()

    registered = httpx.post(
        f"{C2_URL}/api/v1/infrastructure/workers/register",
        json={
            "kind": "scanner",
            "name": worker_name,
            "pairing_token": pairing_payload["pairing_token"],
            "endpoint": "http://scanner.integration:8000",
            "capabilities": ["tcp-connect", "service-enumeration"],
            "capacity": 4,
            "current_load": 1,
            "version": "integration",
        },
        timeout=10,
    )
    registered.raise_for_status()
    worker_payload = registered.json()

    heartbeat = httpx.post(
        f"{C2_URL}/api/v1/infrastructure/workers/{worker_payload['worker_id']}/heartbeat",
        headers={"Authorization": f"Bearer {worker_payload['worker_token']}"},
        json={
            "endpoint": "http://scanner.integration:8000",
            "capabilities": ["tcp-connect"],
            "capacity": 4,
            "current_load": 2,
            "version": "integration-2",
        },
        timeout=10,
    )
    heartbeat.raise_for_status()

    listed = httpx.get(f"{C2_URL}/api/v1/infrastructure/workers", headers=auth_headers, timeout=10)
    listed.raise_for_status()
    listed_text = listed.text
    registered_workers = {item["name"]: item for item in listed.json()["items"]}

    assert registered_workers[worker_name]["status"] == "online"
    assert registered_workers[worker_name]["current_load"] == 2
    assert "worker_token" not in listed_text
    assert "worker_token_hash" not in listed_text


def test_c2_stack_accepts_beacon_websocket_register_and_lists_transport():
    require_url(C2_URL, "C2")
    wait_for_service_health("docker-compose.c2.yml", "c2-api")

    c2_token = c2_access_token()
    protocol = protocol_metadata(c2_token)
    event_id = time.time_ns()
    hostname = f"integration-ws-register-{event_id}"

    with ws_connect(
        websocket_url("/ws/beacon"),
        subprotocols=["xero.beacon.v1"],
        open_timeout=10,
        proxy=None,
    ) as websocket:
        websocket.send(
            encode_protocol_frame(
                protocol,
                REGISTER,
                {
                    "machine_fingerprint_hash": f"integration-ws-{event_id}",
                    "hostname": hostname,
                    "os": "Windows 11",
                    "architecture": "x64",
                    "internal_ip": "10.52.0.10",
                    "external_ip": "198.51.100.52",
                    "pid": 5252,
                    "supported_versions": [1],
                },
            )
        )
        ack_frame = websocket.recv(timeout=10)
        assert isinstance(ack_frame, bytes)
        ack = decode_protocol_ack(ack_frame)
        assert ack["transport"] == "websocket"
        assert ack["selected_protocol_version"] == 1
        assert ack["beacon_token"]

        active = transport_status(c2_token)
        assert active["active_websocket_connections"] >= 1

        listed = httpx.get(f"{C2_URL}/api/v1/beacons", headers=c2_auth_headers(c2_token), timeout=10)
        listed.raise_for_status()
        beacon = next(item for item in listed.json()["items"] if item["hostname"] == hostname)
        assert beacon["protocol_version"] == 1
        assert beacon["transport_mode"] == "websocket"
        assert beacon["transport_connected"] is True

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if transport_status(c2_token)["active_websocket_connections"] == 0:
            break
        time.sleep(0.2)
    assert transport_status(c2_token)["active_websocket_connections"] == 0


def test_c2_stack_websocket_large_frame_and_sequential_receipts():
    require_url(C2_URL, "C2")
    wait_for_service_health("docker-compose.c2.yml", "c2-api")

    c2_token = c2_access_token()
    protocol = protocol_metadata(c2_token)
    transport = transport_status(c2_token)
    event_id = time.time_ns()

    with ws_connect(
        websocket_url("/ws/beacon"),
        subprotocols=["xero.beacon.v1"],
        open_timeout=10,
        proxy=None,
    ) as websocket:
        websocket.send(
            encode_protocol_frame(
                protocol,
                REGISTER,
                {
                    "machine_fingerprint_hash": f"integration-ws-seq-{event_id}",
                    "hostname": f"integration-ws-seq-{event_id}",
                    "os": "Ubuntu 24.04",
                    "architecture": "x64",
                    "internal_ip": "10.53.0.10",
                    "external_ip": "198.51.100.53",
                    "pid": 5353,
                    "supported_versions": [1],
                },
            )
        )
        register_ack_frame = websocket.recv(timeout=10)
        assert isinstance(register_ack_frame, bytes)
        register_ack = decode_protocol_ack(register_ack_frame)
        beacon_id = register_ack["beacon_id"]

        large_frame = encode_protocol_frame(
            protocol,
            TASK_RESULT,
            {
                "beacon_id": beacon_id,
                "result_id": f"large-{event_id}",
                "status": "ok",
                "stdout": "x" * 1_040_000,
            },
            max_frame_bytes=transport["websocket_max_message_bytes"],
        )
        assert len(large_frame) > 1_000_000
        websocket.send(large_frame)
        large_ack_frame = websocket.recv(timeout=10)
        assert isinstance(large_ack_frame, bytes)
        assert decode_protocol_ack(large_ack_frame)["receipt"] == "stored"

        for sequence in range(100):
            websocket.send(encode_protocol_frame(protocol, TASK_POLL, {"beacon_id": beacon_id, "sequence": sequence}))
            ack_frame = websocket.recv(timeout=10)
            assert isinstance(ack_frame, bytes)
            ack = decode_protocol_ack(ack_frame)
            assert ack["acknowledged_message_type"] == TASK_POLL
            assert ack["task"] is None

    assert protocol_receipt_count(beacon_id, (TASK_POLL, TASK_RESULT)) == 101


def test_c2_stack_websocket_task_queue_priority_and_history():
    require_url(C2_URL, "C2")
    wait_for_service_health("docker-compose.c2.yml", "c2-api")

    c2_token = c2_access_token()
    protocol = protocol_metadata(c2_token)
    event_id = time.time_ns()

    with ws_connect(
        websocket_url("/ws/beacon"),
        subprotocols=["xero.beacon.v1"],
        open_timeout=10,
        proxy=None,
    ) as websocket:
        websocket.send(
            encode_protocol_frame(
                protocol,
                REGISTER,
                {
                    "machine_fingerprint_hash": f"integration-ws-task-{event_id}",
                    "hostname": f"integration-ws-task-{event_id}",
                    "os": "Windows 11",
                    "architecture": "x64",
                    "internal_ip": "10.55.0.10",
                    "external_ip": "198.51.100.55",
                    "pid": 5555,
                    "supported_versions": [1],
                },
            )
        )
        register_ack_frame = websocket.recv(timeout=10)
        assert isinstance(register_ack_frame, bytes)
        beacon_id = decode_protocol_ack(register_ack_frame)["beacon_id"]

        normal = create_c2_task(c2_token, beacon_id, command="normal", priority="normal")
        urgent = create_c2_task(c2_token, beacon_id, command="urgent", priority="urgent")
        create_c2_task(c2_token, beacon_id, command="low", priority="low")

        websocket.send(encode_protocol_frame(protocol, TASK_POLL, {"beacon_id": beacon_id}))
        task_ack_frame = websocket.recv(timeout=10)
        assert isinstance(task_ack_frame, bytes)
        task_ack = decode_protocol_ack(task_ack_frame)
        assert task_ack["task"]["id"] == urgent["id"]
        assert task_ack["task"]["args"]["command"] == "urgent"

        websocket.send(
            encode_protocol_frame(
                protocol,
                TASK_RESULT,
                {"beacon_id": beacon_id, "task_id": urgent["id"], "status": "completed"},
            )
        )
        result_ack_frame = websocket.recv(timeout=10)
        assert isinstance(result_ack_frame, bytes)
        assert decode_protocol_ack(result_ack_frame)["task"]["status"] == "completed"

    tasks = {task["id"]: task for task in list_c2_tasks(c2_token, beacon_id)}
    assert tasks[urgent["id"]]["status"] == "completed"
    assert tasks[normal["id"]]["status"] == "queued"


def test_c2_stack_go_beacon_registers_and_completes_shell_task(tmp_path):
    require_url(C2_URL, "C2")
    wait_for_service_health("docker-compose.c2.yml", "c2-api")

    c2_token = c2_access_token()
    protocol = protocol_metadata(c2_token)
    fingerprint = f"integration-go-beacon-{time.time_ns()}"

    first = run_go_beacon_once(tmp_path, protocol=protocol, fingerprint=fingerprint)
    assert first.returncode == 0
    state_file = tmp_path / "go-beacon-state" / "beacon-state.json"
    runtime_state = json.loads(state_file.read_text(encoding="utf-8"))
    beacon_id = runtime_state["beacon_id"]

    task = create_c2_task(c2_token, beacon_id, command="printf f0015-go-beacon", priority="urgent")
    second = run_go_beacon_once(tmp_path, protocol=protocol, fingerprint=fingerprint)
    assert second.returncode == 0

    tasks = {item["id"]: item for item in list_c2_tasks(c2_token, beacon_id)}
    assert tasks[task["id"]]["status"] == "completed"

    listed = httpx.get(f"{C2_URL}/api/v1/beacons/{beacon_id}", headers=c2_auth_headers(c2_token), timeout=10)
    listed.raise_for_status()
    beacon = listed.json()
    assert beacon["transport_mode"] == "websocket"
    assert beacon["protocol_version"] == 1


def test_c2_stack_cancelled_task_is_skipped_by_beacon_poll():
    require_url(C2_URL, "C2")
    wait_for_service_health("docker-compose.c2.yml", "c2-api")

    c2_token = c2_access_token()
    protocol = protocol_metadata(c2_token)
    event_id = time.time_ns()

    with ws_connect(
        websocket_url("/ws/beacon"),
        subprotocols=["xero.beacon.v1"],
        open_timeout=10,
        proxy=None,
    ) as websocket:
        websocket.send(
            encode_protocol_frame(
                protocol,
                REGISTER,
                {
                    "machine_fingerprint_hash": f"integration-ws-cancel-{event_id}",
                    "hostname": f"integration-ws-cancel-{event_id}",
                    "os": "Ubuntu 24.04",
                    "architecture": "x64",
                    "internal_ip": "10.56.0.10",
                    "external_ip": "198.51.100.56",
                    "pid": 5656,
                    "supported_versions": [1],
                },
            )
        )
        register_ack_frame = websocket.recv(timeout=10)
        assert isinstance(register_ack_frame, bytes)
        beacon_id = decode_protocol_ack(register_ack_frame)["beacon_id"]
        task = create_c2_task(c2_token, beacon_id, command="cancel-me", priority="urgent")
        cancelled = httpx.delete(f"{C2_URL}/api/v1/tasks/{task['id']}", headers=c2_auth_headers(c2_token), timeout=10)
        cancelled.raise_for_status()

        websocket.send(encode_protocol_frame(protocol, TASK_POLL, {"beacon_id": beacon_id}))
        ack_frame = websocket.recv(timeout=10)
        assert isinstance(ack_frame, bytes)
        assert decode_protocol_ack(ack_frame)["task"] is None


def test_c2_stack_accepts_longpoll_frame_post_and_lists_transport():
    require_url(C2_URL, "C2")
    wait_for_service_health("docker-compose.c2.yml", "c2-api")

    c2_token = c2_access_token()
    protocol = protocol_metadata(c2_token)
    event_id = time.time_ns()
    hostname = f"integration-longpoll-{event_id}"
    registered = register_c2_beacon(hostname)
    beacon_id = registered["beacon_id"]

    frame = encode_protocol_frame(
        protocol,
        HEARTBEAT,
        {
            "beacon_id": beacon_id,
            "hostname": f"{hostname}-heartbeat",
        },
    )
    response = httpx.post(
        f"{C2_URL}/api/v1/beacons/{beacon_id}/frame",
        content=frame,
        headers={"Authorization": f"Bearer {registered['beacon_token']}", "Content-Type": "application/octet-stream"},
        timeout=10,
    )
    response.raise_for_status()
    assert decode_protocol_ack(response.content)["transport"] == "long-poll"

    listed = httpx.get(f"{C2_URL}/api/v1/beacons", headers=c2_auth_headers(c2_token), timeout=10)
    listed.raise_for_status()
    beacon = next(item for item in listed.json()["items"] if item["id"] == beacon_id)
    assert beacon["hostname"] == f"{hostname}-heartbeat"
    assert beacon["transport_mode"] == "long-poll"
    assert beacon["transport_connected"] is False
    assert transport_status(c2_token)["transport_mode_counts"]["long-poll"] >= 1


def test_c2_stack_longpoll_returns_queued_task_frame():
    require_url(C2_URL, "C2")
    wait_for_service_health("docker-compose.c2.yml", "c2-api")

    c2_token = c2_access_token()
    protocol = protocol_metadata(c2_token)
    event_id = time.time_ns()
    registered = register_c2_beacon(f"integration-longpoll-task-{event_id}")
    beacon_id = registered["beacon_id"]
    heartbeat = httpx.post(
        f"{C2_URL}/api/v1/beacons/{beacon_id}/frame",
        content=encode_protocol_frame(protocol, HEARTBEAT, {"beacon_id": beacon_id}),
        headers={"Authorization": f"Bearer {registered['beacon_token']}", "Content-Type": "application/octet-stream"},
        timeout=10,
    )
    heartbeat.raise_for_status()
    task = create_c2_task(c2_token, beacon_id, command="longpoll-task", priority="urgent")

    poll = httpx.get(
        f"{C2_URL}/api/v1/beacons/{beacon_id}/poll?timeout_seconds=2",
        headers={"Authorization": f"Bearer {registered['beacon_token']}"},
        timeout=10,
    )
    poll.raise_for_status()
    ack = decode_protocol_ack(poll.content)

    assert ack["acknowledged_message_type"] == TASK_POLL
    assert ack["task"]["id"] == task["id"]
    assert list_c2_tasks(c2_token, beacon_id)[0]["status"] == "dispatched"


def test_c2_stack_longpoll_timeout_returns_204():
    require_url(C2_URL, "C2")
    wait_for_service_health("docker-compose.c2.yml", "c2-api")

    registered = register_c2_beacon(f"integration-longpoll-timeout-{time.time_ns()}")
    started = time.monotonic()
    response = httpx.get(
        f"{C2_URL}/api/v1/beacons/{registered['beacon_id']}/poll?timeout_seconds=1",
        headers={"Authorization": f"Bearer {registered['beacon_token']}"},
        timeout=10,
    )
    elapsed = time.monotonic() - started

    assert response.status_code == 204
    assert elapsed < 5


def test_c2_stack_longpoll_large_frame_roundtrips_without_corruption():
    require_url(C2_URL, "C2")
    wait_for_service_health("docker-compose.c2.yml", "c2-api")

    c2_token = c2_access_token()
    protocol = protocol_metadata(c2_token)
    transport = transport_status(c2_token)
    registered = register_c2_beacon(f"integration-longpoll-large-{time.time_ns()}")
    beacon_id = registered["beacon_id"]

    frame = encode_protocol_frame(
        protocol,
        TASK_RESULT,
        {
            "beacon_id": beacon_id,
            "result_id": f"longpoll-large-{time.time_ns()}",
            "status": "ok",
            "stdout": "x" * 1_040_000,
        },
        max_frame_bytes=transport["longpoll_max_frame_bytes"],
    )
    assert len(frame) > 1_000_000
    response = httpx.post(
        f"{C2_URL}/api/v1/beacons/{beacon_id}/frame",
        content=frame,
        headers={"Authorization": f"Bearer {registered['beacon_token']}", "Content-Type": "application/octet-stream"},
        timeout=20,
    )
    response.raise_for_status()

    assert decode_protocol_ack(response.content)["receipt"] == "stored"
    assert protocol_receipt_count(beacon_id, (TASK_RESULT,)) == 1
