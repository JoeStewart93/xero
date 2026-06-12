from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-xero-jwt-secret-change-me"
DEFAULT_C2_CONNECT_PASSWORD = "c2_password"
DEV_PROTOCOL_PRIVATE_KEY_B64 = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    app_env: str = Field(default="development", alias="APP_ENV")
    service_name: str = Field(default="xero-c2-core", alias="C2_SERVICE_NAME")
    service_role: str = "c2"
    database_url: str = Field(
        default="postgresql://xero_c2:xero_c2_password@c2-postgres:5432/xero_c2",
        alias="C2_DATABASE_URL",
    )
    database_pool_size: int = Field(default=5, ge=1, alias="C2_DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, ge=-1, alias="C2_DATABASE_MAX_OVERFLOW")
    database_pool_timeout_seconds: int = Field(default=30, gt=0, alias="C2_DATABASE_POOL_TIMEOUT_SECONDS")
    database_pool_recycle_seconds: int = Field(default=1800, ge=-1, alias="C2_DATABASE_POOL_RECYCLE_SECONDS")
    redis_url: str = Field(default="redis://c2-redis:6379/0", alias="C2_REDIS_URL")
    redis_max_connections: int = Field(default=20, ge=1, alias="C2_REDIS_MAX_CONNECTIONS")
    frontend_origin: str = Field(default="http://localhost:3000", alias="FRONTEND_ORIGIN")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    jwt_secret_key: str = Field(default=DEV_JWT_SECRET, alias="C2_JWT_SECRET_KEY")
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
    worker_pairing_token_expires_minutes: int = Field(default=15, gt=0, alias="WORKER_PAIRING_TOKEN_EXPIRES_MINUTES")
    worker_heartbeat_interval_seconds: int = Field(default=10, gt=0, alias="WORKER_HEARTBEAT_INTERVAL_SECONDS")
    worker_stale_threshold_seconds: int = Field(default=30, gt=0, alias="WORKER_STALE_THRESHOLD_SECONDS")
    local_provisioning_enabled: bool = Field(default=False, alias="C2_LOCAL_PROVISIONING_ENABLED")
    worker_connect_url: str = Field(default="http://host.docker.internal:8001", alias="C2_WORKER_CONNECT_URL")
    provisioning_platform_root: str = Field(default="/workspace/platform", alias="C2_PROVISIONING_PLATFORM_ROOT")
    provisioning_project_prefix: str = Field(default="xero-managed", alias="C2_PROVISIONING_PROJECT_PREFIX")
    protocol_private_key_b64: str = Field(
        default=DEV_PROTOCOL_PRIVATE_KEY_B64,
        alias="C2_PROTOCOL_PRIVATE_KEY_B64",
    )
    protocol_frame_harness_enabled: bool = Field(default=False, alias="C2_PROTOCOL_FRAME_HARNESS_ENABLED")
    protocol_max_frame_bytes: int = Field(default=1_048_576, ge=128, alias="C2_PROTOCOL_MAX_FRAME_BYTES")
    protocol_supported_versions: str = Field(default="1", alias="C2_PROTOCOL_SUPPORTED_VERSIONS")
    beacon_ws_send_queue_size: int = Field(default=32, ge=1, alias="C2_BEACON_WS_SEND_QUEUE_SIZE")
    beacon_ws_registration_timeout_seconds: int = Field(
        default=5,
        gt=0,
        alias="C2_BEACON_WS_REGISTRATION_TIMEOUT_SECONDS",
    )
    beacon_ws_heartbeat_timeout_seconds: int = Field(
        default=90,
        gt=0,
        alias="C2_BEACON_WS_HEARTBEAT_TIMEOUT_SECONDS",
    )
    beacon_ws_ping_interval_seconds: int = Field(default=30, gt=0, alias="C2_BEACON_WS_PING_INTERVAL_SECONDS")
    beacon_ws_ping_timeout_seconds: int = Field(default=30, gt=0, alias="C2_BEACON_WS_PING_TIMEOUT_SECONDS")
    beacon_ws_max_message_bytes: int = Field(default=1_048_576, ge=128, alias="C2_BEACON_WS_MAX_MESSAGE_BYTES")
    beacon_longpoll_timeout_seconds: int = Field(default=60, gt=0, alias="C2_BEACON_LONGPOLL_TIMEOUT_SECONDS")
    beacon_longpoll_max_frame_bytes: int = Field(default=1_048_576, ge=128, alias="C2_BEACON_LONGPOLL_MAX_FRAME_BYTES")
    task_default_timeout_seconds: int = Field(default=60, gt=0, alias="C2_TASK_DEFAULT_TIMEOUT_SECONDS")
    task_max_timeout_seconds: int = Field(default=3600, gt=0, alias="C2_TASK_MAX_TIMEOUT_SECONDS")
    task_retention_days: int = Field(default=30, gt=0, alias="C2_TASK_RETENTION_DAYS")

    @field_validator("api_v1_prefix")
    @classmethod
    def normalize_api_prefix(cls, value: str) -> str:
        prefix = value.strip()
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        return prefix.rstrip("/") or "/"

    @field_validator("beacon_stale_threshold_seconds", mode="before")
    @classmethod
    def normalize_optional_stale_threshold(cls, value):
        if value == "":
            return None
        return value

    @field_validator("protocol_supported_versions")
    @classmethod
    def normalize_protocol_supported_versions(cls, value: str) -> str:
        versions: list[str] = []
        for item in value.split(","):
            normalized = item.strip()
            if not normalized:
                continue
            if not normalized.isdigit() or int(normalized) <= 0:
                raise ValueError("C2_PROTOCOL_SUPPORTED_VERSIONS must be a comma-separated list of positive integers")
            versions.append(str(int(normalized)))
        if not versions:
            raise ValueError("C2_PROTOCOL_SUPPORTED_VERSIONS must include at least one version")
        return ",".join(dict.fromkeys(versions))

    @field_validator(
        "service_name",
        "jwt_secret_key",
        "c2_connect_password",
        "worker_connect_url",
        "provisioning_platform_root",
        "provisioning_project_prefix",
        "protocol_private_key_b64",
        "protocol_supported_versions",
    )
    @classmethod
    def reject_blank_secret_values(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("C2 configuration values cannot be blank")
        return normalized

    @model_validator(mode="after")
    def reject_dev_auth_defaults_outside_local_modes(self) -> "Settings":
        local_modes = {"development", "test"}
        if self.task_default_timeout_seconds > self.task_max_timeout_seconds:
            raise ValueError("C2_TASK_DEFAULT_TIMEOUT_SECONDS must be <= C2_TASK_MAX_TIMEOUT_SECONDS")
        if self.app_env.lower() not in local_modes:
            if self.jwt_secret_key == DEV_JWT_SECRET or len(self.jwt_secret_key) < 32:
                raise ValueError("C2_JWT_SECRET_KEY must be set to a non-default value outside development/test")
            if self.c2_connect_password == DEFAULT_C2_CONNECT_PASSWORD:
                raise ValueError("C2_CONNECT_PASSWORD must be set to a non-default value outside development/test")
            if self.protocol_private_key_b64 == DEV_PROTOCOL_PRIVATE_KEY_B64:
                raise ValueError("C2_PROTOCOL_PRIVATE_KEY_B64 must be set outside development/test")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
