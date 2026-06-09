"""Add opaque beacon token material.

Revision ID: 0006_add_beacon_token_material
Revises: 0005_create_beacons
Create Date: 2026-06-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_add_beacon_token_material"
down_revision = "0005_create_beacons"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "beacons",
        sa.Column(
            "beacon_token_hash",
            sa.String(length=128),
            server_default="sha256:migrated-token-unavailable",
            nullable=False,
        ),
    )
    op.add_column(
        "beacons",
        sa.Column(
            "beacon_token_issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("beacons", "beacon_token_hash", server_default=None)
        op.alter_column("beacons", "beacon_token_issued_at", server_default=None)


def downgrade() -> None:
    op.drop_column("beacons", "beacon_token_issued_at")
    op.drop_column("beacons", "beacon_token_hash")
