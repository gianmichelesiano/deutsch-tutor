"""deck_notes.deck: mazzi separati (b1 = Wortliste B1 con SRS, a1 = Wortliste A1 a caso)

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-19

La stessa coppia (de, it) può stare in entrambi i mazzi: l'unicità diventa
(deck, de, it).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("deck_notes", sa.Column("deck", sa.Text(), nullable=False, server_default=sa.text("'b1'")))
    op.drop_constraint("uq_deck_notes_de_it", "deck_notes", type_="unique")
    op.create_unique_constraint("uq_deck_notes_deck_de_it", "deck_notes", ["deck", "de", "it"])


def downgrade() -> None:
    op.execute("DELETE FROM deck_notes WHERE deck <> 'b1'")
    op.drop_constraint("uq_deck_notes_deck_de_it", "deck_notes", type_="unique")
    op.create_unique_constraint("uq_deck_notes_de_it", "deck_notes", ["de", "it"])
    op.drop_column("deck_notes", "deck")
