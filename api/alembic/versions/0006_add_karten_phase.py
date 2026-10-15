"""add lesson_phase_enum 'karten' (flashcard di fine lezione)

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-17

Le lezioni ``in_progress`` esistenti restano nella loro fase: ``karten`` viene
raggiunta solo avanzando da ``swiss``.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE lesson_phase_enum ADD VALUE IF NOT EXISTS 'karten'")


def downgrade() -> None:
    # PostgreSQL non supporta la rimozione di un valore da un enum in modo semplice.
    pass
