"""Re-add Robokassa InvId and a provider column (Robokassa + Telegram Stars active).

provider_payment_id (added in 0007) is kept and now stores the Telegram Stars
charge id (and, in the future, a YooKassa payment UUID).

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("provider", sa.String(length=16), server_default="robokassa", nullable=False),
    )
    op.add_column(
        "payments",
        sa.Column("robokassa_inv_id", sa.Integer(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_payments_robokassa_inv_id", "payments", ["robokassa_inv_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_payments_robokassa_inv_id", "payments", type_="unique")
    op.drop_column("payments", "robokassa_inv_id")
    op.drop_column("payments", "provider")
