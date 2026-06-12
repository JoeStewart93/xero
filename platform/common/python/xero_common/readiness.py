from collections.abc import Callable
from typing import Any, Protocol

import psycopg
import redis

CheckResult = dict[str, str]


class ReadinessSettings(Protocol):
    service_name: str
    database_url: str
    redis_url: str


DependencyCheck = Callable[[ReadinessSettings], CheckResult]


def _healthy() -> CheckResult:
    return {"status": "healthy"}


def _unhealthy(exc: Exception) -> CheckResult:
    return {"status": "unhealthy", "error": str(exc)}


def check_postgres(settings: ReadinessSettings) -> CheckResult:
    try:
        with psycopg.connect(settings.database_url, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return _healthy()
    except Exception as exc:  # pragma: no cover - exact driver failures vary.
        return _unhealthy(exc)


def check_redis(settings: ReadinessSettings) -> CheckResult:
    client = redis.Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        client.ping()
        return _healthy()
    except Exception as exc:  # pragma: no cover - exact driver failures vary.
        return _unhealthy(exc)
    finally:
        client.close()


def check_readiness(settings: ReadinessSettings) -> dict[str, Any]:
    checks = {
        "postgres": check_postgres(settings),
        "redis": check_redis(settings),
    }
    ready = all(check["status"] == "healthy" for check in checks.values())
    return {
        "status": "ready" if ready else "degraded",
        "service": settings.service_name,
        "checks": checks,
    }
