"""Add traffic shaping profiles.

Revision ID: c2_0014_traffic_profiles
Revises: c2_0013_registry_sessions
Create Date: 2026-06-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c2_0014_traffic_profiles"
down_revision = "c2_0013_registry_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "traffic_profiles",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("template", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_traffic_profiles_name"),
    )
    op.create_index("ix_traffic_profiles_template", "traffic_profiles", ["template"])
    op.create_index("ix_traffic_profiles_is_template", "traffic_profiles", ["is_template"])
    op.create_index("ix_traffic_profiles_is_archived", "traffic_profiles", ["is_archived"])

    op.create_table(
        "traffic_profile_versions",
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["traffic_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "version", name="uq_traffic_profile_versions_profile_version"),
    )
    op.create_index("ix_traffic_profile_versions_profile_id", "traffic_profile_versions", ["profile_id"])
    op.create_index("ix_traffic_profile_versions_version", "traffic_profile_versions", ["version"])

    with op.batch_alter_table("beacons") as batch_op:
        batch_op.add_column(sa.Column("profile_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("applied_profile_version", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("profile_applied_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_beacons_profile_id", ["profile_id"])
        batch_op.create_foreign_key(
            "fk_beacons_profile_id_traffic_profiles",
            "traffic_profiles",
            ["profile_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("beacons") as batch_op:
        batch_op.drop_constraint("fk_beacons_profile_id_traffic_profiles", type_="foreignkey")
        batch_op.drop_index("ix_beacons_profile_id")
        batch_op.drop_column("profile_applied_at")
        batch_op.drop_column("applied_profile_version")
        batch_op.drop_column("profile_id")
    op.drop_index("ix_traffic_profile_versions_version", table_name="traffic_profile_versions")
    op.drop_index("ix_traffic_profile_versions_profile_id", table_name="traffic_profile_versions")
    op.drop_table("traffic_profile_versions")
    op.drop_index("ix_traffic_profiles_is_archived", table_name="traffic_profiles")
    op.drop_index("ix_traffic_profiles_is_template", table_name="traffic_profiles")
    op.drop_index("ix_traffic_profiles_template", table_name="traffic_profiles")
    op.drop_table("traffic_profiles")
