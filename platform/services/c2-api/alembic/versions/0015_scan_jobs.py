"""Add scan jobs.

Revision ID: c2_0015_scan_jobs
Revises: c2_0014_traffic_profiles
Create Date: 2026-06-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c2_0015_scan_jobs"
down_revision = "c2_0014_traffic_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_jobs",
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("args", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("actor_subject", sa.String(length=255), nullable=False),
        sa.Column("execution_target_requested", sa.String(length=64), nullable=False),
        sa.Column("execution_target_resolved", sa.String(length=64), nullable=False),
        sa.Column("worker_id", sa.Uuid(), nullable=True),
        sa.Column("progress_completed", sa.Integer(), nullable=False),
        sa.Column("progress_total", sa.Integer(), nullable=False),
        sa.Column("state_counts", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["worker_id"], ["infrastructure_workers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_jobs_actor_subject", "scan_jobs", ["actor_subject"])
    op.create_index("ix_scan_jobs_completed_at", "scan_jobs", ["completed_at"])
    op.create_index("ix_scan_jobs_module", "scan_jobs", ["module"])
    op.create_index("ix_scan_jobs_queued_at", "scan_jobs", ["queued_at"])
    op.create_index("ix_scan_jobs_status", "scan_jobs", ["status"])
    op.create_index("ix_scan_jobs_worker_id", "scan_jobs", ["worker_id"])

    op.create_table(
        "scan_result_chunks",
        sa.Column("scan_job_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("probes_completed", sa.Integer(), nullable=False),
        sa.Column("probes_total", sa.Integer(), nullable=False),
        sa.Column("emitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scan_job_id"], ["scan_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_job_id", "sequence", name="uq_scan_result_chunks_sequence"),
    )
    op.create_index("ix_scan_result_chunks_emitted_at", "scan_result_chunks", ["emitted_at"])
    op.create_index("ix_scan_result_chunks_kind", "scan_result_chunks", ["kind"])
    op.create_index("ix_scan_result_chunks_scan_job_id", "scan_result_chunks", ["scan_job_id"])


def downgrade() -> None:
    op.drop_index("ix_scan_result_chunks_scan_job_id", table_name="scan_result_chunks")
    op.drop_index("ix_scan_result_chunks_kind", table_name="scan_result_chunks")
    op.drop_index("ix_scan_result_chunks_emitted_at", table_name="scan_result_chunks")
    op.drop_table("scan_result_chunks")
    op.drop_index("ix_scan_jobs_worker_id", table_name="scan_jobs")
    op.drop_index("ix_scan_jobs_status", table_name="scan_jobs")
    op.drop_index("ix_scan_jobs_queued_at", table_name="scan_jobs")
    op.drop_index("ix_scan_jobs_module", table_name="scan_jobs")
    op.drop_index("ix_scan_jobs_completed_at", table_name="scan_jobs")
    op.drop_index("ix_scan_jobs_actor_subject", table_name="scan_jobs")
    op.drop_table("scan_jobs")
