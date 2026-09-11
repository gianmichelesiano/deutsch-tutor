"""add lesson_phase_enum 'test'

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-09

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE lesson_phase_enum ADD VALUE IF NOT EXISTS 'test'")


def downgrade() -> None:
    # PostgreSQL non supporta la rimozione di un valore da un enum in modo semplice.
    pass
