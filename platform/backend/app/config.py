from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-xero-jwt-secret-change-me"
DEV_OPERATOR_PASSWORD = "operator_password"
DEFAULT_LOCAL_ADMIN_USERNAME = "admin"
DEFAULT_LOCAL_ADMIN_PASSWORD = "admin"
DEFAULT_C2_CONNECT_PASSWORD = "c2_password"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    app_env: str = Field(default="development", alias="APP_ENV")
    service_name: str = Field(default="xero-core", alias="XERO_SERVICE_NAME")
    service_role: str = Field(default="core", alias="XERO_SERVICE_ROLE")
    database_url: str = Field(
        default="postgresql://xero:xero_password@postgres:5432/xero",
        alias="DATABASE_URL",
    )
    database_pool_size: int = Field(default=5, ge=1, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, ge=-1, alias="DATABASE_MAX_OVERFLOW")
    database_pool_timeout_seconds: int = Field(default=30, gt=0, alias="DATABASE_POOL_TIMEOUT_SECONDS")
    database_pool_recycle_seconds: int = Field(default=1800, ge=-1, alias="DATABASE_POOL_RECYCLE_SECONDS")
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    redis_max_connections: int = Field(default=20, ge=1, alias="REDIS_MAX_CONNECTIONS")
    redis_queue_dequeue_timeout_seconds: float = Field(default=1, gt=0, alias="REDIS_QUEUE_DEQUEUE_TIMEOUT_SECONDS")
    redis_rate_limit_enabled: bool = Field(default=True, alias="REDIS_RATE_LIMIT_ENABLED")
    redis_rate_limit_requests: int = Field(default=120, ge=1, alias="REDIS_RATE_LIMIT_REQUESTS")
    redis_rate_limit_window_seconds: int = Field(default=60, ge=1, alias="REDIS_RATE_LIMIT_WINDOW_SECONDS")
    frontend_origin: str = Field(
        default="http://localhost:3000",
        alias="FRONTEND_ORIGIN",
    )
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    operator_username: str = Field(default="operator", alias="OPERATOR_USERNAME")
    operator_password: str = Field(default=DEV_OPERATOR_PASSWORD, alias="OPERATOR_PASSWORD")
    local_admin_username: str = Field(default=DEFAULT_LOCAL_ADMIN_USERNAME, alias="LOCAL_ADMIN_USERNAME")
    local_admin_password: str = Field(default=DEFAULT_LOCAL_ADMIN_PASSWORD, alias="LOCAL_ADMIN_PASSWORD")
    jwt_secret_key: str = Field(default=DEV_JWT_SECRET, alias="JWT_SECRET_KEY")
    jwt_expires_minutes: int = Field(default=60, gt=0, alias="JWT_EXPIRES_MINUTES")
    bcrypt_rounds: int = Field(default=12, ge=4, le=14, alias="BCRYPT_ROUNDS")
    c2_connect_password: str = Field(default=DEFAULT_C2_CONNECT_PASSWORD, alias="C2_CONNECT_PASSWORD")
    c2_token_expires_minutes: int = Field(default=480, gt=0, alias="C2_TOKEN_EXPIRES_MINUTES")
    beacon_default_sleep_seconds: int = Field(default=30, gt=0, alias="BEACON_DEFAULT_SLEEP_SECONDS")
    beacon_default_jitter: float = Field(default=0.1, ge=0, le=1, alias="BEACON_DEFAULT_JITTER")
    beacon_heartbeat_check_interval_seconds: int = Field(
        default=30,
        gt=0,
        alias="BEACON_HEARTBEAT_CHECK_INTERVAL_SECONDS",
    )
    beacon_stale_threshold_multiplier: float = Field(default=3, gt=0, alias="BEACON_STALE_THRESHOLD_MULTIPLIER")
    beacon_stale_threshold_seconds: int | None = Field(default=None, gt=0, alias="BEACON_STALE_THRESHOLD_SECONDS")

    @field_validator("api_v1_prefix")
    @classmethod
    def normalize_api_prefix(cls, value: str) -> str:
        prefix = value.strip()
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        return prefix.rstrip("/") or "/"

    @field_validator(
        "service_name",
        "service_role",
        "operator_username",
        "operator_password",
        "local_admin_username",
        "local_admin_password",
        "jwt_secret_key",
        "c2_connect_password",
    )
    @classmethod
    def reject_blank_secret_values(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Auth configuration values cannot be blank")
        return normalized

    @model_validator(mode="after")
    def reject_dev_auth_defaults_outside_local_modes(self) -> "Settings":
        local_modes = {"development", "test"}
        if self.app_env.lower() not in local_modes:
            if self.jwt_secret_key == DEV_JWT_SECRET or len(self.jwt_secret_key) < 32:
                raise ValueError("JWT_SECRET_KEY must be set to a non-default value outside development/test")
            if self.operator_password == DEV_OPERATOR_PASSWORD:
                raise ValueError("OPERATOR_PASSWORD must be set to a non-default value outside development/test")
            if self.local_admin_password == DEFAULT_LOCAL_ADMIN_PASSWORD:
                raise ValueError("LOCAL_ADMIN_PASSWORD must be set to a non-default value outside development/test")
            if self.c2_connect_password == DEFAULT_C2_CONNECT_PASSWORD:
                raise ValueError("C2_CONNECT_PASSWORD must be set to a non-default value outside development/test")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
