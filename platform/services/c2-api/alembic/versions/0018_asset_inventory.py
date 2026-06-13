"""Add asset inventory tables.

Revision ID: c2_0018_asset_inventory
Revises: c2_0017_file_transfers
Create Date: 2026-06-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2_0018_asset_inventory"
down_revision = "c2_0017_file_transfers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("dedup_key", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("primary_ip", sa.String(length=64), nullable=True),
        sa.Column("os", sa.String(length=128), nullable=True),
        sa.Column("role", sa.String(length=128), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_asset_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["canonical_asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedup_key", name="uq_assets_dedup_key"),
    )
    op.create_index("ix_assets_asset_type", "assets", ["asset_type"])
    op.create_index("ix_assets_canonical_asset_id", "assets", ["canonical_asset_id"])
    op.create_index("ix_assets_dedup_key", "assets", ["dedup_key"])
    op.create_index("ix_assets_domain", "assets", ["domain"])
    op.create_index("ix_assets_first_seen", "assets", ["first_seen"])
    op.create_index("ix_assets_hostname", "assets", ["hostname"])
    op.create_index("ix_assets_last_seen", "assets", ["last_seen"])
    op.create_index("ix_assets_primary_ip", "assets", ["primary_ip"])
    op.create_index("ix_assets_source", "assets", ["source"])

    op.create_table(
        "asset_identifiers",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("normalized_value", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "kind", "normalized_value", name="uq_asset_identifiers_asset_kind_value"),
    )
    op.create_index("ix_asset_identifiers_asset_id", "asset_identifiers", ["asset_id"])
    op.create_index("ix_asset_identifiers_kind", "asset_identifiers", ["kind"])
    op.create_index("ix_asset_identifiers_last_seen", "asset_identifiers", ["last_seen"])
    op.create_index("ix_asset_identifiers_normalized_value", "asset_identifiers", ["normalized_value"])
    op.create_index("ix_asset_identifiers_source", "asset_identifiers", ["source"])

    op.create_table(
        "asset_beacon_links",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("beacon_id", sa.Uuid(), nullable=False),
        sa.Column("machine_fingerprint_hash", sa.String(length=128), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["beacon_id"], ["beacons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("beacon_id", name="uq_asset_beacon_links_beacon_id"),
        sa.UniqueConstraint("machine_fingerprint_hash", name="uq_asset_beacon_links_fingerprint"),
    )
    op.create_index("ix_asset_beacon_links_asset_id", "asset_beacon_links", ["asset_id"])
    op.create_index("ix_asset_beacon_links_beacon_id", "asset_beacon_links", ["beacon_id"])
    op.create_index("ix_asset_beacon_links_last_seen", "asset_beacon_links", ["last_seen"])
    op.create_index(
        "ix_asset_beacon_links_machine_fingerprint_hash",
        "asset_beacon_links",
        ["machine_fingerprint_hash"],
    )

    op.create_table(
        "asset_relationships",
        sa.Column("source_asset_id", sa.Uuid(), nullable=False),
        sa.Column("target_asset_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("scan_job_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scan_job_id"], ["scan_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_asset_id",
            "target_asset_id",
            "relationship_type",
            "scan_job_id",
            name="uq_asset_relationships_scan_relationship",
        ),
    )
    op.create_index("ix_asset_relationships_last_seen", "asset_relationships", ["last_seen"])
    op.create_index("ix_asset_relationships_relationship_type", "asset_relationships", ["relationship_type"])
    op.create_index("ix_asset_relationships_scan_job_id", "asset_relationships", ["scan_job_id"])
    op.create_index("ix_asset_relationships_source", "asset_relationships", ["source"])
    op.create_index("ix_asset_relationships_source_asset_id", "asset_relationships", ["source_asset_id"])
    op.create_index("ix_asset_relationships_target_asset_id", "asset_relationships", ["target_asset_id"])

    op.create_table(
        "asset_observations",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("observation_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("scan_job_id", sa.Uuid(), nullable=True),
        sa.Column("scan_result_chunk_id", sa.Uuid(), nullable=True),
        sa.Column("beacon_id", sa.Uuid(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["beacon_id"], ["beacons.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["scan_job_id"], ["scan_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["scan_result_chunk_id"], ["scan_result_chunks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asset_observations_asset_id", "asset_observations", ["asset_id"])
    op.create_index("ix_asset_observations_beacon_id", "asset_observations", ["beacon_id"])
    op.create_index("ix_asset_observations_observation_type", "asset_observations", ["observation_type"])
    op.create_index("ix_asset_observations_observed_at", "asset_observations", ["observed_at"])
    op.create_index("ix_asset_observations_scan_job_id", "asset_observations", ["scan_job_id"])
    op.create_index("ix_asset_observations_scan_result_chunk_id", "asset_observations", ["scan_result_chunk_id"])
    op.create_index("ix_asset_observations_source", "asset_observations", ["source"])


def downgrade() -> None:
    op.drop_index("ix_asset_observations_source", table_name="asset_observations")
    op.drop_index("ix_asset_observations_scan_result_chunk_id", table_name="asset_observations")
    op.drop_index("ix_asset_observations_scan_job_id", table_name="asset_observations")
    op.drop_index("ix_asset_observations_observed_at", table_name="asset_observations")
    op.drop_index("ix_asset_observations_observation_type", table_name="asset_observations")
    op.drop_index("ix_asset_observations_beacon_id", table_name="asset_observations")
    op.drop_index("ix_asset_observations_asset_id", table_name="asset_observations")
    op.drop_table("asset_observations")

    op.drop_index("ix_asset_relationships_target_asset_id", table_name="asset_relationships")
    op.drop_index("ix_asset_relationships_source_asset_id", table_name="asset_relationships")
    op.drop_index("ix_asset_relationships_source", table_name="asset_relationships")
    op.drop_index("ix_asset_relationships_scan_job_id", table_name="asset_relationships")
    op.drop_index("ix_asset_relationships_relationship_type", table_name="asset_relationships")
    op.drop_index("ix_asset_relationships_last_seen", table_name="asset_relationships")
    op.drop_table("asset_relationships")

    op.drop_index("ix_asset_beacon_links_machine_fingerprint_hash", table_name="asset_beacon_links")
    op.drop_index("ix_asset_beacon_links_last_seen", table_name="asset_beacon_links")
    op.drop_index("ix_asset_beacon_links_beacon_id", table_name="asset_beacon_links")
    op.drop_index("ix_asset_beacon_links_asset_id", table_name="asset_beacon_links")
    op.drop_table("asset_beacon_links")

    op.drop_index("ix_asset_identifiers_source", table_name="asset_identifiers")
    op.drop_index("ix_asset_identifiers_normalized_value", table_name="asset_identifiers")
    op.drop_index("ix_asset_identifiers_last_seen", table_name="asset_identifiers")
    op.drop_index("ix_asset_identifiers_kind", table_name="asset_identifiers")
    op.drop_index("ix_asset_identifiers_asset_id", table_name="asset_identifiers")
    op.drop_table("asset_identifiers")

    op.drop_index("ix_assets_source", table_name="assets")
    op.drop_index("ix_assets_primary_ip", table_name="assets")
    op.drop_index("ix_assets_last_seen", table_name="assets")
    op.drop_index("ix_assets_hostname", table_name="assets")
    op.drop_index("ix_assets_first_seen", table_name="assets")
    op.drop_index("ix_assets_domain", table_name="assets")
    op.drop_index("ix_assets_dedup_key", table_name="assets")
    op.drop_index("ix_assets_canonical_asset_id", table_name="assets")
    op.drop_index("ix_assets_asset_type", table_name="assets")
    op.drop_table("assets")
