"""Add users.created_at for auth.

Revision ID: 003
Revises: 002
Create Date: 2025-01-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    # SQLite: optional backfill for existing rows
    try:
        op.execute(sa.text("UPDATE users SET created_at = datetime('now') WHERE created_at IS NULL"))
    except Exception:
        pass


def downgrade() -> None:
    op.drop_column("users", "created_at")
