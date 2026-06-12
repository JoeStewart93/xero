"""Add artifact storage metadata.

Revision ID: c2_0009_artifact_storage
Revises: c2_0008_beacon_builds
Create Date: 2026-06-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2_0009_artifact_storage"
down_revision = "c2_0008_beacon_builds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifacts",
        sa.Column("namespace", sa.String(length=64), nullable=False),
        sa.Column("owner_type", sa.String(length=64), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_backend", sa.String(length=32), nullable=False),
        sa.Column("bucket", sa.String(length=255), nullable=True),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_artifacts_namespace", "artifacts", ["namespace"], unique=False)
    op.create_index("ix_artifacts_object_key", "artifacts", ["object_key"], unique=False)
    op.create_index("ix_artifacts_owner_id", "artifacts", ["owner_id"], unique=False)
    op.create_index("ix_artifacts_owner_type", "artifacts", ["owner_type"], unique=False)
    op.create_index("ix_artifacts_sha256", "artifacts", ["sha256"], unique=False)
    op.create_index("ix_artifacts_storage_backend", "artifacts", ["storage_backend"], unique=False)

    with op.batch_alter_table("beacon_builds") as batch_op:
        batch_op.add_column(sa.Column("artifact_id", sa.Uuid(), nullable=True))
        batch_op.create_index("ix_beacon_builds_artifact_id", ["artifact_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_beacon_builds_artifact_id_artifacts",
            "artifacts",
            ["artifact_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("beacon_builds") as batch_op:
        batch_op.drop_constraint("fk_beacon_builds_artifact_id_artifacts", type_="foreignkey")
        batch_op.drop_index("ix_beacon_builds_artifact_id")
        batch_op.drop_column("artifact_id")
    op.drop_index("ix_artifacts_storage_backend", table_name="artifacts")
    op.drop_index("ix_artifacts_sha256", table_name="artifacts")
    op.drop_index("ix_artifacts_owner_type", table_name="artifacts")
    op.drop_index("ix_artifacts_owner_id", table_name="artifacts")
    op.drop_index("ix_artifacts_object_key", table_name="artifacts")
    op.drop_index("ix_artifacts_namespace", table_name="artifacts")
    op.drop_table("artifacts")
