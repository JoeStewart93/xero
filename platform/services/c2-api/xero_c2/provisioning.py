from __future__ import annotations

import os
import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from xero_c2.config import Settings
from xero_c2.infrastructure_workers import WORKER_KIND_HANDLER, WORKER_KIND_SCANNER


class ProvisioningError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProvisioningSpec:
    compose_file: str
    service_name: str
    port_env: str
    service_name_env: str
    default_port: int


PROVISIONING_SPECS = {
    WORKER_KIND_HANDLER: ProvisioningSpec(
        compose_file="docker-compose.handler.yml",
        service_name="beacon-handler",
        port_env="HANDLER_PORT",
        service_name_env="HANDLER_SERVICE_NAME",
        default_port=8002,
    ),
    WORKER_KIND_SCANNER: ProvisioningSpec(
        compose_file="docker-compose.scanner.yml",
        service_name="scanner",
        port_env="SCANNER_PORT",
        service_name_env="SCANNER_SERVICE_NAME",
        default_port=8003,
    ),
}

PROJECT_FRAGMENT_PATTERN = re.compile(r"[^a-z0-9-]+")


def managed_project_name(settings: Settings, kind: str, worker_id: object) -> str:
    fragment = PROJECT_FRAGMENT_PATTERN.sub("-", kind.lower()).strip("-")
    return f"{settings.provisioning_project_prefix}-{fragment}-{str(worker_id)[:8]}"


def worker_endpoint(settings: Settings, port: int) -> str:
    base = settings.worker_connect_url
    try:
        scheme, remainder = base.split("://", 1)
        host = remainder.split("/", 1)[0].split(":", 1)[0]
        return f"{scheme}://{host}:{port}"
    except ValueError:
        return f"http://host.docker.internal:{port}"


def compose_spec(kind: str) -> ProvisioningSpec:
    try:
        return PROVISIONING_SPECS[kind]
    except KeyError as exc:
        raise ProvisioningError(f"Unsupported worker kind: {kind}") from exc


def run_compose(args: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=False)
    if result.returncode == 0 or args[:2] != ["docker", "compose"]:
        return result
    fallback = ["docker-compose", *args[2:]]
    try:
        return subprocess.run(fallback, cwd=cwd, env=env, text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return result


def launch_worker(
    settings: Settings,
    *,
    kind: str,
    name: str,
    worker_id: uuid.UUID,
    pairing_token: str,
    host_port: int,
) -> tuple[str, str]:
    if not settings.local_provisioning_enabled:
        raise ProvisioningError("C2 local provisioning is disabled.")

    spec = compose_spec(kind)
    platform_root = Path(settings.provisioning_platform_root)
    compose_file = platform_root / spec.compose_file
    if not compose_file.exists():
        raise ProvisioningError(f"Provisioning compose file is unavailable: {spec.compose_file}")

    project_name = managed_project_name(settings, kind, worker_id)
    endpoint = worker_endpoint(settings, host_port)
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": settings.app_env,
            "C2_BASE_URL": settings.worker_connect_url,
            "WORKER_PAIRING_TOKEN": pairing_token,
            "WORKER_NAME": name,
            "WORKER_ENDPOINT": endpoint,
            spec.port_env: str(host_port),
            spec.service_name_env: name,
        }
    )

    result = run_compose(
        ["docker", "compose", "-p", project_name, "-f", str(compose_file), "up", "-d", "--build"],
        cwd=platform_root,
        env=env,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Docker Compose launch failed.").strip()
        raise ProvisioningError(detail)
    return project_name, endpoint


def stop_worker(settings: Settings, *, kind: str, project_name: str) -> None:
    if not settings.local_provisioning_enabled:
        raise ProvisioningError("C2 local provisioning is disabled.")

    spec = compose_spec(kind)
    platform_root = Path(settings.provisioning_platform_root)
    compose_file = platform_root / spec.compose_file
    if not compose_file.exists():
        raise ProvisioningError(f"Provisioning compose file is unavailable: {spec.compose_file}")

    result = run_compose(
        ["docker", "compose", "-p", project_name, "-f", str(compose_file), "down"],
        cwd=platform_root,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Docker Compose stop failed.").strip()
        raise ProvisioningError(detail)
