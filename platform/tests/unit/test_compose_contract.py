from __future__ import annotations

from pathlib import Path

import yaml

PLATFORM_ROOT = Path(__file__).resolve().parents[2]
BFF_COMPOSE = PLATFORM_ROOT / "docker-compose.bff.yml"
DEFAULT_COMPOSE = PLATFORM_ROOT / "docker-compose.yml"
C2_COMPOSE = PLATFORM_ROOT / "docker-compose.c2.yml"
HANDLER_COMPOSE = PLATFORM_ROOT / "docker-compose.handler.yml"
SCANNER_COMPOSE = PLATFORM_ROOT / "docker-compose.scanner.yml"
ENV_EXAMPLE = PLATFORM_ROOT / ".env.example"


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def parse_env_example() -> dict[str, str]:
    values = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


def test_bff_compose_defines_ui_bff_stack_and_default_alias_matches():
    compose = load_yaml(BFF_COMPOSE)
    default_compose = load_yaml(DEFAULT_COMPOSE)

    assert default_compose == compose
    assert set(compose["services"]) == {"bff-postgres", "bff-redis", "bff-api", "frontend"}
    assert compose["services"]["bff-api"]["build"] == {
        "context": ".",
        "dockerfile": "services/bff-api/Dockerfile",
    }
    assert compose["services"]["bff-api"]["ports"] == ["${BACKEND_PORT:-8000}:8000"]
    assert "XERO_SERVICE_ROLE" not in compose["services"]["bff-api"]["environment"]
    assert set(compose["volumes"]) == {"xero_bff_postgres_data", "xero_bff_redis_data"}
    assert compose["services"]["frontend"]["depends_on"]["bff-api"]["condition"] == "service_healthy"


def test_c2_compose_defines_c2_api_stack_without_bff_seed_env():
    compose = load_yaml(C2_COMPOSE)

    assert set(compose["services"]) == {"c2-postgres", "c2-redis", "c2-api"}
    assert compose["services"]["c2-api"]["build"] == {
        "context": ".",
        "dockerfile": "services/c2-api/Dockerfile",
    }
    assert compose["services"]["c2-api"]["ports"] == ["${C2_BACKEND_PORT:-8001}:8000"]
    env = compose["services"]["c2-api"]["environment"]
    assert "XERO_SERVICE_ROLE" not in env
    assert "OPERATOR_USERNAME" not in env
    assert "LOCAL_ADMIN_USERNAME" not in env
    assert env["C2_CONNECT_PASSWORD"] == "${C2_CONNECT_PASSWORD:-c2_password}"
    assert env["C2_LOCAL_PROVISIONING_ENABLED"] == "${C2_LOCAL_PROVISIONING_ENABLED:-true}"
    assert env["C2_PROTOCOL_FRAME_HARNESS_ENABLED"] == "${C2_PROTOCOL_FRAME_HARNESS_ENABLED:-false}"
    assert env["C2_PROTOCOL_SUPPORTED_VERSIONS"] == "${C2_PROTOCOL_SUPPORTED_VERSIONS:-1}"
    assert env["C2_BEACON_WS_SEND_QUEUE_SIZE"] == "${C2_BEACON_WS_SEND_QUEUE_SIZE:-32}"
    assert env["C2_BEACON_WS_PING_INTERVAL_SECONDS"] == "${C2_BEACON_WS_PING_INTERVAL_SECONDS:-30}"
    assert env["C2_BEACON_WS_MAX_MESSAGE_BYTES"] == "${C2_BEACON_WS_MAX_MESSAGE_BYTES:-1048576}"
    assert env["C2_WORKER_CONNECT_URL"] == "${C2_WORKER_CONNECT_URL:-http://host.docker.internal:8001}"
    assert "/var/run/docker.sock:/var/run/docker.sock" in compose["services"]["c2-api"]["volumes"]
    assert set(compose["volumes"]) == {"xero_c2_postgres_data", "xero_c2_redis_data"}


def test_handler_and_scanner_compose_files_define_scaffold_services():
    handler = load_yaml(HANDLER_COMPOSE)
    scanner = load_yaml(SCANNER_COMPOSE)

    assert set(handler["services"]) == {"beacon-handler"}
    assert handler["services"]["beacon-handler"]["build"]["dockerfile"] == "services/beacon-handler/Dockerfile"
    assert handler["services"]["beacon-handler"]["ports"] == ["${HANDLER_PORT:-8002}:8000"]
    assert handler["services"]["beacon-handler"]["environment"]["C2_BASE_URL"] == "${C2_BASE_URL:-}"
    assert handler["services"]["beacon-handler"]["environment"]["WORKER_PAIRING_TOKEN"] == "${WORKER_PAIRING_TOKEN:-}"
    assert set(handler["volumes"]) == {"xero_handler_data"}
    assert "healthcheck" in handler["services"]["beacon-handler"]

    assert set(scanner["services"]) == {"scanner"}
    assert scanner["services"]["scanner"]["build"]["dockerfile"] == "services/scanner/Dockerfile"
    assert scanner["services"]["scanner"]["ports"] == ["${SCANNER_PORT:-8003}:8000"]
    assert scanner["services"]["scanner"]["environment"]["C2_BASE_URL"] == "${C2_BASE_URL:-}"
    assert scanner["services"]["scanner"]["environment"]["WORKER_PAIRING_TOKEN"] == "${WORKER_PAIRING_TOKEN:-}"
    assert set(scanner["volumes"]) == {"xero_scanner_data"}
    assert "healthcheck" in scanner["services"]["scanner"]


def test_env_example_contains_variables_consumed_by_split_compose_files():
    env = parse_env_example()

    assert {
        "APP_ENV",
        "API_V1_PREFIX",
        "FRONTEND_ORIGIN",
        "BFF_SERVICE_NAME",
        "BFF_POSTGRES_DB",
        "BFF_POSTGRES_USER",
        "BFF_POSTGRES_PASSWORD",
        "DATABASE_URL",
        "REDIS_URL",
        "BACKEND_PORT",
        "OPERATOR_USERNAME",
        "OPERATOR_PASSWORD",
        "LOCAL_ADMIN_USERNAME",
        "LOCAL_ADMIN_PASSWORD",
        "JWT_SECRET_KEY",
        "C2_BACKEND_PORT",
        "C2_SERVICE_NAME",
        "C2_POSTGRES_DB",
        "C2_POSTGRES_USER",
        "C2_POSTGRES_PASSWORD",
        "C2_DATABASE_URL",
        "C2_REDIS_URL",
        "C2_CONNECT_PASSWORD",
        "C2_TOKEN_EXPIRES_MINUTES",
        "C2_JWT_SECRET_KEY",
        "C2_PROTOCOL_PRIVATE_KEY_B64",
        "C2_PROTOCOL_FRAME_HARNESS_ENABLED",
        "C2_PROTOCOL_MAX_FRAME_BYTES",
        "C2_PROTOCOL_SUPPORTED_VERSIONS",
        "C2_BEACON_WS_SEND_QUEUE_SIZE",
        "C2_BEACON_WS_REGISTRATION_TIMEOUT_SECONDS",
        "C2_BEACON_WS_HEARTBEAT_TIMEOUT_SECONDS",
        "C2_BEACON_WS_PING_INTERVAL_SECONDS",
        "C2_BEACON_WS_PING_TIMEOUT_SECONDS",
        "C2_BEACON_WS_MAX_MESSAGE_BYTES",
        "WORKER_PAIRING_TOKEN_EXPIRES_MINUTES",
        "WORKER_HEARTBEAT_INTERVAL_SECONDS",
        "WORKER_STALE_THRESHOLD_SECONDS",
        "C2_LOCAL_PROVISIONING_ENABLED",
        "C2_WORKER_CONNECT_URL",
        "C2_PROVISIONING_PLATFORM_ROOT",
        "C2_PROVISIONING_PROJECT_PREFIX",
        "HANDLER_SERVICE_NAME",
        "HANDLER_PORT",
        "SCANNER_SERVICE_NAME",
        "SCANNER_PORT",
        "C2_BASE_URL",
        "WORKER_PAIRING_TOKEN",
        "WORKER_NAME",
        "WORKER_ENDPOINT",
        "WORKER_CAPACITY",
        "FRONTEND_PORT",
        "VITE_API_BASE_URL",
        "VITE_DEFAULT_C2_BASE_URL",
    }.issubset(env)
