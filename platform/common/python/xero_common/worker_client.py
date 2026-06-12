from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class WorkerClientError(RuntimeError):
    pass


@dataclass
class WorkerSession:
    worker_id: str
    worker_token: str
    heartbeat_interval_seconds: int


def post_json(url: str, payload: dict[str, Any], *, token: str | None = None, timeout: float = 5) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise WorkerClientError(detail or f"C2 returned HTTP {exc.code}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkerClientError(str(exc)) from exc


def load_worker_session(path: str) -> WorkerSession | None:
    session_path = Path(path)
    if not session_path.exists():
        return None
    try:
        payload = json.loads(session_path.read_text(encoding="utf-8"))
        return WorkerSession(
            worker_id=str(payload["worker_id"]),
            worker_token=str(payload["worker_token"]),
            heartbeat_interval_seconds=int(payload.get("heartbeat_interval_seconds", 10)),
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def save_worker_session(path: str, session: WorkerSession) -> None:
    session_path = Path(path)
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        json.dumps(
            {
                "worker_id": session.worker_id,
                "worker_token": session.worker_token,
                "heartbeat_interval_seconds": session.heartbeat_interval_seconds,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def register_worker(
    *,
    base_url: str,
    kind: str,
    name: str,
    pairing_token: str,
    endpoint: str | None,
    capabilities: list[str],
    capacity: int,
    current_load: int,
    version: str,
) -> WorkerSession:
    payload = post_json(
        f"{base_url.rstrip('/')}/api/v1/infrastructure/workers/register",
        {
            "kind": kind,
            "name": name,
            "pairing_token": pairing_token,
            "endpoint": endpoint,
            "capabilities": capabilities,
            "capacity": capacity,
            "current_load": current_load,
            "version": version,
        },
    )
    return WorkerSession(
        worker_id=str(payload["worker_id"]),
        worker_token=str(payload["worker_token"]),
        heartbeat_interval_seconds=int(payload.get("heartbeat_interval_seconds", 10)),
    )


def heartbeat_worker(
    *,
    base_url: str,
    session: WorkerSession,
    endpoint: str | None,
    capabilities: list[str],
    capacity: int,
    current_load: int,
    version: str,
) -> dict[str, Any]:
    return post_json(
        f"{base_url.rstrip('/')}/api/v1/infrastructure/workers/{session.worker_id}/heartbeat",
        {
            "endpoint": endpoint,
            "capabilities": capabilities,
            "capacity": capacity,
            "current_load": current_load,
            "version": version,
        },
        token=session.worker_token,
    )
