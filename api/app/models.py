"""Modelli ORM (SQLAlchemy 2.0) per il DB Deutsch-Tutor.

Le enum sono tipi nativi Postgres; i nomi devono coincidere con la migrazione
Alembic ``0001_initial``.
"""
import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class VocabSource(str, enum.Enum):
    curated = "curated"
    requested = "requested"
    error = "error"
    agent_used = "agent_used"


class VocabState(str, enum.Enum):
    new = "new"
    seen = "seen"
    used = "used"
    consolidated = "consolidated"


class ReviewSource(str, enum.Enum):
    warmup = "warmup"
    flashcard = "flashcard"
    roleplay = "roleplay"
    test = "test"


class ReviewResult(str, enum.Enum):
    correct = "correct"
    wrong = "wrong"


class LessonType(str, enum.Enum):
    base = "base"
    variant = "variant"
    incident = "incident"
    review = "review"


class LessonStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"
    abandoned = "abandoned"


class LessonPhase(str, enum.Enum):
    warmup = "warmup"
    prep = "prep"
    roleplay = "roleplay"
    harvest = "harvest"
    swiss = "swiss"
    test = "test"


class MessageRole(str, enum.Enum):
    user = "user"
    agent = "agent"
    system = "system"


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    title_de: Mapped[str] = mapped_column(String(200))
    title_it: Mapped[str] = mapped_column(String(200))
    week_number: Mapped[int] = mapped_column(Integer, unique=True)
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    role_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    key_phrases: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    swiss_variants: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    imprevisti: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    goals: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))


class VocabItem(Base):
    __tablename__ = "vocab_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    de: Mapped[str] = mapped_column(String(200), index=True)
    it: Mapped[str] = mapped_column(String(200))
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    plural: Mapped[str | None] = mapped_column(String(200), nullable=True)
    separable: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    example_de: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    scenario_id: Mapped[int | None] = mapped_column(
        ForeignKey("scenarios.id"), nullable=True, index=True
    )
    source: Mapped[VocabSource] = mapped_column(Enum(VocabSource, name="source_enum", native_enum=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VocabProgress(Base):
    __tablename__ = "vocab_progress"

    vocab_item_id: Mapped[int] = mapped_column(
        ForeignKey("vocab_items.id", ondelete="CASCADE"), primary_key=True
    )
    state: Mapped[VocabState] = mapped_column(
        Enum(VocabState, name="vocab_state_enum", native_enum=True),
        default=VocabState.new,
        server_default=text("'new'"),
    )
    correct_uses: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    lapses: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))


class ReviewEvent(Base):
    __tablename__ = "review_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    vocab_item_id: Mapped[int] = mapped_column(
        ForeignKey("vocab_items.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[ReviewSource] = mapped_column(
        Enum(ReviewSource, name="review_source_enum", native_enum=True)
    )
    result: Mapped[ReviewResult] = mapped_column(
        Enum(ReviewResult, name="review_result_enum", native_enum=True)
    )
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenarios.id"), index=True)
    lesson_type: Mapped[LessonType] = mapped_column(
        Enum(LessonType, name="lesson_type_enum", native_enum=True)
    )
    current_phase: Mapped[LessonPhase | None] = mapped_column(
        Enum(LessonPhase, name="lesson_phase_enum", native_enum=True), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[LessonStatus] = mapped_column(
        Enum(LessonStatus, name="lesson_status_enum", native_enum=True),
        default=LessonStatus.in_progress,
        server_default=text("'in_progress'"),
    )
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    phase: Mapped[LessonPhase] = mapped_column(
        Enum(LessonPhase, name="lesson_phase_enum", native_enum=True)
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role_enum", native_enum=True)
    )
    content: Mapped[str] = mapped_column(Text)
    corrections: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    requested_words: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSentence(Base):
    __tablename__ = "user_sentences"

    id: Mapped[int] = mapped_column(primary_key=True)
    vocab_item_id: Mapped[int] = mapped_column(
        ForeignKey("vocab_items.id", ondelete="CASCADE"), index=True
    )
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    sentence: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    feedback: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LlmCall(Base):
    """Log di una chiamata LLM (task 3.1): task, provider, modello, token, latenza."""

    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    task: Mapped[str] = mapped_column(String(50), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(200))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    ok: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
