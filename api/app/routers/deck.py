"""Mazzo flashcard stile Anki: una carta alla volta, SM-2 (``app/deck_srs.py``).

Ordine della coda: learning/relearning scadute → review dovute oggi → nuove
(entro ``deck_new_per_day``) → learning entro 20 minuti. Le carte gemelle
(stessa nota, altra direzione) slittano a domani se una delle due è già stata
vista oggi; le carte in learning sono escluse da questa regola.
"""
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, distinct, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import deck_srs
from app.config import settings
from app.db import get_session
from app.models import DeckCard, DeckCardState, DeckNote, DeckReview
from app.schemas import (
    DeckAnswerIn,
    DeckCardOut,
    DeckCounts,
    DeckNextOut,
    DeckSummaryOut,
)
from app.services import utcnow

router = APIRouter(prefix=settings.api_prefix, tags=["deck"])

_rng = random.Random()
LEARNING = (DeckCardState.learning, DeckCardState.relearning)


def _state(card: DeckCard) -> deck_srs.CardState:
    return deck_srs.CardState(
        state=card.state.value,
        step=card.step,
        interval_days=card.interval_days,
        ease=card.ease,
        lapses=card.lapses,
        due=card.due,
    )


def _sibling_seen_since(start: datetime):
    """Un'altra carta della stessa nota ha una review da ``start``."""
    other = aliased(DeckCard)
    return exists().where(
        DeckReview.card_id == other.id,
        other.note_id == DeckCard.note_id,
        other.id != DeckCard.id,
        DeckReview.reviewed_at >= start,
    )


async def _count(session: AsyncSession, *where) -> int:
    return await session.scalar(select(func.count()).select_from(DeckCard).where(*where))


async def _next(session: AsyncSession, now: datetime) -> DeckNextOut:
    tz = ZoneInfo(settings.timezone)
    start, end = deck_srs.day_start(now, tz), deck_srs.next_day_start(now, tz)
    not_buried = ~_sibling_seen_since(start)

    new_today = await session.scalar(
        select(func.count())
        .select_from(DeckReview)
        .where(DeckReview.state_before == DeckCardState.new, DeckReview.reviewed_at >= start)
    )
    new_left = max(0, settings.deck_new_per_day - new_today)

    learn_due = and_(DeckCard.state.in_(LEARNING), DeckCard.due <= now)
    review_due = and_(DeckCard.state == DeckCardState.review, DeckCard.due < end, not_buried)
    new_ok = and_(DeckCard.state == DeckCardState.new, not_buried)
    learn_ahead = and_(DeckCard.state.in_(LEARNING), DeckCard.due <= now + deck_srs.LEARN_AHEAD)

    queries = [
        select(DeckCard).where(learn_due).order_by(DeckCard.due),
        select(DeckCard).where(review_due).order_by(DeckCard.due),
    ]
    if new_left:
        queries.append(select(DeckCard).where(new_ok).order_by(DeckCard.note_id, DeckCard.direction))
    queries.append(select(DeckCard).where(learn_ahead).order_by(DeckCard.due))

    card = None
    for q in queries:
        card = await session.scalar(q.limit(1))
        if card is not None:
            break

    counts = DeckCounts(
        new=min(new_left, await _count(session, new_ok)) if new_left else 0,
        learning=await _count(session, learn_ahead),
        review=await _count(session, review_due),
    )
    if card is None:
        return DeckNextOut(card=None, counts=counts, previews=[])
    note = await session.get(DeckNote, card.note_id)
    return DeckNextOut(
        card=DeckCardOut(
            id=card.id,
            direction=card.direction.value,
            state=card.state.value,
            de=note.de,
            it=note.it,
            theme=note.theme,
            example_de=note.example_de,
            example_it=note.example_it,
        ),
        counts=counts,
        previews=deck_srs.previews(_state(card), now),
    )


@router.get("/deck/next", response_model=DeckNextOut)
async def next_card(session: AsyncSession = Depends(get_session)):
    return await _next(session, utcnow())


@router.post("/deck/cards/{card_id}/answer", response_model=DeckNextOut)
async def answer_card(card_id: int, body: DeckAnswerIn, session: AsyncSession = Depends(get_session)):
    card = await session.get(DeckCard, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="carta non trovata")
    now = utcnow()
    before = card.state
    after = deck_srs.answer(_state(card), body.rating, now, rng=_rng)
    card.state = DeckCardState(after.state)
    card.step = after.step
    card.interval_days = after.interval_days
    card.ease = after.ease
    card.lapses = after.lapses
    card.due = after.due
    card.reps += 1
    card.last_reviewed_at = now
    session.add(
        DeckReview(
            card_id=card.id,
            rating=body.rating,
            state_before=before,
            interval_after=after.interval_days,
            ease_after=after.ease,
            reviewed_at=now,
        )
    )
    await session.commit()
    return await _next(session, now)


@router.get("/deck/summary", response_model=DeckSummaryOut)
async def summary(session: AsyncSession = Depends(get_session)):
    now = utcnow()
    start = deck_srs.day_start(now, ZoneInfo(settings.timezone))
    by_state = dict(
        (await session.execute(select(DeckCard.state, func.count()).group_by(DeckCard.state))).all()
    )
    return DeckSummaryOut(
        total_notes=await session.scalar(select(func.count()).select_from(DeckNote)),
        cards={s.value: by_state.get(s, 0) for s in DeckCardState},
        reviewed_today=await session.scalar(
            select(func.count()).select_from(DeckReview).where(DeckReview.reviewed_at >= start)
        ),
        notes_started=await session.scalar(
            select(func.count(distinct(DeckCard.note_id))).where(DeckCard.state != DeckCardState.new)
        ),
        next_due=await session.scalar(
            select(func.min(DeckCard.due)).where(DeckCard.state != DeckCardState.new, DeckCard.due > now)
        ),
        new_per_day=settings.deck_new_per_day,
    )
