"""Macchina a stati della lezione — puro, senza DB.

Stati: warmup → prep → roleplay → harvest → swiss → completed.
- Nessuno stato saltabile tranne ``swiss`` (opzionale: da ``harvest`` con
  ``skip_swiss`` si va direttamente a ``completed``).
- Transizione all'indietro consentita solo ``roleplay → prep`` (e ritorno).
"""
from __future__ import annotations

PHASES: tuple[str, ...] = ("warmup", "prep", "roleplay", "harvest", "swiss")
REVIEW_PHASES: tuple[str, ...] = ("warmup", "test", "harvest", "swiss")
TERMINAL = "completed"
REPEAT_SCENARIO_THRESHOLD = 6


class InvalidTransition(Exception):
    pass


def phases_for(lesson_type: str) -> tuple[str, ...]:
    """Fasi della lezione in base al tipo: ``review`` sostituisce prep+roleplay con ``test``."""
    return REVIEW_PHASES if lesson_type == "review" else PHASES


def phase_index(phase: str, lesson_type: str = "base") -> int:
    """Indice 0-based della fase (per l'indicatore a barre)."""
    return phases_for(lesson_type).index(phase)


def advance_phase(current: str, *, lesson_type: str = "base", skip_swiss: bool = False) -> str:
    """Fase successiva. Da ``swiss`` (o da ``harvest`` con ``skip_swiss``) → ``completed``."""
    if current == TERMINAL:
        raise InvalidTransition("lezione già completata")
    phases = phases_for(lesson_type)
    if current == "swiss":
        return TERMINAL
    if current == "harvest" and skip_swiss:
        return TERMINAL
    idx = phases.index(current)
    return phases[idx + 1]


def back_phase(current: str) -> str:
    """Transizione all'indietro: consentita solo ``roleplay → prep``."""
    if current != "roleplay":
        raise InvalidTransition(f"indietro non consentito da {current}")
    return "prep"


def should_repeat_scenario(requested_word_count: int) -> bool:
    """> 6 parole richieste con [ ] → la lezione successiva resta sullo stesso scenario."""
    return requested_word_count > REPEAT_SCENARIO_THRESHOLD
