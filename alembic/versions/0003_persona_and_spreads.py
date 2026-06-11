"""Add luna_persona to users and create spreads table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("luna_persona", sa.String(16), server_default="young_moon", nullable=False),
    )
    op.create_table(
        "spreads",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.telegram_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("spread_type", sa.String(32), nullable=False),
        sa.Column("question", sa.String(1000), nullable=True),
        sa.Column("topic", sa.String(128), nullable=True),
        sa.Column("cards_json", sa.Text, nullable=True),
        sa.Column("interpretation", sa.Text, nullable=False),
    )
    op.create_index("ix_spreads_user_created", "spreads", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_spreads_user_created", table_name="spreads")
    op.drop_table("spreads")
    op.drop_column("users", "luna_persona")
