"""Add beacon task queue tables.

Revision ID: c2_0007_task_queue
Revises: c2_0006_beacon_ws
Create Date: 2026-06-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2_0007_task_queue"
down_revision = "c2_0006_beacon_ws"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("beacons", sa.Column("protocol_peer_public_key_b64", sa.String(length=64), nullable=True))
    op.create_table(
        "tasks",
        sa.Column("beacon_id", sa.Uuid(), nullable=False),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("args", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("priority", sa.String(length=16), server_default="normal", nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("running_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["beacon_id"], ["beacons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_beacon_id", "tasks", ["beacon_id"], unique=False)
    op.create_index("ix_tasks_module", "tasks", ["module"], unique=False)
    op.create_index("ix_tasks_priority", "tasks", ["priority"], unique=False)
    op.create_index("ix_tasks_queued_at", "tasks", ["queued_at"], unique=False)
    op.create_index("ix_tasks_status", "tasks", ["status"], unique=False)

    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("tasks", "status", server_default=None)
        op.alter_column("tasks", "priority", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_queued_at", table_name="tasks")
    op.drop_index("ix_tasks_priority", table_name="tasks")
    op.drop_index("ix_tasks_module", table_name="tasks")
    op.drop_index("ix_tasks_beacon_id", table_name="tasks")
    op.drop_table("tasks")
    op.drop_column("beacons", "protocol_peer_public_key_b64")
