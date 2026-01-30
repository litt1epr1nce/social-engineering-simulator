"""Initial tables: users, scenarios, progress, attempts.

Revision ID: 001
Revises:
Create Date: 2025-01-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "scenarios",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("tactic", sa.String(64), nullable=False),
        sa.Column("choices_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "progress",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("total_attempted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_progress_session_id"), "progress", ["session_id"], unique=True)
    op.create_index(op.f("ix_progress_user_id"), "progress", ["user_id"], unique=False)

    op.create_table(
        "attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("progress_id", sa.Integer(), nullable=False),
        sa.Column("scenario_id", sa.Integer(), nullable=False),
        sa.Column("choice_index", sa.Integer(), nullable=False),
        sa.Column("is_safe", sa.Boolean(), nullable=False),
        sa.Column("tactic", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["progress_id"], ["progress.id"]),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_attempts_progress_id"), "attempts", ["progress_id"], unique=False)
    op.create_index(op.f("ix_attempts_scenario_id"), "attempts", ["scenario_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_attempts_scenario_id"), table_name="attempts")
    op.drop_index(op.f("ix_attempts_progress_id"), table_name="attempts")
    op.drop_table("attempts")
    op.drop_index(op.f("ix_progress_user_id"), table_name="progress")
    op.drop_index(op.f("ix_progress_session_id"), table_name="progress")
    op.drop_table("progress")
    op.drop_table("scenarios")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
