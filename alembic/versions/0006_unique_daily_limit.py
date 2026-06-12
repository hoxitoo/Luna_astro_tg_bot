"""Unique constraint on daily_limits(user_id, date) — closes get-or-create race.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-13
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Deduplicate first in case the race already produced doubles
    op.execute(
        """
        DELETE FROM daily_limits a
        USING daily_limits b
        WHERE a.id > b.id AND a.user_id = b.user_id AND a.date = b.date
        """
    )
    op.create_unique_constraint(
        "uq_daily_limits_user_date", "daily_limits", ["user_id", "date"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_daily_limits_user_date", "daily_limits", type_="unique")
