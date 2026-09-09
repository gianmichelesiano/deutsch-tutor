"""Modelli Pydantic per le API (Fase 2)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


# --- Richieste ---
class WarmupAnswerIn(BaseModel):
    vocab_item_id: int
    sentence: str


class RoleplayMessageIn(BaseModel):
    content: str


class HarvestConfirmIn(BaseModel):
    vocab_item_ids: list[int]


class ReviewIn(BaseModel):
    result: str  # "correct" | "wrong"


class AdvanceIn(BaseModel):
    skip_swiss: bool = False


# --- Risposte ---
class WarmupAnswerOut(BaseModel):
    vocab_item_id: int
    is_correct: bool
    corrected_sentence: str | None = None
    feedback_it: str
    error_type: str


class RoleplayMessageOut(BaseModel):
    agent_text: str
    dialogue_closed: bool
    requested_words: list[dict] = []


class WarmupWord(BaseModel):
    vocab_item_id: int
    de: str
    it: str
    is_new: bool
    state: str


class LessonDetail(BaseModel):
    id: int
    scenario_id: int
    scenario_title_de: str
    scenario_title_it: str
    role_label: str | None
    lesson_type: str
    status: str
    current_phase: str | None
    started_at: datetime
    ended_at: datetime | None
    key_phrases: list[dict]
    swiss_variants: list[dict]
    warmup_words: list[WarmupWord] | None = None
    roleplay_messages: list[dict] = []
    dialogue_closed: bool = False
    harvest_words: list[dict] | None = None
    requested_words_count: int = 0


class ReviewQueueItem(BaseModel):
    id: int
    de: str
    it: str
    state: str
    gender: str | None
    plural: str | None
    separable: bool
    example_de: str


class VocabItemOut(BaseModel):
    id: int
    de: str
    it: str
    state: str
    gender: str | None
    plural: str | None
    separable: bool
    example_de: str
    next_review_at: datetime | None


class ReviewOut(BaseModel):
    id: int
    state: str
    next_review_at: datetime | None
