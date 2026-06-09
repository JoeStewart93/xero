from app import main as main_module
from app.config import Settings, get_settings
from app.main import create_app
from fastapi.testclient import TestClient


def test_config_parses_env_values(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("XERO_SERVICE_NAME", "xero-bff")
    monkeypatch.setenv("XERO_SERVICE_ROLE", "bff")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@postgres:5432/db")
    monkeypatch.setenv("DATABASE_POOL_SIZE", "6")
    monkeypatch.setenv("DATABASE_MAX_OVERFLOW", "12")
    monkeypatch.setenv("DATABASE_POOL_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("DATABASE_POOL_RECYCLE_SECONDS", "1200")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/1")
    monkeypatch.setenv("REDIS_MAX_CONNECTIONS", "30")
    monkeypatch.setenv("REDIS_QUEUE_DEQUEUE_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("REDIS_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("REDIS_RATE_LIMIT_REQUESTS", "42")
    monkeypatch.setenv("REDIS_RATE_LIMIT_WINDOW_SECONDS", "30")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:3000")
    monkeypatch.setenv("API_V1_PREFIX", "api/v1")
    monkeypatch.setenv("C2_CONNECT_PASSWORD", "local-c2-password")

    settings = Settings()

    assert settings.app_env == "test"
    assert settings.service_name == "xero-bff"
    assert settings.service_role == "bff"
    assert settings.database_url == "postgresql://user:pass@postgres:5432/db"
    assert settings.database_pool_size == 6
    assert settings.database_max_overflow == 12
    assert settings.database_pool_timeout_seconds == 15
    assert settings.database_pool_recycle_seconds == 1200
    assert settings.redis_url == "redis://redis:6379/1"
    assert settings.redis_max_connections == 30
    assert settings.redis_queue_dequeue_timeout_seconds == 2.5
    assert settings.redis_rate_limit_enabled is True
    assert settings.redis_rate_limit_requests == 42
    assert settings.redis_rate_limit_window_seconds == 30
    assert settings.frontend_origin == "http://localhost:3000"
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.operator_username == "operator"
    assert settings.local_admin_username == "admin"
    assert settings.jwt_expires_minutes == 60
    assert settings.c2_connect_password == "local-c2-password"
    assert settings.c2_token_expires_minutes == 480


def test_health_endpoint_returns_liveness_payload(make_test_client):
    client = make_test_client()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "xero-core",
        "role": "core",
        "environment": "test",
    }


def test_api_v1_health_requires_operator_token(make_test_client):
    client = make_test_client()
    response = client.get("/api/v1/health")

    assert response.status_code == 401


def test_api_v1_ready_requires_operator_token(make_test_client):
    client = make_test_client()
    response = client.get("/api/v1/ready")

    assert response.status_code == 401


def test_docs_serves_swagger_ui(make_test_client):
    client = make_test_client()

    response = client.get("/docs")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "swagger-ui" in response.text.lower()


def test_openapi_json_documents_registered_routes(make_test_client):
    client = make_test_client()

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths
    assert "/ready" in paths
    assert "/auth/login" in paths
    assert "/api/v1/health" in paths
    assert "/api/v1/ready" in paths
    assert "/api/v1/c2/connect" in paths
    assert "/api/v1/me" in paths
    assert "/api/v1/beacons" in paths
    assert "/me" not in paths


def test_api_v1_prefix_is_configurable(make_test_client):
    client = make_test_client(API_V1_PREFIX="/custom/v1")

    prefixed_response = client.get("/custom/v1/health")
    default_response = client.get("/api/v1/health")

    assert prefixed_response.status_code == 401
    assert default_response.status_code == 404


def test_cors_preflight_allows_configured_frontend_origin(make_test_client):
    origin = "http://localhost:3100"
    client = make_test_client(FRONTEND_ORIGIN=origin)

    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_unhandled_exceptions_return_json_response(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "test")
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error", "error": "RuntimeError"}


def test_ready_endpoint_reports_dependency_health(monkeypatch, make_test_client):
    def healthy_readiness(_):
        return {
            "status": "ready",
            "service": "xero-core",
            "checks": {
                "postgres": {"status": "healthy"},
                "redis": {"status": "healthy"},
            },
        }

    monkeypatch.setattr(main_module, "check_readiness", healthy_readiness)
    client = make_test_client()

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["checks"]["postgres"]["status"] == "healthy"
    assert response.json()["checks"]["redis"]["status"] == "healthy"


def test_ready_endpoint_returns_503_when_dependency_is_unhealthy(monkeypatch, make_test_client):
    def degraded_readiness(_):
        return {
            "status": "degraded",
            "service": "xero-core",
            "checks": {
                "postgres": {"status": "unhealthy", "error": "connection failed"},
                "redis": {"status": "healthy"},
            },
        }

    monkeypatch.setattr(main_module, "check_readiness", degraded_readiness)
    client = make_test_client()

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["postgres"]["status"] == "unhealthy"
