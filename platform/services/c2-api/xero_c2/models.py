from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from xero_common.models import IdMixin, TimestampMixin, utc_now


class Base(DeclarativeBase):
    pass


class BaseModel(IdMixin, TimestampMixin, Base):
    __abstract__ = True


class Beacon(BaseModel):
    __tablename__ = "beacons"
    __table_args__ = (UniqueConstraint("machine_fingerprint_hash", name="uq_beacons_machine_fingerprint_hash"),)

    machine_fingerprint_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    os: Mapped[str] = mapped_column(String(128), nullable=False)
    architecture: Mapped[str] = mapped_column(String(64), nullable=False)
    internal_ip: Mapped[str] = mapped_column(String(64), nullable=False)
    external_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pid: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="online", nullable=False)
    sleep_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    jitter: Mapped[float] = mapped_column(Float, default=0.1, nullable=False)
    beacon_token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    beacon_token_issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    protocol_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protocol_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    protocol_peer_public_key_b64: Mapped[str | None] = mapped_column(String(64), nullable=True)
    protocol_last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transport_mode: Mapped[str] = mapped_column(String(32), default="rest", nullable=False, index=True)
    transport_connected: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    transport_last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class BeaconEvent(BaseModel):
    __tablename__ = "beacon_events"

    beacon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("beacons.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    old_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class InfrastructureWorker(BaseModel):
    __tablename__ = "infrastructure_workers"
    __table_args__ = (UniqueConstraint("kind", "origin", "name", name="uq_infrastructure_workers_identity"),)

    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    current_load: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    worker_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    managed_project: Mapped[str | None] = mapped_column(String(128), nullable=True)
    managed_service: Mapped[str | None] = mapped_column(String(128), nullable=True)
    managed_compose_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    managed_host_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class WorkerPairingToken(BaseModel):
    __tablename__ = "worker_pairing_tokens"

    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("infrastructure_workers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


class WorkerEvent(BaseModel):
    __tablename__ = "worker_events"

    worker_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("infrastructure_workers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(String(1024), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ProtocolSecurityEvent(BaseModel):
    __tablename__ = "protocol_security_events"

    beacon_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("beacons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    nonce: Mapped[str | None] = mapped_column(String(24), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ProtocolFrameReceipt(BaseModel):
    __tablename__ = "protocol_frame_receipts"
    __table_args__ = (UniqueConstraint("session_id", "nonce", name="uq_protocol_frame_receipts_session_nonce"),)

    beacon_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("beacons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    message_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    nonce: Mapped[str] = mapped_column(String(24), nullable=False)
    payload_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_size: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Task(BaseModel):
    __tablename__ = "tasks"

    beacon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("beacons.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    module: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    args: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(16), default="normal", nullable=False, index=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    running_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
