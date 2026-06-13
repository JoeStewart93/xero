from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
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
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("traffic_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    applied_profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profile_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    removed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    removed_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    profile: Mapped[TrafficProfile | None] = relationship(foreign_keys=[profile_id])


class Asset(BaseModel):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("dedup_key", name="uq_assets_dedup_key"),)

    asset_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    dedup_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    primary_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    os: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    canonical_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    asset_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)


class AssetIdentifier(BaseModel):
    __tablename__ = "asset_identifiers"
    __table_args__ = (
        UniqueConstraint("asset_id", "kind", "normalized_value", name="uq_asset_identifiers_asset_kind_value"),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    asset: Mapped[Asset] = relationship(foreign_keys=[asset_id])


class AssetBeaconLink(BaseModel):
    __tablename__ = "asset_beacon_links"
    __table_args__ = (
        UniqueConstraint("beacon_id", name="uq_asset_beacon_links_beacon_id"),
        UniqueConstraint("machine_fingerprint_hash", name="uq_asset_beacon_links_fingerprint"),
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    beacon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("beacons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    machine_fingerprint_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    asset: Mapped[Asset] = relationship(foreign_keys=[asset_id])
    beacon: Mapped[Beacon] = relationship(foreign_keys=[beacon_id])


class AssetRelationship(BaseModel):
    __tablename__ = "asset_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_asset_id",
            "target_asset_id",
            "relationship_type",
            "scan_job_id",
            name="uq_asset_relationships_scan_relationship",
        ),
    )

    source_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scan_job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("scan_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    relationship_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    source_asset: Mapped[Asset] = relationship(foreign_keys=[source_asset_id])
    target_asset: Mapped[Asset] = relationship(foreign_keys=[target_asset_id])


class AssetObservation(BaseModel):
    __tablename__ = "asset_observations"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    observation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    scan_job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("scan_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scan_result_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("scan_result_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    beacon_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("beacons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    asset: Mapped[Asset] = relationship(foreign_keys=[asset_id])


class AssetGroupingRule(BaseModel):
    __tablename__ = "asset_grouping_rules"
    __table_args__ = (UniqueConstraint("rule_key", name="uq_asset_grouping_rules_rule_key"),)

    rule_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AssetGroup(BaseModel):
    __tablename__ = "asset_groups"
    __table_args__ = (UniqueConstraint("group_key", name="uq_asset_groups_group_key"),)

    group_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    group_type: Mapped[str] = mapped_column("type", String(32), default="auto", nullable=False, index=True)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("asset_grouping_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    criterion_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    criterion_value: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("asset_groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    group_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    rule: Mapped[AssetGroupingRule | None] = relationship(foreign_keys=[rule_id])
    parent: Mapped[AssetGroup | None] = relationship(remote_side="AssetGroup.id", foreign_keys=[parent_id])


class AssetGroupMembership(BaseModel):
    __tablename__ = "asset_group_memberships"
    __table_args__ = (UniqueConstraint("asset_id", "group_id", name="uq_asset_group_memberships_asset_group"),)

    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("asset_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(32), default="auto", nullable=False, index=True)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("asset_grouping_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    membership_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    asset: Mapped[Asset] = relationship(foreign_keys=[asset_id])
    group: Mapped[AssetGroup] = relationship(foreign_keys=[group_id])
    rule: Mapped[AssetGroupingRule | None] = relationship(foreign_keys=[rule_id])


class AssetGroupingEvent(BaseModel):
    __tablename__ = "asset_grouping_events"

    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("asset_groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("asset_grouping_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    asset: Mapped[Asset | None] = relationship(foreign_keys=[asset_id])
    group: Mapped[AssetGroup | None] = relationship(foreign_keys=[group_id])
    rule: Mapped[AssetGroupingRule | None] = relationship(foreign_keys=[rule_id])


class TrafficProfile(BaseModel):
    __tablename__ = "traffic_profiles"
    __table_args__ = (UniqueConstraint("name", name="uq_traffic_profiles_name"),)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    template: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)


class TrafficProfileVersion(BaseModel):
    __tablename__ = "traffic_profile_versions"
    __table_args__ = (UniqueConstraint("profile_id", "version", name="uq_traffic_profile_versions_profile_version"),)

    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("traffic_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    profile: Mapped[TrafficProfile] = relationship(foreign_keys=[profile_id])


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


class InteractiveSession(BaseModel):
    __tablename__ = "sessions"

    beacon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("beacons.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    session_type: Mapped[str] = mapped_column(String(32), default="shell", nullable=False, index=True)
    shell_type: Mapped[str] = mapped_column(String(32), default="auto", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="opening", nullable=False, index=True)
    actor_subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    detached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    close_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rows: Mapped[int] = mapped_column(Integer, default=32, nullable=False)
    cols: Mapped[int] = mapped_column(Integer, default=120, nullable=False)


class RegistryConfirmation(BaseModel):
    __tablename__ = "registry_confirmations"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_registry_confirmations_token_hash"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    beacon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("beacons.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    actor_subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    hive: Mapped[str] = mapped_column(String(8), nullable=False)
    key_path: Mapped[str] = mapped_column(String(512), nullable=False)
    value_name: Mapped[str] = mapped_column(String(255), nullable=False)
    value_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    value_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    value_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class RegistryAuditEvent(BaseModel):
    __tablename__ = "registry_audit_events"

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    beacon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("beacons.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    actor_subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    hive: Mapped[str] = mapped_column(String(8), nullable=False)
    key_path: Mapped[str] = mapped_column(String(512), nullable=False)
    value_name: Mapped[str] = mapped_column(String(255), nullable=False)
    value_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    value_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    value_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)


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


class TaskAuditEvent(BaseModel):
    __tablename__ = "task_audit_events"

    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    beacon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("beacons.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    module: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    command: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    actor_subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    task_status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)


class TaskResult(BaseModel):
    __tablename__ = "task_results"
    __table_args__ = (UniqueConstraint("task_id", name="uq_task_results_task_id"),)

    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    beacon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("beacons.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    timed_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stdout_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    stdout_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stderr_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stdout_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stderr_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    result_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class ResultChunk(BaseModel):
    __tablename__ = "result_chunks"
    __table_args__ = (
        UniqueConstraint("task_result_id", "stream", "upload_id", "sequence", name="uq_result_chunks_sequence"),
    )

    task_result_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("task_results.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    beacon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("beacons.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    upload_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    stream: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    stream_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stream_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)


class TaskResultArtifact(BaseModel):
    __tablename__ = "task_result_artifacts"
    __table_args__ = (UniqueConstraint("task_result_id", "artifact_id", "role", name="uq_task_result_artifacts_role"),)

    task_result_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("task_results.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    artifact: Mapped[Artifact] = relationship(foreign_keys=[artifact_id])


class FileTransfer(BaseModel):
    __tablename__ = "file_transfers"

    beacon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("beacons.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    actor_subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    remote_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    chunk_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    staged_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    acked_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overwrite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    transfer_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    artifact: Mapped[Artifact | None] = relationship(foreign_keys=[artifact_id])


class FileTransferChunk(BaseModel):
    __tablename__ = "file_transfer_chunks"
    __table_args__ = (UniqueConstraint("transfer_id", "sequence", name="uq_file_transfer_chunks_sequence"),)

    transfer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("file_transfers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    staged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class ScanJob(BaseModel):
    __tablename__ = "scan_jobs"

    module: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    args: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    actor_subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    execution_target_requested: Mapped[str] = mapped_column(String(64), default="auto", nullable=False)
    execution_target_resolved: Mapped[str] = mapped_column(String(64), default="embedded-c2", nullable=False)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("infrastructure_workers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    progress_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    state_counts: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    results: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    worker: Mapped[InfrastructureWorker | None] = relationship(foreign_keys=[worker_id])


class ScanResultChunk(BaseModel):
    __tablename__ = "scan_result_chunks"
    __table_args__ = (UniqueConstraint("scan_job_id", "sequence", name="uq_scan_result_chunks_sequence"),)

    scan_job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("scan_jobs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    probes_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    probes_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    emitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    scan_job: Mapped[ScanJob] = relationship(foreign_keys=[scan_job_id])


class Artifact(BaseModel):
    __tablename__ = "artifacts"

    namespace: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    owner_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), default="application/octet-stream", nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)


class BeaconBuild(BaseModel):
    __tablename__ = "beacon_builds"

    target_os: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_arch: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    profile_name: Mapped[str] = mapped_column(String(128), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    artifact: Mapped[Artifact | None] = relationship(foreign_keys=[artifact_id])
    artifact_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    artifact_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    artifact_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    logs_tail: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
