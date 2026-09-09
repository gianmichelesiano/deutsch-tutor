"""Motore di spaced repetition — modulo puro, senza accesso al DB.

Le date sono sempre iniettate (parametro ``now``) per la testabilità.
Il layer di servizio (``app/services.py``) recupera le righe dal DB, costruisce
i ``Candidate``/``Progress`` e chiama queste funzioni.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

# Intervalli in giorni: 1 -> 3 -> 7 -> 21 (capped a 21).
INTERVALS: tuple[int, ...] = (1, 3, 7, 21)
CONSOLIDATION_THRESHOLD = 3


@dataclass(frozen=True)
class Progress:
    """Snapshot dei campi SRS di un vocabolo (vincolato a ``vocab_progress``)."""

    state: str = "new"  # new | seen | used | consolidated
    correct_uses: int = 0
    interval_days: int = 0
    lapses: int = 0
    last_reviewed_at: datetime | None = None
    next_review_at: datetime | None = None


@dataclass(frozen=True)
class Candidate:
    """Candidato al ripasso, con i campi necessari al ranking."""

    id: int
    state: str
    lapses: int
    next_review_at: datetime | None
    source: str  # curated | requested | error | agent_used
    created_at: datetime


def next_interval(days: int) -> int:
    """Intervallo successivo nella sequenza 1→3→7→21 (capped a 21)."""
    for i in INTERVALS:
        if days < i:
            return i
    return INTERVALS[-1]


def should_consolidate(distinct_correct_lessons: int) -> bool:
    """True quando ci sono >= 3 usi corretti in 3 lezioni diverse."""
    return distinct_correct_lessons >= CONSOLIDATION_THRESHOLD


def is_due(next_review_at: datetime | None, now: datetime) -> bool:
    """``None`` = mai ripassato → dovuto subito."""
    return next_review_at is None or next_review_at <= now


def apply_review(
    progress: Progress,
    *,
    result: str,
    now: datetime,
    distinct_correct_lessons: int = 0,
    counts_for_consolidation: bool = False,
) -> Progress:
    """Applica una review e ritorna un nuovo ``Progress`` (immutabile).

    - ``result``: "correct" | "wrong".
    - ``counts_for_consolidation``: True per gli usi in frase
      (warmup/roleplay/test), False per il self-grading flashcard (che **non**
      avanza ``correct_uses`` e non porta a ``used``/``consolidated``).
    - ``distinct_correct_lessons``: numero di lezioni distinte con uso corretto
      **già includendo** l'evento corrente (lo calcola il servizio da
      ``review_events``).
    """
    if result == "correct":
        new_interval = next_interval(progress.interval_days)
        if counts_for_consolidation:
            correct_uses = progress.correct_uses + 1
            state = "consolidated" if should_consolidate(distinct_correct_lessons) else "used"
        else:
            correct_uses = progress.correct_uses
            state = "seen" if progress.state == "new" else progress.state
        return replace(
            progress,
            state=state,
            correct_uses=correct_uses,
            interval_days=new_interval,
            last_reviewed_at=now,
            next_review_at=now + timedelta(days=new_interval),
        )

    # wrong: torna a 1 giorno e incrementa i lapse
    return replace(
        progress,
        state="seen" if progress.state == "new" else progress.state,
        interval_days=1,
        lapses=progress.lapses + 1,
        last_reviewed_at=now,
        next_review_at=now + timedelta(days=1),
    )


def priority_key(candidate: Candidate, now: datetime) -> tuple:
    """Chiave di ranking: più bassa = priorità più alta.

    Ordine: 1) dovuto prima, 2) lapses più alto prima, 3) origine
    requested/error prima di curated/agent_used, 4) più recente prima.
    """
    due = 0 if is_due(candidate.next_review_at, now) else 1
    requested_or_error = 1 if candidate.source in ("requested", "error") else 0
    return (due, -candidate.lapses, -requested_or_error, -candidate.created_at.timestamp())


def rank(candidates: list[Candidate], now: datetime) -> list[Candidate]:
    return sorted(candidates, key=lambda c: priority_key(c, now))


def pick_due(candidates: list[Candidate], now: datetime, limit: int) -> list[Candidate]:
    """Candidati dovuti, ordinati per priorità, fino a ``limit``."""
    due = [c for c in candidates if is_due(c.next_review_at, now)]
    return rank(due, now)[:limit]
