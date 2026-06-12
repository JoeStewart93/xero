"""Add beacon heartbeat profile fields and status events.

Revision ID: c2_0003_beacon_heartbeat
Revises: c2_0002_beacon_token
Create Date: 2026-06-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2_0003_beacon_heartbeat"
down_revision = "c2_0002_beacon_token"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "beacons",
        sa.Column("sleep_seconds", sa.Integer(), server_default="30", nullable=False),
    )
    op.add_column(
        "beacons",
        sa.Column("jitter", sa.Float(), server_default="0.1", nullable=False),
    )
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("beacons", "sleep_seconds", server_default=None)
        op.alter_column("beacons", "jitter", server_default=None)

    op.create_table(
        "beacon_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("beacon_id", sa.Uuid(), nullable=False),
        sa.Column("old_status", sa.String(length=32), nullable=False),
        sa.Column("new_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=128), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["beacon_id"], ["beacons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_beacon_events_beacon_id", "beacon_events", ["beacon_id"], unique=False)
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("beacon_events", "occurred_at", server_default=None)
        op.alter_column("beacon_events", "created_at", server_default=None)
        op.alter_column("beacon_events", "updated_at", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_beacon_events_beacon_id", table_name="beacon_events")
    op.drop_table("beacon_events")
    op.drop_column("beacons", "jitter")
    op.drop_column("beacons", "sleep_seconds")
