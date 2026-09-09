"""add lessons.current_phase

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

lesson_phase_enum = postgresql.ENUM(
    "warmup", "prep", "roleplay", "harvest", "swiss",
    name="lesson_phase_enum",
    create_type=False,
)


def upgrade() -> None:
    op.add_column(
        "lessons",
        sa.Column("current_phase", lesson_phase_enum, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lessons", "current_phase")
