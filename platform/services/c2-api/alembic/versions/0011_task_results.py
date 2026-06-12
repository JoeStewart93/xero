"""Add task result storage.

Revision ID: c2_0011_task_results
Revises: c2_0010_task_audit_events
Create Date: 2026-06-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2_0011_task_results"
down_revision = "c2_0010_task_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_results",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("beacon_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("timed_out", sa.Boolean(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column("stdout_text", sa.Text(), nullable=True),
        sa.Column("stderr_text", sa.Text(), nullable=True),
        sa.Column("stdout_size_bytes", sa.Integer(), nullable=False),
        sa.Column("stderr_size_bytes", sa.Integer(), nullable=False),
        sa.Column("output_size_bytes", sa.Integer(), nullable=False),
        sa.Column("stdout_sha256", sa.String(length=64), nullable=True),
        sa.Column("stderr_sha256", sa.String(length=64), nullable=True),
        sa.Column("output_sha256", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["beacon_id"], ["beacons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_task_results_task_id"),
    )
    op.create_index("ix_task_results_beacon_id", "task_results", ["beacon_id"], unique=False)
    op.create_index("ix_task_results_completed_at", "task_results", ["completed_at"], unique=False)
    op.create_index("ix_task_results_expires_at", "task_results", ["expires_at"], unique=False)
    op.create_index("ix_task_results_output_sha256", "task_results", ["output_sha256"], unique=False)
    op.create_index("ix_task_results_status", "task_results", ["status"], unique=False)
    op.create_index("ix_task_results_task_id", "task_results", ["task_id"], unique=False)

    op.create_table(
        "result_chunks",
        sa.Column("task_result_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("beacon_id", sa.Uuid(), nullable=False),
        sa.Column("upload_id", sa.String(length=128), nullable=False),
        sa.Column("stream", sa.String(length=32), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("chunk_sha256", sa.String(length=64), nullable=False),
        sa.Column("stream_sha256", sa.String(length=64), nullable=True),
        sa.Column("stream_size_bytes", sa.Integer(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["beacon_id"], ["beacons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_result_id"], ["task_results.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_result_id", "stream", "upload_id", "sequence", name="uq_result_chunks_sequence"),
    )
    op.create_index("ix_result_chunks_beacon_id", "result_chunks", ["beacon_id"], unique=False)
    op.create_index("ix_result_chunks_received_at", "result_chunks", ["received_at"], unique=False)
    op.create_index("ix_result_chunks_stream", "result_chunks", ["stream"], unique=False)
    op.create_index("ix_result_chunks_task_id", "result_chunks", ["task_id"], unique=False)
    op.create_index("ix_result_chunks_task_result_id", "result_chunks", ["task_result_id"], unique=False)
    op.create_index("ix_result_chunks_upload_id", "result_chunks", ["upload_id"], unique=False)

    op.create_table(
        "task_result_artifacts",
        sa.Column("task_result_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_result_id"], ["task_results.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_result_id", "artifact_id", "role", name="uq_task_result_artifacts_role"),
    )
    op.create_index("ix_task_result_artifacts_artifact_id", "task_result_artifacts", ["artifact_id"], unique=False)
    op.create_index("ix_task_result_artifacts_role", "task_result_artifacts", ["role"], unique=False)
    op.create_index(
        "ix_task_result_artifacts_task_result_id",
        "task_result_artifacts",
        ["task_result_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_task_result_artifacts_task_result_id", table_name="task_result_artifacts")
    op.drop_index("ix_task_result_artifacts_role", table_name="task_result_artifacts")
    op.drop_index("ix_task_result_artifacts_artifact_id", table_name="task_result_artifacts")
    op.drop_table("task_result_artifacts")
    op.drop_index("ix_result_chunks_upload_id", table_name="result_chunks")
    op.drop_index("ix_result_chunks_task_result_id", table_name="result_chunks")
    op.drop_index("ix_result_chunks_task_id", table_name="result_chunks")
    op.drop_index("ix_result_chunks_stream", table_name="result_chunks")
    op.drop_index("ix_result_chunks_received_at", table_name="result_chunks")
    op.drop_index("ix_result_chunks_beacon_id", table_name="result_chunks")
    op.drop_table("result_chunks")
    op.drop_index("ix_task_results_task_id", table_name="task_results")
    op.drop_index("ix_task_results_status", table_name="task_results")
    op.drop_index("ix_task_results_output_sha256", table_name="task_results")
    op.drop_index("ix_task_results_expires_at", table_name="task_results")
    op.drop_index("ix_task_results_completed_at", table_name="task_results")
    op.drop_index("ix_task_results_beacon_id", table_name="task_results")
    op.drop_table("task_results")
