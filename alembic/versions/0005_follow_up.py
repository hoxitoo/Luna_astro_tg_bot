"""Add follow-up columns to spreads ("Luna remembers").

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("spreads", sa.Column("follow_up_date", sa.Date(), nullable=True))
    op.add_column(
        "spreads",
        sa.Column("follow_up_sent", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_index(
        "ix_spreads_follow_up", "spreads", ["follow_up_date", "follow_up_sent"]
    )


def downgrade() -> None:
    op.drop_index("ix_spreads_follow_up", table_name="spreads")
    op.drop_column("spreads", "follow_up_sent")
    op.drop_column("spreads", "follow_up_date")
