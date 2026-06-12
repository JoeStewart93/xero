"""Add infrastructure worker registry.

Revision ID: c2_0004_workers
Revises: c2_0003_beacon_heartbeat
Create Date: 2026-06-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2_0004_workers"
down_revision = "c2_0003_beacon_heartbeat"
branch_labels = None
depends_on = None


def timestamp_column(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "infrastructure_workers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("endpoint", sa.String(length=512), nullable=True),
        sa.Column("capabilities", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("capacity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("current_load", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("worker_token_hash", sa.String(length=128), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("managed_project", sa.String(length=128), nullable=True),
        sa.Column("managed_service", sa.String(length=128), nullable=True),
        sa.Column("managed_compose_file", sa.String(length=255), nullable=True),
        sa.Column("managed_host_port", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.String(length=1024), nullable=True),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "origin", "name", name="uq_infrastructure_workers_identity"),
    )
    op.create_index("ix_infrastructure_workers_kind", "infrastructure_workers", ["kind"], unique=False)
    op.create_index("ix_infrastructure_workers_origin", "infrastructure_workers", ["origin"], unique=False)
    op.create_index("ix_infrastructure_workers_status", "infrastructure_workers", ["status"], unique=False)

    op.create_table(
        "worker_pairing_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.Uuid(), nullable=True),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.ForeignKeyConstraint(["worker_id"], ["infrastructure_workers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_worker_pairing_tokens_kind", "worker_pairing_tokens", ["kind"], unique=False)
    op.create_index("ix_worker_pairing_tokens_worker_id", "worker_pairing_tokens", ["worker_id"], unique=False)

    op.create_table(
        "worker_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("message", sa.String(length=1024), nullable=False),
        timestamp_column("occurred_at"),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.ForeignKeyConstraint(["worker_id"], ["infrastructure_workers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_worker_events_kind", "worker_events", ["kind"], unique=False)
    op.create_index("ix_worker_events_worker_id", "worker_events", ["worker_id"], unique=False)

    if op.get_bind().dialect.name != "sqlite":
        for table in ("infrastructure_workers", "worker_pairing_tokens", "worker_events"):
            op.alter_column(table, "created_at", server_default=None)
            op.alter_column(table, "updated_at", server_default=None)
        op.alter_column("worker_events", "occurred_at", server_default=None)
        op.alter_column("infrastructure_workers", "status", server_default=None)
        op.alter_column("infrastructure_workers", "capabilities", server_default=None)
        op.alter_column("infrastructure_workers", "capacity", server_default=None)
        op.alter_column("infrastructure_workers", "current_load", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_worker_events_worker_id", table_name="worker_events")
    op.drop_index("ix_worker_events_kind", table_name="worker_events")
    op.drop_table("worker_events")
    op.drop_index("ix_worker_pairing_tokens_worker_id", table_name="worker_pairing_tokens")
    op.drop_index("ix_worker_pairing_tokens_kind", table_name="worker_pairing_tokens")
    op.drop_table("worker_pairing_tokens")
    op.drop_index("ix_infrastructure_workers_status", table_name="infrastructure_workers")
    op.drop_index("ix_infrastructure_workers_origin", table_name="infrastructure_workers")
    op.drop_index("ix_infrastructure_workers_kind", table_name="infrastructure_workers")
    op.drop_table("infrastructure_workers")
