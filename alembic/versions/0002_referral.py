"""Add referral columns to users table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("referred_by", sa.BigInteger(), nullable=True))
    op.add_column("users", sa.Column(
        "referral_bonus_given", sa.Boolean(), nullable=False, server_default=sa.false()
    ))
    op.create_index("ix_users_referred_by", "users", ["referred_by"])


def downgrade() -> None:
    op.drop_index("ix_users_referred_by", table_name="users")
    op.drop_column("users", "referral_bonus_given")
    op.drop_column("users", "referred_by")
