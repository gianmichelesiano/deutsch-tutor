"""SM-2 (variante Anki) per il mazzo — modulo puro, senza accesso al DB.

Separato da ``app/srs.py`` (vocabolario delle lezioni): qui gli intervalli
crescono senza tetto, con facilità per carta e passi di apprendimento in minuti.
``now`` e ``rng`` sono sempre iniettati per la testabilità.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4

LEARNING_STEPS = (timedelta(minutes=1), timedelta(minutes=10))
RELEARNING_STEPS = (timedelta(minutes=10),)
GRADUATING_INTERVAL = 1
EASY_INTERVAL = 4
START_EASE = 2.5
MIN_EASE = 1.3
HARD_FACTOR = 1.2
EASY_BONUS = 1.3
FUZZ_RATIO = 0.05
FUZZ_MIN_DAYS = 3
DAY_CUTOFF_HOUR = 4  # la giornata di studio inizia alle 04:00 locali, come in Anki
LEARN_AHEAD = timedelta(minutes=20)


@dataclass(frozen=True)
class CardState:
    """Campi SRS di una carta (vincolati a ``deck_cards``)."""

    state: str = "new"  # new | learning | review | relearning
    step: int = 0
    interval_days: int = 0
    ease: float = START_EASE
    lapses: int = 0
    due: datetime | None = None


def _fuzz(days: int, floor: int, rng: random.Random | None) -> int:
    """±5% (almeno ±1 giorno) da 3 giorni in su; mai sotto ``floor``."""
    if rng is None or days < FUZZ_MIN_DAYS:
        return days
    delta = max(1, round(days * FUZZ_RATIO))
    return rng.randint(max(days - delta, floor), days + delta)


def _to_review(card: CardState, days: int, now: datetime) -> CardState:
    return replace(card, state="review", step=0, interval_days=days, due=now + timedelta(days=days))


def answer(card: CardState, rating: int, now: datetime, rng: random.Random | None = None) -> CardState:
    """Applica una risposta (1 Ancora · 2 Difficile · 3 Bene · 4 Facile).

    ``rng=None`` disattiva il fuzz (anteprime dei pulsanti, test).
    """
    if card.state in ("new", "learning", "relearning"):
        steps = RELEARNING_STEPS if card.state == "relearning" else LEARNING_STEPS
        state = "learning" if card.state == "new" else card.state
        if rating == AGAIN:
            return replace(card, state=state, step=0, due=now + steps[0])
        if rating == HARD:
            step = min(card.step, len(steps) - 1)
            return replace(card, state=state, step=step, due=now + steps[step])
        if rating == GOOD and card.step + 1 < len(steps):
            return replace(card, state=state, step=card.step + 1, due=now + steps[card.step + 1])
        if card.state == "relearning":
            return _to_review(card, card.interval_days, now)
        days = GRADUATING_INTERVAL if rating == GOOD else _fuzz(EASY_INTERVAL, 1, rng)
        return _to_review(card, days, now)

    # review
    ivl = card.interval_days
    if rating == AGAIN:
        return replace(
            card,
            state="relearning",
            step=0,
            interval_days=GRADUATING_INTERVAL,
            ease=max(MIN_EASE, round(card.ease - 0.20, 2)),
            lapses=card.lapses + 1,
            due=now + RELEARNING_STEPS[0],
        )
    if rating == HARD:
        ease, factor = max(MIN_EASE, round(card.ease - 0.15, 2)), HARD_FACTOR
    elif rating == GOOD:
        ease, factor = card.ease, card.ease
    else:
        ease, factor = round(card.ease + 0.15, 2), card.ease * EASY_BONUS
    days = _fuzz(max(ivl + 1, round(ivl * factor)), ivl + 1, rng)
    return replace(_to_review(card, days, now), ease=ease)


def format_interval(delta: timedelta) -> str:
    """Etichetta breve per i pulsanti: 1m · 3h · 4g · 1,5 mesi · 1,1 anni."""
    minutes = round(delta.total_seconds() / 60)
    if minutes < 60:
        return f"{minutes}m"
    if minutes < 24 * 60:
        return f"{round(minutes / 60)}h"
    days = round(minutes / (24 * 60))
    if days < 30:
        return f"{days}g"
    value, one, many = (days / 30, "mese", "mesi") if days < 365 else (days / 365, "anno", "anni")
    text = f"{value:.1f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{text} {one if text == '1' else many}"


def previews(card: CardState, now: datetime) -> list[str]:
    """Etichette dei 4 pulsanti (senza fuzz)."""
    return [format_interval(answer(card, r, now).due - now) for r in (AGAIN, HARD, GOOD, EASY)]


def day_start(now: datetime, tz: ZoneInfo) -> datetime:
    """Inizio della giornata di studio che contiene ``now`` (04:00 locali)."""
    local = now.astimezone(tz)
    d = local.date() if local.hour >= DAY_CUTOFF_HOUR else local.date() - timedelta(days=1)
    return datetime.combine(d, time(DAY_CUTOFF_HOUR), tzinfo=tz)


def next_day_start(now: datetime, tz: ZoneInfo) -> datetime:
    return datetime.combine(day_start(now, tz).date() + timedelta(days=1), time(DAY_CUTOFF_HOUR), tzinfo=tz)
