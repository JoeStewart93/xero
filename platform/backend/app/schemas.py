from __future__ import annotations

import ipaddress
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=72)


class OperatorResponse(BaseModel):
    id: str
    username: str
    role: str = "operator"
    is_enabled: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    operator: OperatorResponse


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=1, max_length=72)


class StatusResponse(BaseModel):
    status: str


class BeaconResponse(BaseModel):
    id: str
    machine_fingerprint_hash: str
    hostname: str
    os: str
    architecture: str
    internal_ip: str
    external_ip: str | None = None
    pid: int
    status: str
    first_seen: datetime
    last_seen: datetime


class BeaconListResponse(BaseModel):
    items: list[BeaconResponse] = Field(default_factory=list)


class BeaconRegistrationRequest(BaseModel):
    machine_fingerprint_hash: str = Field(min_length=8, max_length=128)
    hostname: str = Field(min_length=1, max_length=255)
    os: str = Field(min_length=1, max_length=128)
    architecture: str = Field(min_length=1, max_length=64)
    internal_ip: str = Field(min_length=3, max_length=64)
    external_ip: str | None = Field(default=None, min_length=3, max_length=64)
    pid: int = Field(ge=0)

    @field_validator("machine_fingerprint_hash", "hostname", "os", "architecture")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field cannot be blank")
        return normalized

    @field_validator("internal_ip", "external_ip")
    @classmethod
    def validate_ip_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        try:
            ipaddress.ip_address(normalized)
        except ValueError as exc:
            raise ValueError("Enter a valid IP address") from exc
        return normalized


class BeaconRegistrationResponse(BaseModel):
    beacon_id: str
    beacon_token: str
    status: str
    sleep: int = 30
    jitter: float = 0.1
    beacon: BeaconResponse


class BeaconHeartbeatRequest(BaseModel):
    hostname: str | None = Field(default=None, min_length=1, max_length=255)
    os: str | None = Field(default=None, min_length=1, max_length=128)
    architecture: str | None = Field(default=None, min_length=1, max_length=64)
    internal_ip: str | None = Field(default=None, min_length=3, max_length=64)
    external_ip: str | None = Field(default=None, min_length=3, max_length=64)
    pid: int | None = Field(default=None, ge=0)

    @field_validator("hostname", "os", "architecture")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Field cannot be blank")
        return normalized

    @field_validator("internal_ip", "external_ip")
    @classmethod
    def validate_optional_ip_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        try:
            ipaddress.ip_address(normalized)
        except ValueError as exc:
            raise ValueError("Enter a valid IP address") from exc
        return normalized


class BeaconHeartbeatResponse(BaseModel):
    status: str
    sleep: int
    jitter: float
    beacon: BeaconResponse


class C2ConnectRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class C2ConnectResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    service: str
    service_role: str
    status: str = "connected"


class C2SessionResponse(BaseModel):
    service: str
    service_role: str
    status: str
