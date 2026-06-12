"""Add user role and enabled state.

Revision ID: bff_0002_role_enabled
Revises: bff_0001_users
Create Date: 2026-06-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "bff_0002_role_enabled"
down_revision = "bff_0001_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(length=32), server_default="operator", nullable=False))
    op.add_column("users", sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False))
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("users", "role", server_default=None)
        op.alter_column("users", "is_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "is_enabled")
    op.drop_column("users", "role")
