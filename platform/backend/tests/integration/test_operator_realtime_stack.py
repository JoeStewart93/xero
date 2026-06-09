from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest
import websockets

PLATFORM_ROOT = Path(__file__).resolve().parents[3]
C2_BACKEND_URL = os.getenv("XERO_C2_BACKEND_URL", "http://localhost:8001")
C2_CONNECT_PASSWORD = os.getenv("C2_CONNECT_PASSWORD", "c2_password")
C2_POSTGRES_DB = os.getenv("C2_POSTGRES_DB", "xero_c2")
C2_POSTGRES_USER = os.getenv("C2_POSTGRES_USER", "xero_c2")


def run_c2_compose(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "-f", "docker-compose.c2.yml", *args],
        cwd=PLATFORM_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def c2_compose_ps() -> list[dict]:
    output = run_c2_compose("ps", "--format", "json").stdout.strip()
    if not output:
        return []
    try:
        parsed = json.loads(output)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        return [json.loads(line) for line in output.splitlines()]


def wait_for_c2_service_health(service: str, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matching = [item for item in c2_compose_ps() if item.get("Service") == service]
        if matching and matching[0].get("Health") == "healthy":
            return
        time.sleep(2)
    raise AssertionError(f"{service} did not become healthy within {timeout}s")


def require_c2_stack() -> None:
    try:
        response = httpx.get(f"{C2_BACKEND_URL}/health", timeout=2)
    except httpx.HTTPError as exc:
        pytest.skip(f"C2 backend stack is not available: {exc}")
    if response.status_code != 200:
        pytest.skip(f"C2 backend stack is not healthy: HTTP {response.status_code}")


def c2_token() -> str:
    response = httpx.post(
        f"{C2_BACKEND_URL}/api/v1/c2/connect",
        json={"password": C2_CONNECT_PASSWORD},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def register_beacon(fingerprint: str, hostname: str) -> str:
    return register_beacon_payload(fingerprint, hostname)["beacon_id"]


def register_beacon_payload(fingerprint: str, hostname: str, *, internal_ip: str = "10.10.0.12") -> dict:
    response = httpx.post(
        f"{C2_BACKEND_URL}/api/v1/beacons/register",
        json={
            "machine_fingerprint_hash": fingerprint,
            "hostname": hostname,
            "os": "Windows 11",
            "architecture": "x64",
            "internal_ip": internal_ip,
            "external_ip": "198.51.100.12",
            "pid": 4321,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def list_beacons(token: str) -> list[dict]:
    response = httpx.get(
        f"{C2_BACKEND_URL}/api/v1/beacons",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["items"]


def heartbeat_beacon(beacon_id: str, beacon_token: str, *, hostname: str | None = None) -> dict:
    payload = {} if hostname is None else {"hostname": hostname}
    response = httpx.post(
        f"{C2_BACKEND_URL}/api/v1/beacons/{beacon_id}/heartbeat",
        headers={"Authorization": f"Bearer {beacon_token}"},
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def run_c2_postgres_sql(sql: str) -> None:
    run_c2_compose(
        "exec",
        "-T",
        "c2-postgres",
        "psql",
        "-U",
        C2_POSTGRES_USER,
        "-d",
        C2_POSTGRES_DB,
        "-c",
        sql,
    )


async def receive_event(websocket, event_type: str, timeout: float = 2) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        remaining = max(0.01, deadline - asyncio.get_running_loop().time())
        message = await asyncio.wait_for(websocket.recv(), timeout=remaining)
        payload = json.loads(message)
        if payload.get("type") == event_type:
            return payload
    raise AssertionError(f"Did not receive {event_type!r} within {timeout}s")


async def receive_beacon_event(websocket, event_type: str, beacon_id: str, timeout: float = 2) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        remaining = max(0.01, deadline - asyncio.get_running_loop().time())
        message = await asyncio.wait_for(websocket.recv(), timeout=remaining)
        payload = json.loads(message)
        if payload.get("type") == event_type and payload.get("scope", {}).get("beacon_id") == beacon_id:
            return payload
    raise AssertionError(f"Did not receive {event_type!r} for beacon {beacon_id} within {timeout}s")


def operator_socket(token: str):
    websocket_url = C2_BACKEND_URL.replace("https://", "wss://").replace("http://", "ws://") + "/ws/operator"
    return websockets.connect(websocket_url, subprotocols=["xero.operator.v1", f"bearer.{token}"])


def test_c2_operator_websocket_receives_beacon_registration_event():
    require_c2_stack()
    token = c2_token()

    async def scenario() -> None:
        async with operator_socket(token) as websocket:
            assert (await receive_event(websocket, "realtime.connected"))["source"]["role"] == "c2"
            beacon_id = await asyncio.to_thread(
                register_beacon,
                f"integration-fingerprint-{time.time_ns()}",
                "integration-host",
            )
            event = await receive_event(websocket, "beacon.registered")
            assert event["scope"]["beacon_id"] == beacon_id
            assert event["data"]["beacon"]["hostname"] == "integration-host"

    asyncio.run(scenario())


def test_two_operator_websockets_receive_same_task_event():
    require_c2_stack()
    token = c2_token()

    async def scenario() -> None:
        async with operator_socket(token) as first, operator_socket(token) as second:
            await receive_event(first, "realtime.connected")
            await receive_event(second, "realtime.connected")
            beacon_id = await asyncio.to_thread(
                register_beacon,
                f"integration-fingerprint-{time.time_ns()}",
                "integration-multi-tab",
            )
            first_event, second_event = await asyncio.gather(
                receive_event(first, "beacon.registered"),
                receive_event(second, "beacon.registered"),
            )
            assert first_event["id"] == second_event["id"]
            assert first_event["scope"]["beacon_id"] == beacon_id

    asyncio.run(scenario())


def test_operator_websocket_reports_redis_degraded_and_recovers():
    require_c2_stack()
    token = c2_token()

    async def scenario() -> None:
        async with operator_socket(token) as websocket:
            await receive_event(websocket, "realtime.connected")
            try:
                await asyncio.to_thread(run_c2_compose, "stop", "c2-redis")
                degraded = await receive_event(websocket, "system.realtime.degraded", timeout=10)
                assert degraded["source"]["role"] == "c2"
            finally:
                await asyncio.to_thread(run_c2_compose, "start", "c2-redis")
                await asyncio.to_thread(wait_for_c2_service_health, "c2-redis")
            recovered = await receive_event(websocket, "system.realtime.recovered", timeout=20)
            assert recovered["source"]["role"] == "c2"

    asyncio.run(scenario())


def test_c2_beacon_registration_persists_across_backend_restart():
    require_c2_stack()
    fingerprint = f"integration-persist-{time.time_ns()}"
    registered = register_beacon_payload(fingerprint, "integration-persistent")
    assert registered["beacon_token"]

    run_c2_compose("restart", "c2-backend")
    wait_for_c2_service_health("c2-backend")

    token = c2_token()
    matching = [item for item in list_beacons(token) if item["id"] == registered["beacon_id"]]

    assert len(matching) == 1
    assert matching[0]["hostname"] == "integration-persistent"
    assert "beacon_token" not in matching[0]
    assert "beacon_token_hash" not in matching[0]


def test_c2_duplicate_fingerprint_updates_one_row_and_emits_status_event():
    require_c2_stack()
    token = c2_token()
    fingerprint = f"integration-duplicate-{time.time_ns()}"

    async def scenario() -> None:
        async with operator_socket(token) as websocket:
            await receive_event(websocket, "realtime.connected")
            first = await asyncio.to_thread(register_beacon_payload, fingerprint, "integration-original")
            registered_event = await receive_event(websocket, "beacon.registered")
            second = await asyncio.to_thread(
                register_beacon_payload,
                fingerprint,
                "integration-updated",
                internal_ip="10.10.0.13",
            )
            updated_event = await receive_event(websocket, "beacon.status.changed")
            beacons = await asyncio.to_thread(list_beacons, token)

            matching = [item for item in beacons if item["machine_fingerprint_hash"] == fingerprint]
            assert len(matching) == 1
            assert first["beacon_id"] == second["beacon_id"]
            assert first["beacon_token"] != second["beacon_token"]
            assert matching[0]["hostname"] == "integration-updated"
            assert matching[0]["internal_ip"] == "10.10.0.13"
            assert registered_event["scope"]["beacon_id"] == first["beacon_id"]
            assert updated_event["scope"]["beacon_id"] == first["beacon_id"]

    asyncio.run(scenario())


def test_c2_beacon_heartbeat_and_stale_recovery_flow():
    require_c2_stack()
    token = c2_token()
    fingerprint = f"integration-heartbeat-{time.time_ns()}"
    registered = register_beacon_payload(fingerprint, "integration-heartbeat")
    beacon_id = registered["beacon_id"]
    beacon_token = registered["beacon_token"]

    heartbeat = heartbeat_beacon(beacon_id, beacon_token, hostname="integration-heartbeat-renamed")
    assert heartbeat["beacon"]["status"] == "online"
    assert heartbeat["beacon"]["hostname"] == "integration-heartbeat-renamed"

    async def scenario() -> None:
        async with operator_socket(token) as websocket:
            await receive_event(websocket, "realtime.connected")
            await asyncio.to_thread(
                run_c2_postgres_sql,
                "UPDATE beacons "
                "SET status = 'online', last_seen = NOW() - INTERVAL '5 minutes' "
                f"WHERE id = '{beacon_id}'",
            )
            offline_event = await receive_beacon_event(websocket, "beacon.status.changed", beacon_id, timeout=45)
            assert offline_event["scope"]["beacon_id"] == beacon_id
            assert offline_event["data"]["beacon"]["status"] == "offline"

            recovered = await asyncio.to_thread(heartbeat_beacon, beacon_id, beacon_token)
            assert recovered["beacon"]["status"] == "online"
            online_event = await receive_beacon_event(websocket, "beacon.status.changed", beacon_id, timeout=5)
            heartbeat_event = await receive_beacon_event(websocket, "beacon.heartbeat", beacon_id, timeout=5)
            assert online_event["scope"]["beacon_id"] == beacon_id
            assert online_event["data"]["beacon"]["status"] == "online"
            assert heartbeat_event["scope"]["beacon_id"] == beacon_id

    asyncio.run(scenario())

    matching = [item for item in list_beacons(token) if item["id"] == beacon_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "online"
