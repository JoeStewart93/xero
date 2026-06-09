import json
import os
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from textwrap import dedent

import httpx
import jwt

PLATFORM_ROOT = Path(__file__).resolve().parents[3]
EXPECTED_SERVICES = {"postgres", "redis", "backend", "frontend"}
BACKEND_URL = os.getenv("XERO_BACKEND_URL", "http://localhost:8000")
DEV_JWT_SECRET = "dev-only-xero-jwt-secret-change-me"


def run_compose(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=PLATFORM_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def run_backend_python(code: str) -> str:
    result = run_compose("exec", "-T", "backend", "python", "-c", code)
    return result.stdout.strip()


def run_redis_cli(*args: str) -> str:
    result = run_compose("exec", "-T", "redis", "redis-cli", *args)
    return result.stdout.strip()


def last_output_line(output: str) -> str:
    return output.splitlines()[-1] if output else ""


def wait_for_redis_value(key: str, expected: str, timeout: int = 5) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if run_redis_cli("GET", key) == expected:
            return
        time.sleep(0.1)
    raise AssertionError(f"Redis key {key} did not become {expected!r}")


def compose_ps() -> list[dict]:
    output = run_compose("ps", "--format", "json").stdout.strip()
    if not output:
        return []
    try:
        parsed = json.loads(output)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        return [json.loads(line) for line in output.splitlines()]


def wait_for_service_health(service: str, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matching = [item for item in compose_ps() if item.get("Service") == service]
        if matching and matching[0].get("Health") == "healthy":
            return
        time.sleep(2)
    raise AssertionError(f"{service} did not become healthy within {timeout}s")


def test_compose_config_is_valid():
    result = run_compose("config")

    assert "postgres:" in result.stdout
    assert "frontend:" in result.stdout


def test_all_services_are_healthy_within_60_seconds():
    deadline = time.monotonic() + 60
    healthy = set()

    while time.monotonic() < deadline:
        healthy = {
            item.get("Service")
            for item in compose_ps()
            if item.get("Health") == "healthy"
        }
        if EXPECTED_SERVICES.issubset(healthy):
            return
        time.sleep(2)

    missing = EXPECTED_SERVICES - healthy
    raise AssertionError(f"Services did not become healthy: {sorted(missing)}")


def test_persistent_volumes_survive_container_restart():
    run_compose(
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "xero",
        "-d",
        "xero",
        "-c",
        (
            "CREATE TABLE IF NOT EXISTS f0001_persistence_probe "
            "(id integer PRIMARY KEY, value text NOT NULL); "
            "INSERT INTO f0001_persistence_probe (id, value) VALUES (1, 'postgres-ok') "
            "ON CONFLICT (id) DO UPDATE SET value = EXCLUDED.value;"
        ),
    )
    run_compose("exec", "-T", "redis", "redis-cli", "SET", "f0001:persistence", "redis-ok")
    run_compose("exec", "-T", "redis", "redis-cli", "SAVE")

    run_compose("restart", "postgres", "redis")
    wait_for_service_health("postgres")
    wait_for_service_health("redis")

    pg_result = run_compose(
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "xero",
        "-d",
        "xero",
        "-tAc",
        "SELECT value FROM f0001_persistence_probe WHERE id = 1;",
    )
    redis_result = run_compose("exec", "-T", "redis", "redis-cli", "GET", "f0001:persistence")

    assert pg_result.stdout.strip() == "postgres-ok"
    assert redis_result.stdout.strip() == "redis-ok"


def test_backend_recovers_after_postgres_restart():
    run_compose("restart", "postgres")
    wait_for_service_health("postgres")
    wait_for_service_health("backend")

    deadline = time.monotonic() + 60
    last_status = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{BACKEND_URL}/ready", timeout=5)
            last_status = response.status_code
            if response.status_code == 200 and response.json()["checks"]["postgres"]["status"] == "healthy":
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)

    raise AssertionError(f"Backend did not recover readiness; last status was {last_status}")


def test_backend_docs_are_accessible_from_host():
    response = httpx.get(f"{BACKEND_URL}/docs", timeout=10)

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "swagger-ui" in response.text.lower()


def test_backend_migrations_are_applied_in_compose():
    output = run_backend_python(
        dedent(
            """
            import json

            from alembic.runtime.migration import MigrationContext
            from alembic.script import ScriptDirectory
            from app.database import session_scope
            from app.manage import alembic_config
            from sqlalchemy import inspect

            cfg = alembic_config()
            expected_heads = list(ScriptDirectory.from_config(cfg).get_heads())
            with session_scope() as session:
                connection = session.connection()
                payload = {
                    "heads": list(MigrationContext.configure(connection).get_current_heads()),
                    "expected_heads": expected_heads,
                    "tables": inspect(connection).get_table_names(),
                    "user_columns": [
                        column["name"]
                        for column in inspect(connection).get_columns("users")
                    ],
                }
            print(json.dumps(payload))
            """
        )
    )

    payload = json.loads(last_output_line(output))
    assert payload["heads"] == payload["expected_heads"]
    assert "users" in payload["tables"]
    assert {"id", "username", "password_hash", "role", "is_enabled", "created_at", "updated_at"}.issubset(
        set(payload["user_columns"])
    )


def test_orm_persistence_survives_postgres_restart():
    username = "f0005_orm_probe"
    stored = run_backend_python(
        dedent(
            f"""
            from app import crud
            from app.auth import get_user_by_username
            from app.database import session_scope
            from app.models import User

            with session_scope() as session:
                user = get_user_by_username(session, "{username}")
                if user is None:
                    user = crud.create(
                        session,
                        User(
                            username="{username}",
                            password_hash="f0005-hash",
                            role="operator",
                            is_enabled=True,
                        ),
                    )
                else:
                    user = crud.update(
                        session,
                        user,
                        password_hash="f0005-hash",
                        role="operator",
                        is_enabled=True,
                    )
                print(f"stored:{{user.username}}:{{user.id}}")
            """
        )
    )
    assert last_output_line(stored).startswith(f"stored:{username}:")

    run_compose("restart", "postgres", "backend")
    wait_for_service_health("postgres")
    wait_for_service_health("backend")

    loaded = run_backend_python(
        dedent(
            f"""
            import json

            from app.auth import get_user_by_username
            from app.database import session_scope

            with session_scope() as session:
                user = get_user_by_username(session, "{username}")
                payload = {{
                    "exists": user is not None,
                    "username": user.username if user else None,
                    "role": user.role if user else None,
                    "is_enabled": user.is_enabled if user else None,
                }}
            print(json.dumps(payload))
            """
        )
    )

    payload = json.loads(last_output_line(loaded))
    assert payload == {
        "exists": True,
        "username": username,
        "role": "operator",
        "is_enabled": True,
    }


def test_redis_queue_round_trip_across_backend_processes():
    queue_name = "f0006:integration"
    producer = run_backend_python(
        dedent(
            f"""
            import asyncio
            import json

            from app.config import get_settings
            from app.redis_bus import create_redis_client, enqueue_task, task_queue_key

            async def main():
                client = create_redis_client(get_settings())
                await client.delete(task_queue_key("{queue_name}"))
                ok = await enqueue_task(
                    client,
                    "{queue_name}",
                    {{"task_id": "task-1", "kind": "probe"}},
                )
                await client.aclose()
                print(json.dumps({{"ok": ok}}))

            asyncio.run(main())
            """
        )
    )
    assert json.loads(last_output_line(producer)) == {"ok": True}

    consumer = run_backend_python(
        dedent(
            f"""
            import asyncio
            import json

            from app.config import get_settings
            from app.redis_bus import create_redis_client, dequeue_task

            async def main():
                settings = get_settings()
                client = create_redis_client(settings)
                payload = await dequeue_task(
                    client,
                    "{queue_name}",
                    settings.redis_queue_dequeue_timeout_seconds,
                )
                await client.aclose()
                print(json.dumps(payload))

            asyncio.run(main())
            """
        )
    )

    assert json.loads(last_output_line(consumer)) == {"task_id": "task-1", "kind": "probe"}


def test_redis_pubsub_message_received_by_subscriber():
    channel = "events:f0006:integration"
    ready_key = "f0006:pubsub:ready"
    subscriber_code = dedent(
        f"""
        import asyncio
        import json

        from app.config import get_settings
        from app.redis_bus import create_redis_client

        async def main():
            client = create_redis_client(get_settings())
            await client.delete("{ready_key}")
            pubsub = client.pubsub()
            await pubsub.subscribe("{channel}")
            subscribe_deadline = asyncio.get_running_loop().time() + 1
            while asyncio.get_running_loop().time() < subscribe_deadline:
                message = await pubsub.get_message(ignore_subscribe_messages=False, timeout=0.1)
                if message and message.get("type") == "subscribe":
                    break
            await client.set("{ready_key}", "1", ex=5)
            deadline = asyncio.get_running_loop().time() + 5
            payload = None
            while asyncio.get_running_loop().time() < deadline:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
                if message and message.get("type") == "message":
                    payload = json.loads(message["data"])
                    break
            await pubsub.unsubscribe("{channel}")
            await pubsub.aclose()
            await client.delete("{ready_key}")
            await client.aclose()
            print(json.dumps(payload or {{"received": False}}))

        asyncio.run(main())
        """
    )
    process = subprocess.Popen(
        ["docker", "compose", "exec", "-T", "backend", "python", "-c", subscriber_code],
        cwd=PLATFORM_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_for_redis_value(ready_key, "1")
        published = run_redis_cli("PUBLISH", channel, json.dumps({"kind": "probe", "status": "ok"}))
        assert int(published) >= 1
        stdout, stderr = process.communicate(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()

    assert process.returncode == 0, stderr
    assert json.loads(last_output_line(stdout)) == {"kind": "probe", "status": "ok"}


def test_protected_api_rate_limit_uses_real_redis():
    login_response = httpx.post(
        f"{BACKEND_URL}/auth/login",
        json={"username": "operator", "password": "operator_password"},
        timeout=10,
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    operator_id = jwt.decode(token, options={"verify_signature": False})["operator_id"]
    prepared = run_backend_python(
        dedent(
            f"""
            import asyncio
            import json

            from app.config import get_settings
            from app.redis_bus import create_redis_client, rate_limit_key

            async def main():
                settings = get_settings()
                client = create_redis_client(settings)
                key = rate_limit_key("{operator_id}", "/api/v1/me")
                await client.set(
                    key,
                    max(0, settings.redis_rate_limit_requests - 1),
                    ex=settings.redis_rate_limit_window_seconds,
                )
                await client.aclose()
                print(json.dumps({{"key": key, "limit": settings.redis_rate_limit_requests}}))

            asyncio.run(main())
            """
        )
    )
    payload = json.loads(last_output_line(prepared))

    first = httpx.get(
        f"{BACKEND_URL}/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    second = httpx.get(
        f"{BACKEND_URL}/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    run_redis_cli("DEL", payload["key"])

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json() == {"detail": "Rate limit exceeded"}


def test_default_operator_can_login_and_access_protected_beacons_endpoint():
    login_response = httpx.post(
        f"{BACKEND_URL}/auth/login",
        json={"username": "operator", "password": "operator_password"},
        timeout=10,
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    beacons_response = httpx.get(
        f"{BACKEND_URL}/api/v1/beacons",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    assert beacons_response.status_code == 200
    assert beacons_response.json() == {"items": []}


def test_default_local_admin_can_login_and_access_protected_beacons_endpoint():
    login_response = httpx.post(
        f"{BACKEND_URL}/auth/login",
        json={"username": "admin", "password": "admin"},
        timeout=10,
    )
    assert login_response.status_code == 200
    assert login_response.json()["operator"]["role"] == "admin"
    assert login_response.json()["operator"]["is_enabled"] is True

    token = login_response.json()["access_token"]
    beacons_response = httpx.get(
        f"{BACKEND_URL}/api/v1/beacons",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    assert beacons_response.status_code == 200
    assert beacons_response.json() == {"items": []}


def test_protected_endpoint_rejects_missing_and_expired_token():
    missing_response = httpx.get(f"{BACKEND_URL}/api/v1/beacons", timeout=10)
    assert missing_response.status_code == 401

    login_response = httpx.post(
        f"{BACKEND_URL}/auth/login",
        json={"username": "operator", "password": "operator_password"},
        timeout=10,
    )
    assert login_response.status_code == 200

    token_claims = jwt.decode(login_response.json()["access_token"], options={"verify_signature": False})
    now = datetime.now(UTC)
    expired_token = jwt.encode(
        {
            "sub": token_claims["sub"],
            "operator_id": token_claims["operator_id"],
            "role": token_claims["role"],
            "iat": now - timedelta(minutes=120),
            "exp": now - timedelta(minutes=60),
        },
        os.getenv("JWT_SECRET_KEY", DEV_JWT_SECRET),
        algorithm="HS256",
    )

    expired_response = httpx.get(
        f"{BACKEND_URL}/api/v1/beacons",
        headers={"Authorization": f"Bearer {expired_token}"},
        timeout=10,
    )

    assert expired_response.status_code == 401
