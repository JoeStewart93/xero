from __future__ import annotations

import ipaddress
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


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
    protocol_version: int | None = None
    transport_mode: Literal["long-poll", "rest", "websocket"] = "rest"
    transport_connected: bool = False
    transport_last_seen: datetime | None = None
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


class ProtocolInfoResponse(BaseModel):
    current_version: int
    supported_versions: list[int]
    key_exchange: str
    encryption: str
    integrity: str
    frame_header_length: int
    max_frame_bytes: int
    c2_public_key_b64: str
    frame_harness_enabled: bool


class ProtocolSecurityEventResponse(BaseModel):
    id: str
    beacon_id: str | None = None
    event_type: str
    severity: str
    message: str
    session_id: str | None = None
    nonce: str | None = None
    occurred_at: datetime


class ProtocolSecurityEventListResponse(BaseModel):
    items: list[ProtocolSecurityEventResponse] = Field(default_factory=list)


class TransportStatusResponse(BaseModel):
    active_websocket_connections: int
    active_longpoll_requests: int
    transport_mode_counts: dict[str, int]
    websocket_send_queue_size: int
    websocket_registration_timeout_seconds: int
    websocket_heartbeat_timeout_seconds: int
    websocket_ping_interval_seconds: int
    websocket_ping_timeout_seconds: int
    websocket_max_message_bytes: int
    longpoll_timeout_seconds: int
    longpoll_max_frame_bytes: int


WorkerKind = Literal["beacon-handler", "scanner"]


class InfrastructureWorkerResponse(BaseModel):
    id: str
    kind: WorkerKind
    name: str
    origin: Literal["embedded", "external", "c2-managed"]
    status: Literal["pending", "online", "offline", "starting", "stopping", "failed"]
    endpoint: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    capacity: int
    current_load: int
    version: str | None = None
    last_seen: datetime | None = None
    managed_project: str | None = None
    managed_service: str | None = None
    managed_host_port: int | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class InfrastructureWorkerListResponse(BaseModel):
    items: list[InfrastructureWorkerResponse] = Field(default_factory=list)


class PairingTokenCreateRequest(BaseModel):
    kind: WorkerKind
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name cannot be blank")
        return normalized


class PairingTokenCreateResponse(BaseModel):
    id: str
    kind: WorkerKind
    name: str
    pairing_token: str
    expires_at: datetime
    command: str


class WorkerRegistrationRequest(BaseModel):
    kind: WorkerKind
    name: str = Field(min_length=1, max_length=255)
    pairing_token: str = Field(min_length=16, max_length=256)
    endpoint: str | None = Field(default=None, max_length=512)
    capabilities: list[str] = Field(default_factory=list, max_length=32)
    capacity: int = Field(default=1, ge=1, le=100000)
    current_load: int = Field(default=0, ge=0)
    version: str | None = Field(default=None, max_length=64)

    @field_validator("name")
    @classmethod
    def normalize_worker_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name cannot be blank")
        return normalized

    @field_validator("capabilities")
    @classmethod
    def normalize_capabilities(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class WorkerRegistrationResponse(BaseModel):
    worker_id: str
    worker_token: str
    heartbeat_interval_seconds: int
    worker: InfrastructureWorkerResponse


class WorkerHeartbeatRequest(BaseModel):
    endpoint: str | None = Field(default=None, max_length=512)
    capabilities: list[str] = Field(default_factory=list, max_length=32)
    capacity: int = Field(default=1, ge=1, le=100000)
    current_load: int = Field(default=0, ge=0)
    version: str | None = Field(default=None, max_length=64)

    @field_validator("capabilities")
    @classmethod
    def normalize_heartbeat_capabilities(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class WorkerHeartbeatResponse(BaseModel):
    status: str
    heartbeat_interval_seconds: int
    worker: InfrastructureWorkerResponse


class WorkerLaunchRequest(BaseModel):
    kind: WorkerKind
    name: str = Field(min_length=1, max_length=255)
    host_port: int = Field(ge=1024, le=65535)

    @field_validator("name")
    @classmethod
    def normalize_launch_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name cannot be blank")
        return normalized


class WorkerLaunchResponse(BaseModel):
    worker: InfrastructureWorkerResponse


class WorkerStopResponse(BaseModel):
    status: str
    worker: InfrastructureWorkerResponse
