"""Add beacon soft removal fields.

Revision ID: c2_0016_beacon_soft_removal
Revises: c2_0015_scan_jobs
Create Date: 2026-06-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c2_0016_beacon_soft_removal"
down_revision = "c2_0015_scan_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("beacons", sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("beacons", sa.Column("removed_by", sa.String(length=255), nullable=True))
    op.add_column("beacons", sa.Column("removed_reason", sa.String(length=255), nullable=True))
    op.create_index("ix_beacons_removed_at", "beacons", ["removed_at"])


def downgrade() -> None:
    op.drop_index("ix_beacons_removed_at", table_name="beacons")
    op.drop_column("beacons", "removed_reason")
    op.drop_column("beacons", "removed_by")
    op.drop_column("beacons", "removed_at")
