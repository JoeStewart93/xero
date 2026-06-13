"""Add file transfer tables.

Revision ID: c2_0017_file_transfers
Revises: c2_0016_beacon_soft_removal
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2_0017_file_transfers"
down_revision = "c2_0016_beacon_soft_removal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "file_transfers",
        sa.Column("beacon_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("actor_subject", sa.String(length=255), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("remote_path", sa.String(length=1024), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("chunk_size_bytes", sa.Integer(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("staged_chunks", sa.Integer(), nullable=False),
        sa.Column("acked_chunks", sa.Integer(), nullable=False),
        sa.Column("overwrite", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["beacon_id"], ["beacons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_file_transfers_actor_subject", "file_transfers", ["actor_subject"])
    op.create_index("ix_file_transfers_artifact_id", "file_transfers", ["artifact_id"])
    op.create_index("ix_file_transfers_beacon_id", "file_transfers", ["beacon_id"])
    op.create_index("ix_file_transfers_completed_at", "file_transfers", ["completed_at"])
    op.create_index("ix_file_transfers_direction", "file_transfers", ["direction"])
    op.create_index("ix_file_transfers_session_id", "file_transfers", ["session_id"])
    op.create_index("ix_file_transfers_sha256", "file_transfers", ["sha256"])
    op.create_index("ix_file_transfers_started_at", "file_transfers", ["started_at"])
    op.create_index("ix_file_transfers_status", "file_transfers", ["status"])

    op.create_table(
        "file_transfer_chunks",
        sa.Column("transfer_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("chunk_sha256", sa.String(length=64), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("staged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["transfer_id"], ["file_transfers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transfer_id", "sequence", name="uq_file_transfer_chunks_sequence"),
    )
    op.create_index("ix_file_transfer_chunks_acked_at", "file_transfer_chunks", ["acked_at"])
    op.create_index("ix_file_transfer_chunks_staged_at", "file_transfer_chunks", ["staged_at"])
    op.create_index("ix_file_transfer_chunks_transfer_id", "file_transfer_chunks", ["transfer_id"])


def downgrade() -> None:
    op.drop_index("ix_file_transfer_chunks_transfer_id", table_name="file_transfer_chunks")
    op.drop_index("ix_file_transfer_chunks_staged_at", table_name="file_transfer_chunks")
    op.drop_index("ix_file_transfer_chunks_acked_at", table_name="file_transfer_chunks")
    op.drop_table("file_transfer_chunks")

    op.drop_index("ix_file_transfers_status", table_name="file_transfers")
    op.drop_index("ix_file_transfers_started_at", table_name="file_transfers")
    op.drop_index("ix_file_transfers_sha256", table_name="file_transfers")
    op.drop_index("ix_file_transfers_session_id", table_name="file_transfers")
    op.drop_index("ix_file_transfers_direction", table_name="file_transfers")
    op.drop_index("ix_file_transfers_completed_at", table_name="file_transfers")
    op.drop_index("ix_file_transfers_beacon_id", table_name="file_transfers")
    op.drop_index("ix_file_transfers_artifact_id", table_name="file_transfers")
    op.drop_index("ix_file_transfers_actor_subject", table_name="file_transfers")
    op.drop_table("file_transfers")
