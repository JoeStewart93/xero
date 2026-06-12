"""Add beacon build metadata.

Revision ID: c2_0008_beacon_builds
Revises: c2_0007_task_queue
Create Date: 2026-06-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2_0008_beacon_builds"
down_revision = "c2_0007_task_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "beacon_builds",
        sa.Column("target_os", sa.String(length=32), nullable=False),
        sa.Column("target_arch", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("profile_name", sa.String(length=128), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("artifact_path", sa.String(length=1024), nullable=True),
        sa.Column("artifact_filename", sa.String(length=255), nullable=True),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=True),
        sa.Column("artifact_size", sa.Integer(), nullable=True),
        sa.Column("logs_tail", sa.String(length=4096), nullable=True),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_beacon_builds_status", "beacon_builds", ["status"], unique=False)
    op.create_index("ix_beacon_builds_target_arch", "beacon_builds", ["target_arch"], unique=False)
    op.create_index("ix_beacon_builds_target_os", "beacon_builds", ["target_os"], unique=False)
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("beacon_builds", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_beacon_builds_target_os", table_name="beacon_builds")
    op.drop_index("ix_beacon_builds_target_arch", table_name="beacon_builds")
    op.drop_index("ix_beacon_builds_status", table_name="beacon_builds")
    op.drop_table("beacon_builds")
