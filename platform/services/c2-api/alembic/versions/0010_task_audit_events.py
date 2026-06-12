"""Add task audit events.

Revision ID: c2_0010_task_audit_events
Revises: c2_0009_artifact_storage
Create Date: 2026-06-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2_0010_task_audit_events"
down_revision = "c2_0009_artifact_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_audit_events",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("beacon_id", sa.Uuid(), nullable=False),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("command", sa.String(length=4096), nullable=True),
        sa.Column("actor_subject", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("task_status", sa.String(length=32), nullable=True),
        sa.Column("message", sa.String(length=512), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["beacon_id"], ["beacons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_audit_events_actor_subject", "task_audit_events", ["actor_subject"], unique=False)
    op.create_index("ix_task_audit_events_beacon_id", "task_audit_events", ["beacon_id"], unique=False)
    op.create_index("ix_task_audit_events_event_type", "task_audit_events", ["event_type"], unique=False)
    op.create_index("ix_task_audit_events_module", "task_audit_events", ["module"], unique=False)
    op.create_index("ix_task_audit_events_occurred_at", "task_audit_events", ["occurred_at"], unique=False)
    op.create_index("ix_task_audit_events_task_id", "task_audit_events", ["task_id"], unique=False)
    op.create_index("ix_task_audit_events_task_status", "task_audit_events", ["task_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_audit_events_task_status", table_name="task_audit_events")
    op.drop_index("ix_task_audit_events_task_id", table_name="task_audit_events")
    op.drop_index("ix_task_audit_events_occurred_at", table_name="task_audit_events")
    op.drop_index("ix_task_audit_events_module", table_name="task_audit_events")
    op.drop_index("ix_task_audit_events_event_type", table_name="task_audit_events")
    op.drop_index("ix_task_audit_events_beacon_id", table_name="task_audit_events")
    op.drop_index("ix_task_audit_events_actor_subject", table_name="task_audit_events")
    op.drop_table("task_audit_events")
