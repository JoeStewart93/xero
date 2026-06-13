from __future__ import annotations

import ipaddress
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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
    profile_id: str | None = None
    profile_name: str | None = None
    profile_template: str | None = None
    profile_version: int | None = None
    applied_profile_version: int | None = None
    profile_applied_at: datetime | None = None
    sleep_seconds: int = 30
    jitter: float = 0.1
    protocol_version: int | None = None
    transport_mode: Literal["long-poll", "rest", "websocket"] = "rest"
    transport_connected: bool = False
    transport_last_seen: datetime | None = None
    removed_at: datetime | None = None
    removed_by: str | None = None
    removed_reason: str | None = None
    first_seen: datetime
    last_seen: datetime


class BeaconListResponse(BaseModel):
    items: list[BeaconResponse] = Field(default_factory=list)


class BeaconKillResponse(BaseModel):
    beacon: BeaconResponse
    cancelled_tasks: int = 0
    closed_sessions: int = 0
    status: Literal["already_removed", "removed"]


class BeaconActivityItemResponse(BaseModel):
    id: str
    type: str
    label: str
    occurred_at: datetime
    beacon_id: str
    task_id: str | None = None
    session_id: str | None = None
    status: str | None = None
    detail: str | None = None


class BeaconActivityListResponse(BaseModel):
    items: list[BeaconActivityItemResponse] = Field(default_factory=list)


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
    profile: dict | None = None
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
    profile: dict | None = None
    beacon: BeaconResponse


class TrafficProfileConfig(BaseModel):
    headers: dict[str, str] = Field(default_factory=dict)
    jitter: float = Field(default=0.1, ge=0, le=1)
    padding: dict = Field(default_factory=dict)
    paths: dict[str, str] = Field(default_factory=dict)
    sleep_seconds: int = Field(default=30, ge=1, le=86400)
    user_agent: str = Field(default="xero-go-beacon/0.1", min_length=1, max_length=255)


class TrafficProfileCreateRequest(BaseModel):
    config: dict
    description: str | None = Field(default=None, max_length=512)
    name: str = Field(min_length=1, max_length=128)
    template: str = Field(default="custom", min_length=1, max_length=64)


class TrafficProfileUpdateRequest(BaseModel):
    config: dict
    description: str | None = Field(default=None, max_length=512)
    name: str = Field(min_length=1, max_length=128)


class TrafficProfileCloneRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)


class TrafficProfileRollbackRequest(BaseModel):
    version: int = Field(ge=1)


class TrafficProfileAssignRequest(BaseModel):
    profile_id: str | None = None


class TrafficProfileResponse(BaseModel):
    id: str
    name: str
    template: str
    description: str | None = None
    current_version: int
    is_template: bool
    is_archived: bool
    config: dict
    created_at: datetime
    updated_at: datetime


class TrafficProfileListResponse(BaseModel):
    items: list[TrafficProfileResponse] = Field(default_factory=list)


class TrafficProfileVersionResponse(BaseModel):
    id: str
    profile_id: str
    version: int
    config: dict
    created_by: str
    created_at: datetime


class TrafficProfileVersionListResponse(BaseModel):
    items: list[TrafficProfileVersionResponse] = Field(default_factory=list)


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


class DashboardBeaconCountsResponse(BaseModel):
    total: int
    online: int
    offline: int


class DashboardActivityItemResponse(BaseModel):
    id: str
    type: str
    label: str
    occurred_at: datetime
    beacon_id: str | None = None
    task_id: str | None = None
    status: str | None = None
    detail: str | None = None


class DashboardHealthCheckResponse(BaseModel):
    status: str
    error: str | None = None


class DashboardHealthResponse(BaseModel):
    status: Literal["ready", "degraded"]
    checks: dict[str, DashboardHealthCheckResponse] = Field(default_factory=dict)


TaskPriority = Literal["high", "low", "normal", "urgent"]
TaskStatus = Literal["cancelled", "completed", "dispatched", "failed", "queued", "running"]
ScanJobStatus = Literal["completed", "failed", "queued", "running"]
ShellType = Literal["auto", "bash", "cmd", "powershell"]
SessionStatus = Literal["closed", "closing", "detached", "failed", "open", "opening"]
SessionType = Literal["file_browser", "registry", "shell"]
ShellSessionStatus = SessionStatus
BeaconBuildStatus = Literal["building", "failed", "queued", "succeeded"]
BeaconBuildTargetOS = Literal["linux", "windows"]
BeaconBuildTargetArch = Literal["amd64"]
BeaconBuildConfigMode = Literal["all", "env", "file", "ldflags"]


class ShellTaskArgs(BaseModel):
    command: str = Field(min_length=1, max_length=4096)
    shell_type: ShellType = "auto"
    timeout_seconds: int | None = Field(default=None, ge=1)

    @field_validator("command")
    @classmethod
    def normalize_command(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Command cannot be blank")
        return normalized


class TaskCreateRequest(BaseModel):
    beacon_id: str
    module: Literal["shell"] = "shell"
    args: dict = Field(default_factory=dict)
    priority: TaskPriority = "normal"

    @model_validator(mode="after")
    def validate_args(self) -> TaskCreateRequest:
        if self.module == "shell":
            self.args = ShellTaskArgs.model_validate(self.args).model_dump(exclude_none=True)
        return self


class TaskResponse(BaseModel):
    id: str
    beacon_id: str
    module: str
    args: dict
    status: TaskStatus
    priority: TaskPriority
    queued_at: datetime
    dispatched_at: datetime | None = None
    running_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    items: list[TaskResponse] = Field(default_factory=list)


class DashboardSummaryResponse(BaseModel):
    generated_at: datetime
    beacons: DashboardBeaconCountsResponse
    recent_tasks: list[TaskResponse] = Field(default_factory=list)
    recent_activity: list[DashboardActivityItemResponse] = Field(default_factory=list)
    c2_health: DashboardHealthResponse


class TaskAuditEventResponse(BaseModel):
    id: str
    task_id: str
    beacon_id: str
    module: str
    command: str | None = None
    actor_subject: str
    event_type: str
    task_status: TaskStatus | None = None
    message: str | None = None
    metadata: dict = Field(default_factory=dict)
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime


class TaskAuditEventListResponse(BaseModel):
    items: list[TaskAuditEventResponse] = Field(default_factory=list)


TaskResultStatus = Literal["completed", "failed"]


class TaskResultArtifactResponse(BaseModel):
    id: str
    role: Literal["binary", "combined", "stderr", "stdout"]
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    available: bool | None = None


class TaskResultResponse(BaseModel):
    id: str
    task_id: str
    beacon_id: str
    status: TaskResultStatus
    exit_code: int | None = None
    error_message: str | None = None
    timed_out: bool = False
    truncated: bool = False
    stdout: str | None = None
    stderr: str | None = None
    stdout_size_bytes: int
    stderr_size_bytes: int
    output_size_bytes: int
    stdout_sha256: str | None = None
    stderr_sha256: str | None = None
    output_sha256: str | None = None
    metadata: dict = Field(default_factory=dict)
    artifacts: list[TaskResultArtifactResponse] = Field(default_factory=list)
    completed_at: datetime | None = None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class TaskResultListResponse(BaseModel):
    items: list[TaskResultResponse] = Field(default_factory=list)
    next_cursor: datetime | None = None


class TaskResultChunkResponse(BaseModel):
    id: str
    task_result_id: str
    task_id: str
    beacon_id: str
    upload_id: str
    stream: Literal["stderr", "stdout"]
    sequence: int
    total_chunks: int
    chunk: str
    chunk_sha256: str
    stream_sha256: str | None = None
    stream_size_bytes: int | None = None
    received_at: datetime
    created_at: datetime


class TaskResultChunkListResponse(BaseModel):
    items: list[TaskResultChunkResponse] = Field(default_factory=list)


class ModuleDefinitionResponse(BaseModel):
    id: str
    name: str
    category: str
    description: str
    source: str
    version: str
    execution_kind: str
    supported_execution_targets: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    args_schema: dict = Field(default_factory=dict)
    result_schema: dict = Field(default_factory=dict)
    example: dict = Field(default_factory=dict)


class ModuleListResponse(BaseModel):
    items: list[ModuleDefinitionResponse] = Field(default_factory=list)


class ScanJobCreateRequest(BaseModel):
    module: str = Field(min_length=1, max_length=64)
    args: dict = Field(default_factory=dict)


class ScanJobResponse(BaseModel):
    id: str
    module: str
    args: dict
    status: ScanJobStatus
    actor_subject: str
    execution_target_requested: str
    execution_target_resolved: str
    worker_id: str | None = None
    progress_completed: int
    progress_total: int
    state_counts: dict = Field(default_factory=dict)
    summary: dict = Field(default_factory=dict)
    results: list[dict] = Field(default_factory=list)
    error_message: str | None = None
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ScanJobListResponse(BaseModel):
    items: list[ScanJobResponse] = Field(default_factory=list)


class ScanResultChunkResponse(BaseModel):
    id: str
    scan_job_id: str
    sequence: int
    kind: Literal["progress", "summary"]
    payload: dict = Field(default_factory=dict)
    probes_completed: int
    probes_total: int
    emitted_at: datetime
    created_at: datetime


class ScanResultChunkListResponse(BaseModel):
    items: list[ScanResultChunkResponse] = Field(default_factory=list)


class ShellSessionCreateRequest(BaseModel):
    beacon_id: str
    shell_type: ShellType = "auto"
    rows: int = Field(default=32, ge=5, le=80)
    cols: int = Field(default=120, ge=20, le=300)


class FileBrowserSessionCreateRequest(BaseModel):
    beacon_id: str
    root_path: str | None = Field(default=None, max_length=1024)

    @field_validator("root_path")
    @classmethod
    def normalize_root_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class RegistrySessionCreateRequest(BaseModel):
    beacon_id: str


class SessionResponse(BaseModel):
    id: str
    beacon_id: str
    session_type: SessionType
    shell_type: ShellType | str | None = None
    status: SessionStatus
    actor_subject: str
    opened_at: datetime
    last_activity_at: datetime
    detached_at: datetime | None = None
    closed_at: datetime | None = None
    close_reason: str | None = None
    rows: int | None = None
    cols: int | None = None
    created_at: datetime
    updated_at: datetime


class ShellSessionResponse(BaseModel):
    id: str
    beacon_id: str
    session_type: Literal["shell"]
    shell_type: ShellType
    status: ShellSessionStatus
    actor_subject: str
    opened_at: datetime
    last_activity_at: datetime
    detached_at: datetime | None = None
    closed_at: datetime | None = None
    close_reason: str | None = None
    rows: int
    cols: int
    created_at: datetime
    updated_at: datetime


class FileBrowserSessionResponse(BaseModel):
    id: str
    beacon_id: str
    session_type: Literal["file_browser"]
    status: SessionStatus
    actor_subject: str
    opened_at: datetime
    last_activity_at: datetime
    detached_at: datetime | None = None
    closed_at: datetime | None = None
    close_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class RegistrySessionResponse(BaseModel):
    id: str
    beacon_id: str
    session_type: Literal["registry"]
    status: SessionStatus
    actor_subject: str
    opened_at: datetime
    last_activity_at: datetime
    detached_at: datetime | None = None
    closed_at: datetime | None = None
    close_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class BeaconBuildTargetResponse(BaseModel):
    os: BeaconBuildTargetOS
    arch: BeaconBuildTargetArch
    extension: str
    label: str


class BeaconBuildTargetListResponse(BaseModel):
    items: list[BeaconBuildTargetResponse] = Field(default_factory=list)


class BeaconBuildCreateRequest(BaseModel):
    target_os: BeaconBuildTargetOS = "linux"
    target_arch: BeaconBuildTargetArch = "amd64"
    c2_url: str = Field(min_length=8, max_length=512)
    profile_name: str = Field(default="default", min_length=1, max_length=128)
    sleep_seconds: int = Field(default=30, ge=1, le=86400)
    jitter: float = Field(default=0.1, ge=0, le=1)
    user_agent: str | None = Field(default=None, max_length=255)
    config_mode: BeaconBuildConfigMode = "all"
    fallback_longpoll_enabled: bool = True
    output_limit_bytes: int = Field(default=65536, ge=1024, le=1_048_576)
    output_name: str | None = Field(default=None, max_length=128)

    @field_validator("c2_url")
    @classmethod
    def normalize_c2_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("c2_url must start with http:// or https://")
        return normalized

    @field_validator("profile_name", "output_name", mode="after")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name cannot be blank")
        return normalized


class BeaconBuildResponse(BaseModel):
    id: str
    target_os: BeaconBuildTargetOS
    target_arch: BeaconBuildTargetArch
    status: BeaconBuildStatus
    profile_name: str
    config: dict
    artifact_filename: str | None = None
    artifact_sha256: str | None = None
    artifact_size: int | None = None
    artifact_available: bool = False
    logs_tail: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class BeaconBuildListResponse(BaseModel):
    items: list[BeaconBuildResponse] = Field(default_factory=list)


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
