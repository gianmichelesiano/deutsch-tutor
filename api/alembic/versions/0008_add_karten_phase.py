"""add lesson_phase_enum 'karten' (flashcard di fine lezione)

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-17

Rinumerata da 0006 a 0008 quando la fase Karten e' stata mergiata in main: nel
frattempo main aveva introdotto 0006_add_deck e 0007_add_deck_freq_rank, quindi
la revisione 0006 era occupata due volte. La migrazione e' idempotente
(ADD VALUE IF NOT EXISTS), quindi e' sicuro rilanciarla su un DB che aveva gia'
applicato la vecchia 0006.

Le lezioni ``in_progress`` esistenti restano nella loro fase: ``karten`` viene
raggiunta solo avanzando da ``swiss``.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE lesson_phase_enum ADD VALUE IF NOT EXISTS 'karten'")


def downgrade() -> None:
    # PostgreSQL non supporta la rimozione di un valore da un enum in modo semplice.
    pass
