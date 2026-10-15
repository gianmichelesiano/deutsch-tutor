"""deck_notes.freq_rank: ordine di introduzione delle carte nuove per frequenza

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("deck_notes", sa.Column("freq_rank", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("deck_notes", "freq_rank")
