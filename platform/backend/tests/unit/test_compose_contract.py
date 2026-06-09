from pathlib import Path

import yaml

PLATFORM_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = PLATFORM_ROOT / "docker-compose.yml"
C2_COMPOSE_FILE = PLATFORM_ROOT / "docker-compose.c2.yml"
ENV_EXAMPLE = PLATFORM_ROOT / ".env.example"


def load_compose() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


def load_c2_compose() -> dict:
    return yaml.safe_load(C2_COMPOSE_FILE.read_text(encoding="utf-8"))


def parse_env_example() -> dict[str, str]:
    values = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


def test_compose_defines_required_services_network_and_volumes():
    compose = load_compose()

    assert set(compose["services"]) == {"postgres", "redis", "backend", "frontend"}
    assert compose["networks"]["xero"]["driver"] == "bridge"
    assert set(compose["volumes"]) == {"xero_postgres_data", "xero_redis_data"}

    for service in compose["services"].values():
        assert "xero" in service["networks"]


def test_compose_wires_persistent_storage_and_service_names():
    compose = load_compose()

    assert "xero_postgres_data:/var/lib/postgresql/data" in compose["services"]["postgres"]["volumes"]
    assert "xero_redis_data:/data" in compose["services"]["redis"]["volumes"]
    assert "--appendonly" in compose["services"]["redis"]["command"]
    assert compose["services"]["backend"]["environment"]["DATABASE_URL"].endswith("@postgres:5432/xero}")
    assert compose["services"]["backend"]["environment"]["DATABASE_POOL_SIZE"] == "${DATABASE_POOL_SIZE:-5}"
    assert compose["services"]["backend"]["environment"]["DATABASE_MAX_OVERFLOW"] == "${DATABASE_MAX_OVERFLOW:-10}"
    assert compose["services"]["backend"]["environment"]["REDIS_URL"].startswith("${REDIS_URL:-redis://redis:6379")
    assert compose["services"]["backend"]["environment"]["REDIS_MAX_CONNECTIONS"] == "${REDIS_MAX_CONNECTIONS:-20}"
    assert compose["services"]["backend"]["environment"]["REDIS_RATE_LIMIT_REQUESTS"] == (
        "${REDIS_RATE_LIMIT_REQUESTS:-120}"
    )
    assert compose["services"]["backend"]["environment"]["XERO_SERVICE_ROLE"] == "bff"


def test_compose_healthchecks_and_dependency_ordering_are_present():
    compose = load_compose()
    services = compose["services"]

    for service_name in ("postgres", "redis", "backend", "frontend"):
        assert "healthcheck" in services[service_name]
        assert "test" in services[service_name]["healthcheck"]

    assert services["backend"]["depends_on"]["postgres"]["condition"] == "service_healthy"
    assert services["backend"]["depends_on"]["redis"]["condition"] == "service_healthy"
    assert services["frontend"]["depends_on"]["backend"]["condition"] == "service_healthy"


def test_env_example_contains_required_variables():
    env = parse_env_example()

    assert {
        "APP_ENV",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "DATABASE_URL",
        "DATABASE_POOL_SIZE",
        "DATABASE_MAX_OVERFLOW",
        "DATABASE_POOL_TIMEOUT_SECONDS",
        "DATABASE_POOL_RECYCLE_SECONDS",
        "REDIS_URL",
        "REDIS_MAX_CONNECTIONS",
        "REDIS_QUEUE_DEQUEUE_TIMEOUT_SECONDS",
        "REDIS_RATE_LIMIT_ENABLED",
        "REDIS_RATE_LIMIT_REQUESTS",
        "REDIS_RATE_LIMIT_WINDOW_SECONDS",
        "BACKEND_HOST",
        "BACKEND_PORT",
        "API_V1_PREFIX",
        "FRONTEND_ORIGIN",
        "FRONTEND_PORT",
        "VITE_API_BASE_URL",
        "VITE_DEFAULT_C2_BASE_URL",
        "BFF_SERVICE_NAME",
        "C2_BACKEND_PORT",
        "C2_SERVICE_NAME",
        "C2_DATABASE_POOL_SIZE",
        "C2_DATABASE_MAX_OVERFLOW",
        "C2_DATABASE_POOL_TIMEOUT_SECONDS",
        "C2_DATABASE_POOL_RECYCLE_SECONDS",
        "C2_REDIS_MAX_CONNECTIONS",
        "C2_REDIS_QUEUE_DEQUEUE_TIMEOUT_SECONDS",
        "C2_REDIS_RATE_LIMIT_ENABLED",
        "C2_REDIS_RATE_LIMIT_REQUESTS",
        "C2_REDIS_RATE_LIMIT_WINDOW_SECONDS",
        "C2_CONNECT_PASSWORD",
        "C2_TOKEN_EXPIRES_MINUTES",
    }.issubset(env)


def test_c2_compose_defines_separate_c2_stack():
    compose = load_c2_compose()

    assert set(compose["services"]) == {"c2-postgres", "c2-redis", "c2-backend"}
    assert compose["name"] == "xero-c2"
    assert compose["networks"]["xero-c2"]["driver"] == "bridge"
    assert set(compose["volumes"]) == {"xero_c2_postgres_data", "xero_c2_redis_data"}
    assert compose["services"]["c2-backend"]["environment"]["XERO_SERVICE_ROLE"] == "c2"
    assert compose["services"]["c2-backend"]["environment"]["DATABASE_POOL_SIZE"] == "${C2_DATABASE_POOL_SIZE:-5}"
    assert (
        compose["services"]["c2-backend"]["environment"]["DATABASE_MAX_OVERFLOW"]
        == "${C2_DATABASE_MAX_OVERFLOW:-10}"
    )
    assert compose["services"]["c2-backend"]["environment"]["C2_CONNECT_PASSWORD"].startswith("${C2_CONNECT_PASSWORD:-")
    assert (
        compose["services"]["c2-backend"]["environment"]["REDIS_MAX_CONNECTIONS"]
        == "${C2_REDIS_MAX_CONNECTIONS:-20}"
    )
    assert compose["services"]["c2-backend"]["ports"] == ["${C2_BACKEND_PORT:-8001}:8000"]
    assert compose["services"]["c2-backend"]["depends_on"]["c2-postgres"]["condition"] == "service_healthy"
    assert compose["services"]["c2-backend"]["depends_on"]["c2-redis"]["condition"] == "service_healthy"
