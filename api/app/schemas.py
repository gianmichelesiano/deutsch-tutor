"""Modelli Pydantic per le API (Fase 2)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# --- Richieste ---
class WarmupAnswerIn(BaseModel):
    vocab_item_id: int
    sentence: str


class RoleplayMessageIn(BaseModel):
    content: str


class TestAnswerIn(BaseModel):
    vocab_item_id: int
    answer: str


class HarvestConfirmIn(BaseModel):
    vocab_item_ids: list[int]


class ReviewIn(BaseModel):
    result: str  # "correct" | "wrong"


class AdvanceIn(BaseModel):
    skip_swiss: bool = False


class LessonCreateIn(BaseModel):
    # se presente, salta il Planer e avvia una lezione "base" su questo scenario
    # (selezione manuale dal Percorso, tutti gli scenari sono sbloccati)
    scenario_id: int | None = None
    # scelta esplicita di un altro scenario dal Percorso mentre una lezione è
    # aperta: abbandona quella in corso invece di riprenderla (senza questo
    # flag la POST resta "riprendi la lezione corrente")
    replace_in_progress: bool = False


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


class TestAnswerOut(BaseModel):
    vocab_item_id: int
    is_correct: bool
    correct_de: str
    it: str


class WarmupWord(BaseModel):
    vocab_item_id: int
    de: str
    it: str
    is_new: bool
    state: str


class ReviewQueueItem(BaseModel):
    id: int
    de: str
    it: str
    state: str
    gender: str | None
    plural: str | None
    separable: bool
    example_de: str


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
    intro: dict | None = None
    intro_collapsed: bool = False
    warmup_words: list[WarmupWord] | None = None
    roleplay_messages: list[dict] = []
    dialogue_closed: bool = False
    harvest_words: list[dict] | None = None
    harvest_corrections: list[dict] | None = None
    requested_words_count: int = 0
    test_words: list[dict] | None = None
    karten_words: list[ReviewQueueItem] | None = None


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


# --- Mazzo ---
class DeckAnswerIn(BaseModel):
    rating: int = Field(ge=1, le=4)  # 1 Ancora · 2 Difficile · 3 Bene · 4 Facile


class DeckCardOut(BaseModel):
    id: int
    direction: str  # de_it | it_de
    state: str
    de: str
    it: str
    theme: str
    example_de: str
    example_it: str


class DeckCounts(BaseModel):
    new: int
    learning: int
    review: int


class DeckNextOut(BaseModel):
    card: DeckCardOut | None
    counts: DeckCounts
    previews: list[str]  # etichette dei 4 pulsanti; vuota se card è None


class DeckNoteCardOut(BaseModel):
    direction: str  # de_it | it_de
    status: str  # new | learning | review | mature
    interval_days: int
    lapses: int
    due: datetime | None


class DeckNoteOut(BaseModel):
    id: int
    de: str
    it: str
    theme: str
    cards: list[DeckNoteCardOut]
    next_due: datetime | None


class DeckNotesOut(BaseModel):
    counts: dict[str, int]  # carte per stato: new | learning | review | mature
    total: int  # parole che rispettano filtro e ricerca (l'elenco ne mostra al massimo 200)
    notes: list[DeckNoteOut]


class DeckSummaryOut(BaseModel):
    total_notes: int
    cards: dict[str, int]  # per stato: new | learning | review | relearning
    reviewed_today: int
    notes_started: int
    next_due: datetime | None
    new_per_day: int
