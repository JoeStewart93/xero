"""Add interactive shell sessions.

Revision ID: c2_0012_interactive_sessions
Revises: c2_0011_task_results
Create Date: 2026-06-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2_0012_interactive_sessions"
down_revision = "c2_0011_task_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("beacon_id", sa.Uuid(), nullable=False),
        sa.Column("session_type", sa.String(length=32), nullable=False),
        sa.Column("shell_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("actor_subject", sa.String(length=255), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.String(length=128), nullable=True),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("cols", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["beacon_id"], ["beacons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_actor_subject", "sessions", ["actor_subject"], unique=False)
    op.create_index("ix_sessions_beacon_id", "sessions", ["beacon_id"], unique=False)
    op.create_index("ix_sessions_closed_at", "sessions", ["closed_at"], unique=False)
    op.create_index("ix_sessions_detached_at", "sessions", ["detached_at"], unique=False)
    op.create_index("ix_sessions_last_activity_at", "sessions", ["last_activity_at"], unique=False)
    op.create_index("ix_sessions_opened_at", "sessions", ["opened_at"], unique=False)
    op.create_index("ix_sessions_session_type", "sessions", ["session_type"], unique=False)
    op.create_index("ix_sessions_status", "sessions", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sessions_status", table_name="sessions")
    op.drop_index("ix_sessions_session_type", table_name="sessions")
    op.drop_index("ix_sessions_opened_at", table_name="sessions")
    op.drop_index("ix_sessions_last_activity_at", table_name="sessions")
    op.drop_index("ix_sessions_detached_at", table_name="sessions")
    op.drop_index("ix_sessions_closed_at", table_name="sessions")
    op.drop_index("ix_sessions_beacon_id", table_name="sessions")
    op.drop_index("ix_sessions_actor_subject", table_name="sessions")
    op.drop_table("sessions")
