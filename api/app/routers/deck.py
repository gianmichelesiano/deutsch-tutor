"""Mazzo flashcard stile Anki: una carta alla volta, SM-2 (``app/deck_srs.py``).

Ordine della coda: learning/relearning scadute → review dovute oggi → nuove
(entro ``deck_new_per_day`` + ``extra``, per ``freq_rank``: più usate prima) → learning
entro 20 minuti. Le carte gemelle
(stessa nota, altra direzione) slittano a domani se una delle due è già stata
vista oggi; le carte in learning sono escluse da questa regola.

Tutto questo vale per il mazzo B1. Il mazzo A1 (``deck_notes.deck = 'a1'``) non ha
SRS: si usa solo con ``/deck/practice?deck=a1``, in ordine casuale.
"""
import random
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, distinct, exists, func, or_, select
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
    DeckNoteCardOut,
    DeckNoteOut,
    DeckNotesOut,
    DeckSummaryOut,
    DeckThemeOut,
)
from app.services import utcnow

router = APIRouter(prefix=settings.api_prefix, tags=["deck"])

_rng = random.Random()
LEARNING = (DeckCardState.learning, DeckCardState.relearning)
NOTES_LIMIT = 200

# Stato mostrato nell'elenco parole (relearning conta come learning)
_IS_REVIEW = DeckCard.state == DeckCardState.review
STATUS = case(
    (DeckCard.state.in_(LEARNING), "learning"),
    (and_(_IS_REVIEW, DeckCard.interval_days >= deck_srs.MATURE_DAYS), "mature"),
    (_IS_REVIEW, "review"),
    else_="new",
)
NOTE_FILTERS = {
    "started": DeckCard.state != DeckCardState.new,
    "learning": STATUS == "learning",
    "review": STATUS == "review",
    "mature": STATUS == "mature",
    "leech": DeckCard.lapses >= deck_srs.LEECH_LAPSES,
}


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


def _in_theme(theme: str, deck: str = "b1"):
    """Carte di un mazzo (b1 | a1), solo di un tema se ``theme`` non è vuoto."""
    notes = select(DeckNote.id).where(DeckNote.deck == deck)
    if theme:
        notes = notes.where(DeckNote.theme == theme)
    return DeckCard.note_id.in_(notes)


def _card_out(card: DeckCard, note: DeckNote) -> DeckCardOut:
    return DeckCardOut(
        id=card.id,
        direction=card.direction.value,
        state=card.state.value,
        de=note.de,
        it=note.it,
        theme=note.theme,
        example_de=note.example_de,
        example_it=note.example_it,
    )


async def _next(session: AsyncSession, now: datetime, extra: int = 0, theme: str = "") -> DeckNextOut:
    tz = ZoneInfo(settings.timezone)
    start, end = deck_srs.day_start(now, tz), deck_srs.next_day_start(now, tz)
    not_buried = and_(~_sibling_seen_since(start), _in_theme(theme))

    new_today = await session.scalar(
        select(func.count())
        .select_from(DeckReview)
        .where(DeckReview.state_before == DeckCardState.new, DeckReview.reviewed_at >= start)
    )
    new_left = max(0, settings.deck_new_per_day + extra - new_today)

    learn_due = and_(DeckCard.state.in_(LEARNING), DeckCard.due <= now, _in_theme(theme))
    review_due = and_(DeckCard.state == DeckCardState.review, DeckCard.due < end, not_buried)
    new_ok = and_(DeckCard.state == DeckCardState.new, not_buried)
    learn_ahead = and_(DeckCard.state.in_(LEARNING), DeckCard.due <= now + deck_srs.LEARN_AHEAD, _in_theme(theme))

    queries = [
        select(DeckCard).where(learn_due).order_by(DeckCard.due),
        select(DeckCard).where(review_due).order_by(DeckCard.due),
    ]
    if new_left:
        queries.append(
            select(DeckCard)
            .join(DeckNote, DeckNote.id == DeckCard.note_id)
            .where(new_ok)
            .order_by(DeckNote.freq_rank.asc().nulls_last(), DeckCard.note_id, DeckCard.direction)
        )
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
        card=_card_out(card, note),
        counts=counts,
        previews=deck_srs.previews(_state(card), now),
    )


@router.get("/deck/next", response_model=DeckNextOut)
async def next_card(
    extra: int = Query(0, ge=0),  # carte nuove in più oggi, scelte dall'utente oltre il limite
    theme: str = "",  # studia solo questo tema (il limite di nuove al giorno resta unico)
    session: AsyncSession = Depends(get_session),
):
    return await _next(session, utcnow(), extra, theme)


@router.post("/deck/cards/{card_id}/answer", response_model=DeckNextOut)
async def answer_card(
    card_id: int,
    body: DeckAnswerIn,
    extra: int = Query(0, ge=0),
    theme: str = "",
    session: AsyncSession = Depends(get_session),
):
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
    return await _next(session, now, extra, theme)


@router.get("/deck/summary", response_model=DeckSummaryOut)
async def summary(session: AsyncSession = Depends(get_session)):
    now = utcnow()
    start = deck_srs.day_start(now, ZoneInfo(settings.timezone))
    by_state = dict(
        (await session.execute(select(DeckCard.state, func.count()).where(_in_theme("")).group_by(DeckCard.state))).all()
    )
    return DeckSummaryOut(
        total_notes=await session.scalar(select(func.count()).select_from(DeckNote).where(DeckNote.deck == "b1")),
        cards={s.value: by_state.get(s, 0) for s in DeckCardState},
        reviewed_today=await session.scalar(
            select(func.count()).select_from(DeckReview).where(DeckReview.reviewed_at >= start)
        ),
        notes_started=await session.scalar(
            select(func.count(distinct(DeckCard.note_id))).where(DeckCard.state != DeckCardState.new, _in_theme(""))
        ),
        next_due=await session.scalar(
            select(func.min(DeckCard.due)).where(DeckCard.state != DeckCardState.new, DeckCard.due > now, _in_theme(""))
        ),
        new_per_day=settings.deck_new_per_day,
    )


@router.get("/deck/notes", response_model=DeckNotesOut)
async def list_notes(
    kind: str = Query("started", alias="filter"),  # started | learning | review | mature | leech | all
    q: str = "",
    session: AsyncSession = Depends(get_session),
):
    """Elenco parole con lo stato delle due carte: le viste di recente prima."""
    if kind != "all" and kind not in NOTE_FILTERS:
        raise HTTPException(status_code=422, detail=f"filtro sconosciuto: {kind}")
    where = [DeckNote.deck == "b1"]
    if kind != "all":
        where.append(exists().where(DeckCard.note_id == DeckNote.id, NOTE_FILTERS[kind]))
    if q.strip():
        pattern = f"%{q.strip()}%"
        where.append(or_(DeckNote.de.ilike(pattern), DeckNote.it.ilike(pattern)))
    last_seen = (
        select(func.max(DeckCard.last_reviewed_at)).where(DeckCard.note_id == DeckNote.id).scalar_subquery()
    )
    notes = (
        await session.scalars(
            select(DeckNote)
            .where(*where)
            .order_by(last_seen.desc().nulls_last(), DeckNote.freq_rank.asc().nulls_last(), DeckNote.id)
            .limit(NOTES_LIMIT)
        )
    ).all()
    cards = defaultdict(list)
    rows = await session.execute(
        select(DeckCard, STATUS)
        .where(DeckCard.note_id.in_([n.id for n in notes]))
        .order_by(DeckCard.note_id, DeckCard.direction)
    )
    for card, status in rows:
        cards[card.note_id].append(
            DeckNoteCardOut(
                direction=card.direction.value,
                status=status,
                interval_days=card.interval_days,
                lapses=card.lapses,
                due=card.due,
            )
        )
    counts = dict((await session.execute(select(STATUS, func.count()).where(_in_theme("")).group_by(STATUS))).all())
    return DeckNotesOut(
        counts={s: counts.get(s, 0) for s in ("new", "learning", "review", "mature")},
        total=await session.scalar(select(func.count()).select_from(DeckNote).where(*where)),
        notes=[
            DeckNoteOut(
                id=n.id,
                de=n.de,
                it=n.it,
                theme=n.theme,
                cards=cards[n.id],
                next_due=min((c.due for c in cards[n.id] if c.status != "new" and c.due), default=None),
            )
            for n in notes
        ],
    )


@router.get("/deck/themes", response_model=list[DeckThemeOut])
async def list_themes(session: AsyncSession = Depends(get_session)):
    """Temi del mazzo con il numero di parole, i più piccoli (più mirati) prima."""
    rows = await session.execute(
        select(DeckNote.theme, func.count())
        .where(DeckNote.theme != "", DeckNote.deck == "b1")
        .group_by(DeckNote.theme)
        .order_by(func.count(), DeckNote.theme)
    )
    return [DeckThemeOut(theme=t, notes=n) for t, n in rows]


# Fasce di frequenza per il ripasso libero (freq_rank: 1 = più usata)
FREQ_BANDS = {"top": (1, 1000), "mid": (1001, 2000), "rare": (2001, None)}


@router.get("/deck/practice", response_model=list[DeckCardOut])
async def practice(
    n: int = Query(20, ge=1, le=100),
    mode: str = Query("random", pattern="^(random|hard)$"),  # hard = carte sbagliate almeno una volta
    theme: str = "",
    freq: str = Query("all", pattern="^(all|top|mid|rare)$"),
    deck: str = Query("b1", pattern="^(a1|b1)$"),  # a1 = Wortliste A1, solo così (niente SRS)
    session: AsyncSession = Depends(get_session),
):
    """Ripasso libero: carte in ordine casuale, anche mai viste. Non tocca l'SRS."""
    where = [_in_theme(theme, deck)]
    if mode == "hard":
        where.append(DeckCard.lapses > 0)
    if freq in FREQ_BANDS:
        lo, hi = FREQ_BANDS[freq]
        where.append(DeckNote.freq_rank >= lo)
        if hi:
            where.append(DeckNote.freq_rank <= hi)
    rows = await session.execute(
        select(DeckCard, DeckNote).join(DeckNote, DeckNote.id == DeckCard.note_id).where(*where).order_by(func.random()).limit(n)
    )
    return [_card_out(card, note) for card, note in rows]
