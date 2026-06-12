from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    app_env: str = Field(default="development", alias="APP_ENV")
    service_name: str = Field(default="xero-scanner", alias="SCANNER_SERVICE_NAME")
    service_role: str = "scanner"
    c2_base_url: str | None = Field(default=None, alias="C2_BASE_URL")
    worker_pairing_token: str | None = Field(default=None, alias="WORKER_PAIRING_TOKEN")
    worker_token_file: str = Field(default="/data/worker-session.json", alias="WORKER_TOKEN_FILE")
    worker_name: str | None = Field(default=None, alias="WORKER_NAME")
    worker_endpoint: str | None = Field(default=None, alias="WORKER_ENDPOINT")
    worker_capacity: int = Field(default=25, ge=1, alias="WORKER_CAPACITY")
    worker_heartbeat_interval_seconds: int = Field(default=10, gt=0, alias="WORKER_HEARTBEAT_INTERVAL_SECONDS")
    worker_version: str = Field(default="0.1.0", alias="WORKER_VERSION")

    @field_validator("c2_base_url", "worker_pairing_token", "worker_name", "worker_endpoint", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
