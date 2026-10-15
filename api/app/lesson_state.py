"""Macchina a stati della lezione — puro, senza DB.

Stati: intro → warmup → prep → roleplay → harvest → swiss → karten → completed.
- Il ripasso (``review``) non ha ``intro``: warmup → test → harvest → swiss → karten.
- ``karten`` è l'ultima fase (flashcard di ripasso a fine lezione) e porta a
  ``completed``: è l'unica tappa non saltabile dopo la Svizzera.
- ``skip_swiss`` da ``harvest`` salta solo la Svizzera e porta direttamente a
  ``karten`` (le carte restano).
- Transizioni all'indietro consentite: ``roleplay → prep`` e ``warmup → intro``.
"""
from __future__ import annotations

PHASES: tuple[str, ...] = ("intro", "warmup", "prep", "roleplay", "harvest", "swiss", "karten")
REVIEW_PHASES: tuple[str, ...] = ("warmup", "test", "harvest", "swiss", "karten")
TERMINAL = "completed"
REPEAT_SCENARIO_THRESHOLD = 6

SWISS_PHASE = "swiss"
KARTEN_PHASE = "karten"

BACK_TRANSITIONS: dict[str, str] = {"roleplay": "prep", "warmup": "intro"}


class InvalidTransition(Exception):
    pass


def phases_for(lesson_type: str) -> tuple[str, ...]:
    """Fasi della lezione in base al tipo: ``review`` sostituisce prep+roleplay con ``test``."""
    return REVIEW_PHASES if lesson_type == "review" else PHASES


def first_phase(lesson_type: str) -> str:
    """Fase iniziale di una nuova lezione (``intro``; ``warmup`` per il ripasso)."""
    return phases_for(lesson_type)[0]


def phase_index(phase: str, lesson_type: str = "base") -> int:
    """Indice 0-based della fase (per l'indicatore a barre)."""
    return phases_for(lesson_type).index(phase)


def advance_phase(current: str, *, lesson_type: str = "base", skip_swiss: bool = False) -> str:
    """Fase successiva. Da ``karten`` (ultima) → ``completed``."""
    if current == TERMINAL:
        raise InvalidTransition("lezione già completata")
    phases = phases_for(lesson_type)
    if current == "harvest" and skip_swiss:
        return KARTEN_PHASE
    idx = phases.index(current)
    if idx + 1 >= len(phases):
        return TERMINAL
    return phases[idx + 1]


def back_phase(current: str) -> str:
    """Transizione all'indietro: ``roleplay → prep`` e ``warmup → intro``."""
    try:
        return BACK_TRANSITIONS[current]
    except KeyError as exc:
        raise InvalidTransition(f"indietro non consentito da {current}") from exc


def should_repeat_scenario(requested_word_count: int) -> bool:
    """> 6 parole richieste con [ ] → la lezione successiva resta sullo stesso scenario."""
    return requested_word_count > REPEAT_SCENARIO_THRESHOLD
