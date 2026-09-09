"""schema iniziale

Revision ID: 0001
Revises:
Create Date: 2026-09-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENUMS: dict[str, list[str]] = {
    "source_enum": ["curated", "requested", "error", "agent_used"],
    "vocab_state_enum": ["new", "seen", "used", "consolidated"],
    "review_source_enum": ["warmup", "flashcard", "roleplay", "test"],
    "review_result_enum": ["correct", "wrong"],
    "lesson_type_enum": ["base", "variant", "incident", "review"],
    "lesson_status_enum": ["in_progress", "completed", "abandoned"],
    "lesson_phase_enum": ["warmup", "prep", "roleplay", "harvest", "swiss"],
    "message_role_enum": ["user", "agent", "system"],
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in ENUMS.items():
        quoted = ", ".join(f"'{v}'" for v in values)
        bind.execute(sa.text(f"CREATE TYPE {name} AS ENUM ({quoted})"))

    op.create_table(
        "scenarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=120), nullable=False, unique=True),
        sa.Column("title_de", sa.String(length=200), nullable=False),
        sa.Column("title_it", sa.String(length=200), nullable=False),
        sa.Column("week_number", sa.Integer(), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("role_label", sa.String(length=200), nullable=True),
        sa.Column("key_phrases", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("swiss_variants", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("imprevisti", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("goals", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )

    op.create_table(
        "vocab_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("de", sa.String(length=200), nullable=False),
        sa.Column("it", sa.String(length=200), nullable=False),
        sa.Column("gender", sa.String(length=10), nullable=True),
        sa.Column("plural", sa.String(length=200), nullable=True),
        sa.Column("separable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("example_de", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("scenario_id", sa.Integer(), sa.ForeignKey("scenarios.id"), nullable=True),
        sa.Column("source", _enum("source_enum"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_vocab_items_de", "vocab_items", ["de"])
    op.create_index("ix_vocab_items_scenario_id", "vocab_items", ["scenario_id"])

    op.create_table(
        "vocab_progress",
        sa.Column("vocab_item_id", sa.Integer(), sa.ForeignKey("vocab_items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("state", _enum("vocab_state_enum"), nullable=False, server_default=sa.text("'new'")),
        sa.Column("correct_uses", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("lapses", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    op.create_table(
        "lessons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scenario_id", sa.Integer(), sa.ForeignKey("scenarios.id"), nullable=False),
        sa.Column("lesson_type", _enum("lesson_type_enum"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", _enum("lesson_status_enum"), nullable=False, server_default=sa.text("'in_progress'")),
        sa.Column("summary", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_lessons_scenario_id", "lessons", ["scenario_id"])

    op.create_table(
        "review_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vocab_item_id", sa.Integer(), sa.ForeignKey("vocab_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", _enum("review_source_enum"), nullable=False),
        sa.Column("result", _enum("review_result_enum"), nullable=False),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_review_events_vocab_item_id", "review_events", ["vocab_item_id"])
    op.create_index("ix_review_events_lesson_id", "review_events", ["lesson_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phase", _enum("lesson_phase_enum"), nullable=False),
        sa.Column("role", _enum("message_role_enum"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("corrections", postgresql.JSONB(), nullable=True),
        sa.Column("requested_words", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_messages_lesson_id", "messages", ["lesson_id"])

    op.create_table(
        "user_sentences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vocab_item_id", sa.Integer(), sa.ForeignKey("vocab_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sentence", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("feedback", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_user_sentences_vocab_item_id", "user_sentences", ["vocab_item_id"])
    op.create_index("ix_user_sentences_lesson_id", "user_sentences", ["lesson_id"])


def downgrade() -> None:
    op.drop_table("user_sentences")
    op.drop_table("messages")
    op.drop_table("review_events")
    op.drop_table("lessons")
    op.drop_table("vocab_progress")
    op.drop_table("vocab_items")
    op.drop_table("scenarios")
    for name in ENUMS:
        op.execute(sa.text(f"DROP TYPE {name}"))
