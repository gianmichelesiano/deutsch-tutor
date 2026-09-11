"""add lesson_phase_enum 'intro' + scenarios.intro

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE lesson_phase_enum ADD VALUE IF NOT EXISTS 'intro'")
    op.add_column("scenarios", sa.Column("intro", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("scenarios", "intro")
    # PostgreSQL non supporta la rimozione di un valore da un enum in modo semplice.
