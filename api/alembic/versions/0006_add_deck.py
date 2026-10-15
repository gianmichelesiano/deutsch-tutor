"""mazzo flashcard stile Anki: deck_notes, deck_cards, deck_reviews

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DIRECTION = postgresql.ENUM("de_it", "it_de", name="deck_direction_enum", create_type=False)
CARD_STATE = postgresql.ENUM(
    "new", "learning", "review", "relearning", name="deck_card_state_enum", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    DIRECTION.create(bind)
    CARD_STATE.create(bind)

    op.create_table(
        "deck_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("de", sa.Text(), nullable=False),
        sa.Column("it", sa.Text(), nullable=False),
        sa.Column("theme", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("example_de", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("example_it", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("de", "it", name="uq_deck_notes_de_it"),
    )
    op.create_table(
        "deck_cards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("deck_notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", DIRECTION, nullable=False),
        sa.Column("state", CARD_STATE, nullable=False, server_default=sa.text("'new'")),
        sa.Column("due", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("ease", sa.Float(), nullable=False, server_default=sa.text("2.5")),
        sa.Column("step", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("reps", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("lapses", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("note_id", "direction", name="uq_deck_cards_note_direction"),
    )
    op.create_index("ix_deck_cards_note_id", "deck_cards", ["note_id"])
    op.create_index("ix_deck_cards_due", "deck_cards", ["due"])
    op.create_table(
        "deck_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("card_id", sa.Integer(), sa.ForeignKey("deck_cards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("state_before", CARD_STATE, nullable=False),
        sa.Column("interval_after", sa.Integer(), nullable=False),
        sa.Column("ease_after", sa.Float(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_deck_reviews_card_id", "deck_reviews", ["card_id"])
    op.create_index("ix_deck_reviews_reviewed_at", "deck_reviews", ["reviewed_at"])


def downgrade() -> None:
    op.drop_table("deck_reviews")
    op.drop_table("deck_cards")
    op.drop_table("deck_notes")
    bind = op.get_bind()
    CARD_STATE.drop(bind)
    DIRECTION.drop(bind)
