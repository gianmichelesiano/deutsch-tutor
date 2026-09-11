"""add llm_calls

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_llm_calls_task", "llm_calls", ["task"])


def downgrade() -> None:
    op.drop_index("ix_llm_calls_task", table_name="llm_calls")
    op.drop_table("llm_calls")
