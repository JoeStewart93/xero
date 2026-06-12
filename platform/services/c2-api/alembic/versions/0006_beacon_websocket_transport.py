"""Add beacon WebSocket transport metadata.

Revision ID: c2_0006_beacon_ws
Revises: c2_0005_protocol
Create Date: 2026-06-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2_0006_beacon_ws"
down_revision = "c2_0005_protocol"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "beacons",
        sa.Column("transport_mode", sa.String(length=32), server_default="rest", nullable=False),
    )
    op.add_column(
        "beacons",
        sa.Column("transport_connected", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("beacons", sa.Column("transport_last_seen", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_beacons_transport_mode", "beacons", ["transport_mode"], unique=False)
    op.create_index("ix_beacons_transport_connected", "beacons", ["transport_connected"], unique=False)

    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("beacons", "transport_mode", server_default=None)
        op.alter_column("beacons", "transport_connected", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_beacons_transport_connected", table_name="beacons")
    op.drop_index("ix_beacons_transport_mode", table_name="beacons")
    op.drop_column("beacons", "transport_last_seen")
    op.drop_column("beacons", "transport_connected")
    op.drop_column("beacons", "transport_mode")
