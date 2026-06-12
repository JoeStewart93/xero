"""Add protocol metadata and observability tables.

Revision ID: c2_0005_protocol
Revises: c2_0004_workers
Create Date: 2026-06-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2_0005_protocol"
down_revision = "c2_0004_workers"
branch_labels = None
depends_on = None


def timestamp_column(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)


def upgrade() -> None:
    op.add_column("beacons", sa.Column("protocol_version", sa.Integer(), nullable=True))
    op.add_column("beacons", sa.Column("protocol_session_id", sa.String(length=64), nullable=True))
    op.add_column("beacons", sa.Column("protocol_last_seen", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_beacons_protocol_session_id", "beacons", ["protocol_session_id"], unique=False)

    op.create_table(
        "protocol_security_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("beacon_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("message", sa.String(length=512), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("nonce", sa.String(length=24), nullable=True),
        timestamp_column("occurred_at"),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.ForeignKeyConstraint(["beacon_id"], ["beacons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_protocol_security_events_beacon_id", "protocol_security_events", ["beacon_id"], unique=False)
    op.create_index("ix_protocol_security_events_event_type", "protocol_security_events", ["event_type"], unique=False)
    op.create_index("ix_protocol_security_events_severity", "protocol_security_events", ["severity"], unique=False)
    op.create_index("ix_protocol_security_events_session_id", "protocol_security_events", ["session_id"], unique=False)

    op.create_table(
        "protocol_frame_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("beacon_id", sa.Uuid(), nullable=True),
        sa.Column("message_type", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("nonce", sa.String(length=24), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("payload_size", sa.Integer(), nullable=False),
        timestamp_column("occurred_at"),
        timestamp_column("created_at"),
        timestamp_column("updated_at"),
        sa.ForeignKeyConstraint(["beacon_id"], ["beacons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "nonce", name="uq_protocol_frame_receipts_session_nonce"),
    )
    op.create_index("ix_protocol_frame_receipts_beacon_id", "protocol_frame_receipts", ["beacon_id"], unique=False)
    op.create_index(
        "ix_protocol_frame_receipts_message_type",
        "protocol_frame_receipts",
        ["message_type"],
        unique=False,
    )
    op.create_index("ix_protocol_frame_receipts_session_id", "protocol_frame_receipts", ["session_id"], unique=False)

    if op.get_bind().dialect.name != "sqlite":
        for table in ("protocol_security_events", "protocol_frame_receipts"):
            op.alter_column(table, "occurred_at", server_default=None)
            op.alter_column(table, "created_at", server_default=None)
            op.alter_column(table, "updated_at", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_protocol_frame_receipts_session_id", table_name="protocol_frame_receipts")
    op.drop_index("ix_protocol_frame_receipts_message_type", table_name="protocol_frame_receipts")
    op.drop_index("ix_protocol_frame_receipts_beacon_id", table_name="protocol_frame_receipts")
    op.drop_table("protocol_frame_receipts")
    op.drop_index("ix_protocol_security_events_session_id", table_name="protocol_security_events")
    op.drop_index("ix_protocol_security_events_severity", table_name="protocol_security_events")
    op.drop_index("ix_protocol_security_events_event_type", table_name="protocol_security_events")
    op.drop_index("ix_protocol_security_events_beacon_id", table_name="protocol_security_events")
    op.drop_table("protocol_security_events")
    op.drop_index("ix_beacons_protocol_session_id", table_name="beacons")
    op.drop_column("beacons", "protocol_last_seen")
    op.drop_column("beacons", "protocol_session_id")
    op.drop_column("beacons", "protocol_version")
