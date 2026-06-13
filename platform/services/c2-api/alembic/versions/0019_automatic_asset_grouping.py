"""Add automatic asset grouping tables.

Revision ID: c2_0019_asset_grouping
Revises: c2_0018_asset_inventory
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2_0019_asset_grouping"
down_revision = "c2_0018_asset_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_grouping_rules",
        sa.Column("rule_key", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_key", name="uq_asset_grouping_rules_rule_key"),
    )
    op.create_index("ix_asset_grouping_rules_enabled", "asset_grouping_rules", ["enabled"])
    op.create_index("ix_asset_grouping_rules_rule_key", "asset_grouping_rules", ["rule_key"])

    op.create_table(
        "asset_groups",
        sa.Column("group_key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=True),
        sa.Column("criterion_type", sa.String(length=64), nullable=True),
        sa.Column("criterion_value", sa.String(length=255), nullable=True),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["asset_groups.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rule_id"], ["asset_grouping_rules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_key", name="uq_asset_groups_group_key"),
    )
    op.create_index("ix_asset_groups_criterion_type", "asset_groups", ["criterion_type"])
    op.create_index("ix_asset_groups_criterion_value", "asset_groups", ["criterion_value"])
    op.create_index("ix_asset_groups_group_key", "asset_groups", ["group_key"])
    op.create_index("ix_asset_groups_parent_id", "asset_groups", ["parent_id"])
    op.create_index("ix_asset_groups_rule_id", "asset_groups", ["rule_id"])
    op.create_index("ix_asset_groups_type", "asset_groups", ["type"])

    op.create_table(
        "asset_group_memberships",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["asset_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["asset_grouping_rules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "group_id", name="uq_asset_group_memberships_asset_group"),
    )
    op.create_index("ix_asset_group_memberships_asset_id", "asset_group_memberships", ["asset_id"])
    op.create_index("ix_asset_group_memberships_group_id", "asset_group_memberships", ["group_id"])
    op.create_index("ix_asset_group_memberships_last_seen", "asset_group_memberships", ["last_seen"])
    op.create_index("ix_asset_group_memberships_rule_id", "asset_group_memberships", ["rule_id"])
    op.create_index("ix_asset_group_memberships_source", "asset_group_memberships", ["source"])

    op.create_table(
        "asset_grouping_events",
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column("group_id", sa.Uuid(), nullable=True),
        sa.Column("rule_id", sa.Uuid(), nullable=True),
        sa.Column("actor_subject", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("message", sa.String(length=512), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["group_id"], ["asset_groups.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rule_id"], ["asset_grouping_rules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asset_grouping_events_actor_subject", "asset_grouping_events", ["actor_subject"])
    op.create_index("ix_asset_grouping_events_asset_id", "asset_grouping_events", ["asset_id"])
    op.create_index("ix_asset_grouping_events_event_type", "asset_grouping_events", ["event_type"])
    op.create_index("ix_asset_grouping_events_group_id", "asset_grouping_events", ["group_id"])
    op.create_index("ix_asset_grouping_events_occurred_at", "asset_grouping_events", ["occurred_at"])
    op.create_index("ix_asset_grouping_events_rule_id", "asset_grouping_events", ["rule_id"])


def downgrade() -> None:
    op.drop_index("ix_asset_grouping_events_rule_id", table_name="asset_grouping_events")
    op.drop_index("ix_asset_grouping_events_occurred_at", table_name="asset_grouping_events")
    op.drop_index("ix_asset_grouping_events_group_id", table_name="asset_grouping_events")
    op.drop_index("ix_asset_grouping_events_event_type", table_name="asset_grouping_events")
    op.drop_index("ix_asset_grouping_events_asset_id", table_name="asset_grouping_events")
    op.drop_index("ix_asset_grouping_events_actor_subject", table_name="asset_grouping_events")
    op.drop_table("asset_grouping_events")

    op.drop_index("ix_asset_group_memberships_source", table_name="asset_group_memberships")
    op.drop_index("ix_asset_group_memberships_rule_id", table_name="asset_group_memberships")
    op.drop_index("ix_asset_group_memberships_last_seen", table_name="asset_group_memberships")
    op.drop_index("ix_asset_group_memberships_group_id", table_name="asset_group_memberships")
    op.drop_index("ix_asset_group_memberships_asset_id", table_name="asset_group_memberships")
    op.drop_table("asset_group_memberships")

    op.drop_index("ix_asset_groups_type", table_name="asset_groups")
    op.drop_index("ix_asset_groups_rule_id", table_name="asset_groups")
    op.drop_index("ix_asset_groups_parent_id", table_name="asset_groups")
    op.drop_index("ix_asset_groups_group_key", table_name="asset_groups")
    op.drop_index("ix_asset_groups_criterion_value", table_name="asset_groups")
    op.drop_index("ix_asset_groups_criterion_type", table_name="asset_groups")
    op.drop_table("asset_groups")

    op.drop_index("ix_asset_grouping_rules_rule_key", table_name="asset_grouping_rules")
    op.drop_index("ix_asset_grouping_rules_enabled", table_name="asset_grouping_rules")
    op.drop_table("asset_grouping_rules")
