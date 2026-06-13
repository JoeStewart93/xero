"""Add registry session confirmation and audit tables.

Revision ID: c2_0013_registry_sessions
Revises: c2_0012_interactive_sessions
Create Date: 2026-06-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2_0013_registry_sessions"
down_revision = "c2_0012_interactive_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "registry_confirmations",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("beacon_id", sa.Uuid(), nullable=False),
        sa.Column("actor_subject", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("hive", sa.String(length=8), nullable=False),
        sa.Column("key_path", sa.String(length=512), nullable=False),
        sa.Column("value_name", sa.String(length=255), nullable=False),
        sa.Column("value_type", sa.String(length=32), nullable=True),
        sa.Column("value_digest", sa.String(length=64), nullable=True),
        sa.Column("value_length", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["beacon_id"], ["beacons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_registry_confirmations_token_hash"),
    )
    op.create_index("ix_registry_confirmations_actor_subject", "registry_confirmations", ["actor_subject"])
    op.create_index("ix_registry_confirmations_beacon_id", "registry_confirmations", ["beacon_id"])
    op.create_index("ix_registry_confirmations_expires_at", "registry_confirmations", ["expires_at"])
    op.create_index("ix_registry_confirmations_operation", "registry_confirmations", ["operation"])
    op.create_index("ix_registry_confirmations_session_id", "registry_confirmations", ["session_id"])
    op.create_index("ix_registry_confirmations_token_hash", "registry_confirmations", ["token_hash"])
    op.create_index("ix_registry_confirmations_used_at", "registry_confirmations", ["used_at"])

    op.create_table(
        "registry_audit_events",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("beacon_id", sa.Uuid(), nullable=False),
        sa.Column("actor_subject", sa.String(length=255), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("hive", sa.String(length=8), nullable=False),
        sa.Column("key_path", sa.String(length=512), nullable=False),
        sa.Column("value_name", sa.String(length=255), nullable=False),
        sa.Column("value_type", sa.String(length=32), nullable=True),
        sa.Column("value_digest", sa.String(length=64), nullable=True),
        sa.Column("value_length", sa.Integer(), nullable=True),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("message", sa.String(length=512), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["beacon_id"], ["beacons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_registry_audit_events_actor_subject", "registry_audit_events", ["actor_subject"])
    op.create_index("ix_registry_audit_events_beacon_id", "registry_audit_events", ["beacon_id"])
    op.create_index("ix_registry_audit_events_occurred_at", "registry_audit_events", ["occurred_at"])
    op.create_index("ix_registry_audit_events_operation", "registry_audit_events", ["operation"])
    op.create_index("ix_registry_audit_events_result", "registry_audit_events", ["result"])
    op.create_index("ix_registry_audit_events_session_id", "registry_audit_events", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_registry_audit_events_session_id", table_name="registry_audit_events")
    op.drop_index("ix_registry_audit_events_result", table_name="registry_audit_events")
    op.drop_index("ix_registry_audit_events_operation", table_name="registry_audit_events")
    op.drop_index("ix_registry_audit_events_occurred_at", table_name="registry_audit_events")
    op.drop_index("ix_registry_audit_events_beacon_id", table_name="registry_audit_events")
    op.drop_index("ix_registry_audit_events_actor_subject", table_name="registry_audit_events")
    op.drop_table("registry_audit_events")

    op.drop_index("ix_registry_confirmations_used_at", table_name="registry_confirmations")
    op.drop_index("ix_registry_confirmations_token_hash", table_name="registry_confirmations")
    op.drop_index("ix_registry_confirmations_session_id", table_name="registry_confirmations")
    op.drop_index("ix_registry_confirmations_operation", table_name="registry_confirmations")
    op.drop_index("ix_registry_confirmations_expires_at", table_name="registry_confirmations")
    op.drop_index("ix_registry_confirmations_beacon_id", table_name="registry_confirmations")
    op.drop_index("ix_registry_confirmations_actor_subject", table_name="registry_confirmations")
    op.drop_table("registry_confirmations")
