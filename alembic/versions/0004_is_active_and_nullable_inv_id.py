"""Add users.is_active; make payments.robokassa_inv_id nullable.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
    )
    op.alter_column("payments", "robokassa_inv_id", nullable=True)


def downgrade() -> None:
    op.alter_column("payments", "robokassa_inv_id", nullable=False)
    op.drop_column("users", "is_active")
