"""Switch payments from Robokassa InvId to YooKassa provider_payment_id.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("provider_payment_id", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_payments_provider_payment_id", "payments", ["provider_payment_id"]
    )
    # Robokassa is no longer used; drop the old InvId column.
    op.drop_column("payments", "robokassa_inv_id")


def downgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("robokassa_inv_id", sa.Integer(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_payments_robokassa_inv_id", "payments", ["robokassa_inv_id"]
    )
    op.drop_constraint("uq_payments_provider_payment_id", "payments", type_="unique")
    op.drop_column("payments", "provider_payment_id")
