"""Create beacons table for registration events.

Revision ID: c2_0001_beacons
Revises:
Create Date: 2026-06-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2_0001_beacons"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "beacons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("machine_fingerprint_hash", sa.String(length=128), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("os", sa.String(length=128), nullable=False),
        sa.Column("architecture", sa.String(length=64), nullable=False),
        sa.Column("internal_ip", sa.String(length=64), nullable=False),
        sa.Column("external_ip", sa.String(length=64), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="online", nullable=False),
        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "last_seen",
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("machine_fingerprint_hash", name="uq_beacons_machine_fingerprint_hash"),
    )
    op.create_index("ix_beacons_machine_fingerprint_hash", "beacons", ["machine_fingerprint_hash"], unique=False)
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("beacons", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_beacons_machine_fingerprint_hash", table_name="beacons")
    op.drop_table("beacons")
