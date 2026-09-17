"""Servizi DB-backed (Fase 2). Delegano la logica SRS pura a ``app.srs``."""
from __future__ import annotations

import random
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import lesson_state
from app.config import settings
from app.models import (
    Lesson,
    LessonPhase,
    LessonStatus,
    LessonType,
    Message,
    MessageRole,
    ReviewEvent,
    ReviewResult,
    ReviewSource,
    Scenario,
    UserSentence,
    VocabItem,
    VocabProgress,
    VocabSource,
    VocabState,
)
from app.srs import Candidate, Progress, apply_review, pick_due


# Carte di ripasso a fine lezione (fase ``karten``).
KARTEN_LIMIT = 12


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def is_placeholder_de(vocab: VocabItem) -> bool:
    """True se ``de`` è un placeholder (il termine tedesco non è ancora noto).

    Le parole richieste via ``[ ]`` nascono con ``de == it`` (placeholder) in attesa
    che l'agente fornisca il termine tedesco (Fase 3). Finché è placeholder non può
    essere confermata in harvest né entrare in alcuna coda di ripasso.
    """
    return not vocab.de or vocab.de == vocab.it


def _local_date(dt: datetime) -> date:
    return dt.astimezone(ZoneInfo(settings.timezone)).date()


async def get_lesson_or_404(session: AsyncSession, lesson_id: int) -> Lesson:
    lesson = await session.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="lezione non trovata")
    return lesson


async def get_current_lesson(session: AsyncSession) -> Lesson | None:
    return await session.scalar(
        select(Lesson)
        .where(Lesson.status == LessonStatus.in_progress)
        .order_by(Lesson.started_at.desc())
        .limit(1)
    )


async def count_requested_words(session: AsyncSession, lesson_id: int) -> int:
    rows = (
        await session.scalars(
            select(Message.requested_words).where(
                Message.lesson_id == lesson_id,
                Message.role == MessageRole.user,
                Message.requested_words.is_not(None),
            )
        )
    ).all()
    return sum(len(r or []) for r in rows)


async def plan_next_lesson(session: AsyncSession) -> tuple[Scenario, LessonType]:
    """Sceglie scenario e tipo per la prossima lezione (planner semplificato).

    Il planner completo (raccomandazioni, summary) arriva in Fase 3 (task 3.4);
    qui vale la regola > 6 parole richieste → resta sullo stesso scenario (variant).
    """
    scenarios = (await session.scalars(select(Scenario).order_by(Scenario.week_number))).all()
    first = scenarios[0]
    last = await session.scalar(select(Lesson).order_by(Lesson.started_at.desc()).limit(1))
    if last is None:
        return first, LessonType.base

    last_scenario = await session.get(Scenario, last.scenario_id)

    if last.status == LessonStatus.abandoned:
        return last_scenario, LessonType.base

    requested = await count_requested_words(session, last.id)
    if last.lesson_type != LessonType.variant and lesson_state.should_repeat_scenario(requested):
        return last_scenario, LessonType.variant

    order = [LessonType.base, LessonType.variant, LessonType.incident, LessonType.review]
    idx = order.index(last.lesson_type)
    if idx < len(order) - 1:
        return last_scenario, order[idx + 1]

    # dopo review → scenario successivo (week_number 1-based → indice 0-based = week_number)
    next_idx = last_scenario.week_number
    if next_idx < len(scenarios):
        return scenarios[next_idx], LessonType.base
    return scenarios[-1], LessonType.base


async def get_or_create_progress(session: AsyncSession, vocab_item_id: int) -> VocabProgress:
    progress = await session.get(VocabProgress, vocab_item_id)
    if progress is None:
        progress = VocabProgress(vocab_item_id=vocab_item_id, state=VocabState.new)
        session.add(progress)
        await session.flush()
    return progress


async def distinct_correct_lessons(session: AsyncSession, vocab_item_id: int) -> int:
    count = await session.scalar(
        select(func.count(func.distinct(ReviewEvent.lesson_id))).where(
            ReviewEvent.vocab_item_id == vocab_item_id,
            ReviewEvent.result == ReviewResult.correct,
            ReviewEvent.source.in_(
                [ReviewSource.warmup, ReviewSource.roleplay, ReviewSource.test]
            ),
            ReviewEvent.lesson_id.is_not(None),
        )
    )
    return count or 0


async def apply_review_event(
    session: AsyncSession,
    vocab_item_id: int,
    result: ReviewResult,
    now: datetime,
    source: ReviewSource,
    lesson_id: int | None,
    *,
    counts_for_consolidation: bool,
) -> VocabProgress:
    """Registra l'evento di review e aggiorna ``vocab_progress`` via SRS puro."""
    session.add(
        ReviewEvent(
            vocab_item_id=vocab_item_id,
            source=source,
            result=result,
            lesson_id=lesson_id,
        )
    )
    await session.flush()

    progress = await get_or_create_progress(session, vocab_item_id)
    distinct = 0
    if result == ReviewResult.correct and counts_for_consolidation:
        distinct = await distinct_correct_lessons(session, vocab_item_id)

    p = Progress(
        state=progress.state.value,
        correct_uses=progress.correct_uses,
        interval_days=progress.interval_days,
        lapses=progress.lapses,
        last_reviewed_at=progress.last_reviewed_at,
        next_review_at=progress.next_review_at,
    )
    new_p = apply_review(
        p,
        result=result.value,
        now=now,
        distinct_correct_lessons=distinct,
        counts_for_consolidation=counts_for_consolidation,
    )
    progress.state = VocabState(new_p.state)
    progress.correct_uses = new_p.correct_uses
    progress.interval_days = new_p.interval_days
    progress.lapses = new_p.lapses
    progress.last_reviewed_at = new_p.last_reviewed_at
    progress.next_review_at = new_p.next_review_at
    return progress


async def downgrade_consolidated_on_error(
    session: AsyncSession,
    vocab_item_id: int,
    now: datetime,
) -> VocabProgress | None:
    """Regola Fase 3: una parola ``consolidated`` che compare in un errore del
    Korrektor torna a ``used`` con ``next_review_at`` a 1 giorno e ``lapses += 1``.

    Ritorna il progress aggiornato, o ``None`` se la parola non era consolidated.
    """
    progress = await get_or_create_progress(session, vocab_item_id)
    if progress.state != VocabState.consolidated:
        return None
    progress.state = VocabState.used
    progress.lapses += 1
    progress.interval_days = 1
    progress.last_reviewed_at = now
    progress.next_review_at = now + timedelta(days=1)
    return progress


async def pick_warmup_words(
    session: AsyncSession,
    scenario_id: int,
    n_review: int = 5,
    n_new: int = 3,
    now: datetime | None = None,
    rng: random.Random | None = None,
) -> list[dict]:
    """8 parole del warm-up: ``n_review`` in ripasso + ``n_new`` nuove dello scenario.

    Ripasso = parole già viste/usate con ``next_review_at`` scaduto; nuove = parole
    dello scenario mai introdotte. Se un pool è insufficiente, si riempie dall'altro.
    """
    now = now or utcnow()

    review_rows = (
        await session.execute(
            select(VocabItem, VocabProgress)
            .join(VocabProgress, VocabProgress.vocab_item_id == VocabItem.id)
            .where(
                VocabItem.de != VocabItem.it,  # esclude i placeholder
                or_(
                    and_(
                        VocabProgress.state.in_([VocabState.seen, VocabState.used]),
                        VocabProgress.next_review_at.is_not(None),
                        VocabProgress.next_review_at <= now,
                    ),
                    VocabProgress.state == VocabState.consolidated,
                ),
            )
        )
    ).all()
    review_candidates = [
        Candidate(
            id=vi.id,
            state=vp.state.value,
            lapses=vp.lapses,
            next_review_at=vp.next_review_at,
            source=vi.source.value,
            created_at=vi.created_at,
        )
        for vi, vp in review_rows
    ]
    review_pick = pick_due(review_candidates, now, n_review, rng=rng)

    new_rows = (
        await session.execute(
            select(VocabItem, VocabProgress)
            .join(VocabProgress, VocabProgress.vocab_item_id == VocabItem.id)
            .where(VocabItem.scenario_id == scenario_id, VocabProgress.state == VocabState.new)
            .order_by(VocabItem.id)
        )
    ).all()
    new_pool = list(new_rows)
    new_pick = list(new_pool[:n_new])

    picked_ids = {c.id for c in review_pick} | {vi.id for vi, _ in new_pick}
    target = n_review + n_new
    while len(review_pick) + len(new_pick) < target:
        extra_new = next(((vi, vp) for vi, vp in new_pool if vi.id not in picked_ids), None)
        if extra_new is not None:
            new_pick.append(extra_new)
            picked_ids.add(extra_new[0].id)
            continue
        extra_review = next((c for c in review_candidates if c.id not in picked_ids), None)
        if extra_review is not None:
            review_pick.append(extra_review)
            picked_ids.add(extra_review.id)
            continue
        break

    words: list[dict] = []
    for c in review_pick:
        vi, _ = next((vi, vp) for vi, vp in review_rows if vi.id == c.id)
        words.append(
            {"vocab_item_id": vi.id, "de": vi.de, "it": vi.it, "is_new": False, "state": c.state}
        )
    for vi, vp in new_pick:
        words.append(
            {"vocab_item_id": vi.id, "de": vi.de, "it": vi.it, "is_new": True, "state": vp.state.value}
        )
    return words


async def pick_flashcard_queue(
    session: AsyncSession,
    limit: int = 20,
    now: datetime | None = None,
    rng: random.Random | None = None,
    scenario_id: int | None = None,
) -> list[dict]:
    """Coda flashcard: parole viste/usate con ``next_review_at`` scaduto + ripescaggio
    casuale delle consolidate, per priorità.

    ``scenario_id`` restringe la coda a un solo scenario (mazzo di fine lezione);
    ``None`` = tutti gli scenari.
    """
    now = now or utcnow()
    stmt = (
        select(VocabItem, VocabProgress)
        .join(VocabProgress, VocabProgress.vocab_item_id == VocabItem.id)
        .where(
            VocabItem.de != VocabItem.it,  # esclude i placeholder
            or_(
                and_(
                    VocabProgress.state.in_([VocabState.seen, VocabState.used]),
                    VocabProgress.next_review_at.is_not(None),
                    VocabProgress.next_review_at <= now,
                ),
                VocabProgress.state == VocabState.consolidated,
            ),
        )
    )
    if scenario_id is not None:
        stmt = stmt.where(VocabItem.scenario_id == scenario_id)
    rows = (await session.execute(stmt)).all()
    candidates = [
        Candidate(
            id=vi.id,
            state=vp.state.value,
            lapses=vp.lapses,
            next_review_at=vp.next_review_at,
            source=vi.source.value,
            created_at=vi.created_at,
        )
        for vi, vp in rows
    ]
    picked = pick_due(candidates, now, limit, rng=rng)
    by_id = {vi.id: (vi, vp) for vi, vp in rows}
    return [
        {
            "id": c.id,
            "de": by_id[c.id][0].de,
            "it": by_id[c.id][0].it,
            "state": c.state,
            "gender": by_id[c.id][0].gender,
            "plural": by_id[c.id][0].plural,
            "separable": by_id[c.id][0].separable,
            "example_de": by_id[c.id][0].example_de,
        }
        for c in picked
    ]


async def get_cards_by_ids(session: AsyncSession, ids: list[int]) -> list[dict]:
    """Carte (stesso formato di ``ReviewQueueItem``) per id, nell'ordine richiesto."""
    if not ids:
        return []
    rows = (
        await session.execute(
            select(VocabItem, VocabProgress)
            .join(VocabProgress, VocabProgress.vocab_item_id == VocabItem.id)
            .where(VocabItem.id.in_(ids))
        )
    ).all()
    by_id = {vi.id: (vi, vp) for vi, vp in rows}
    cards: list[dict] = []
    for vocab_id in ids:
        if vocab_id not in by_id:
            continue
        vi, vp = by_id[vocab_id]
        cards.append(
            {
                "id": vi.id,
                "de": vi.de,
                "it": vi.it,
                "state": vp.state.value,
                "gender": vi.gender,
                "plural": vi.plural,
                "separable": vi.separable,
                "example_de": vi.example_de,
            }
        )
    return cards


async def pick_karten_words(
    session: AsyncSession,
    lesson: Lesson,
    limit: int = KARTEN_LIMIT,
    now: datetime | None = None,
    rng: random.Random | None = None,
) -> list[dict]:
    """Mazzo dell'ultima fase (``karten``), in ordine di priorità:

    1. le parole usate in **questa** lezione, anche se non ancora dovute (chiude il
       cerchio su quello che l'utente ha appena fatto);
    2. le parole dovute dello **stesso scenario**;
    3. le altre parole dovute, di qualunque scenario, fino a ``limit`` carte.
    """
    now = now or utcnow()
    used_ids = list(
        dict.fromkeys(
            (
                await session.scalars(
                    select(ReviewEvent.vocab_item_id)
                    .join(VocabItem, VocabItem.id == ReviewEvent.vocab_item_id)
                    .where(
                        ReviewEvent.lesson_id == lesson.id,
                        ReviewEvent.source != ReviewSource.flashcard,
                        VocabItem.de != VocabItem.it,  # esclude i placeholder
                    )
                    .order_by(ReviewEvent.id)
                )
            ).all()
        )
    )
    ordered: list[int] = used_ids[:limit]
    if len(ordered) < limit:
        same_scenario = await pick_flashcard_queue(
            session, limit=limit, now=now, rng=rng, scenario_id=lesson.scenario_id
        )
        ordered += [w["id"] for w in same_scenario if w["id"] not in ordered]
    if len(ordered) < limit:
        global_due = await pick_flashcard_queue(session, limit=limit, now=now, rng=rng)
        ordered += [w["id"] for w in global_due if w["id"] not in ordered]
    return await get_cards_by_ids(session, ordered[:limit])


async def pick_test_words(
    session: AsyncSession,
    scenario_id: int,
    n: int = 15,
    now: datetime | None = None,
) -> list[dict]:
    """Parole del test della lezione ``review``: ``n`` vocaboli con ``example_de``.

    Priorità alle parole in scadenza (viste/usate), poi alle parole dello scenario,
    in ordine deterministico (stabile tra richieste successive).
    """
    now = now or utcnow()
    due_rows = (
        await session.execute(
            select(VocabItem, VocabProgress)
            .join(VocabProgress, VocabProgress.vocab_item_id == VocabItem.id)
            .where(
                VocabItem.de != VocabItem.it,
                VocabItem.example_de != "",
                VocabProgress.state.in_([VocabState.seen, VocabState.used]),
                VocabProgress.next_review_at.is_not(None),
                VocabProgress.next_review_at <= now,
            )
            .order_by(VocabProgress.next_review_at, VocabItem.id)
        )
    ).all()
    scenario_rows = (
        await session.scalars(
            select(VocabItem)
            .where(
                VocabItem.scenario_id == scenario_id,
                VocabItem.de != VocabItem.it,
                VocabItem.example_de != "",
            )
            .order_by(VocabItem.id)
        )
    ).all()

    words: list[dict] = []
    seen: set[int] = set()
    for vi, _ in due_rows:
        if vi.id in seen:
            continue
        seen.add(vi.id)
        words.append({"vocab_item_id": vi.id, "de": vi.de, "it": vi.it, "example_de": vi.example_de})
        if len(words) >= n:
            return words
    for vi in scenario_rows:
        if vi.id in seen:
            continue
        seen.add(vi.id)
        words.append({"vocab_item_id": vi.id, "de": vi.de, "it": vi.it, "example_de": vi.example_de})
        if len(words) >= n:
            break
    return words


async def get_test_harvest_words(session: AsyncSession, lesson_id: int) -> list[dict]:
    """Parole dell'Ernte per la lezione ``review``: quelle sbagliate nel test."""
    rows = (
        await session.scalars(
            select(VocabItem)
            .join(ReviewEvent, ReviewEvent.vocab_item_id == VocabItem.id)
            .where(
                ReviewEvent.lesson_id == lesson_id,
                ReviewEvent.source == ReviewSource.test,
                ReviewEvent.result == ReviewResult.wrong,
            )
            .order_by(VocabItem.id)
        )
    ).all()
    words = [
        {
            "de": vi.de,
            "it": vi.it,
            "source": "error",
            "vocab_item_id": vi.id,
        }
        for vi in rows
    ]
    # deduplica per vocab_item_id (eventi multipli sullo stesso vocab)
    deduped: list[dict] = []
    seen: set[int] = set()
    for w in words:
        if w["vocab_item_id"] in seen:
            continue
        seen.add(w["vocab_item_id"])
        deduped.append(w)
    return deduped


async def roleplay_history(session: AsyncSession, lesson_id: int) -> list[dict]:
    msgs = (
        await session.scalars(
            select(Message)
            .where(Message.lesson_id == lesson_id, Message.phase == LessonPhase.roleplay)
            .order_by(Message.id)
        )
    ).all()
    return [{"role": m.role.value, "content": m.content} for m in msgs]


async def get_or_create_requested_vocab(
    session: AsyncSession, scenario_id: int, term: str
) -> VocabItem:
    """Crea/ritrova il vocabolo richiesto via ``[ ]`` (source=requested).

    Il termine tedesco nasce come placeholder (= termine italiano); in Fase 3
    l'agente fornisce il termine tedesco e lo sostituisce. La chiave di ricerca è
    ``it`` (stabile anche dopo la sostituzione di ``de``).
    """
    item = await session.scalar(
        select(VocabItem).where(
            VocabItem.it == term,
            VocabItem.source == VocabSource.requested,
            VocabItem.scenario_id == scenario_id,
        )
    )
    if item is None:
        item = VocabItem(de=term, it=term, scenario_id=scenario_id, source=VocabSource.requested)
        session.add(item)
        await session.flush()
        session.add(VocabProgress(vocab_item_id=item.id, state=VocabState.new))
    return item


async def get_or_create_agent_used_vocab(
    session: AsyncSession, scenario_id: int, de: str, it: str
) -> VocabItem:
    """Crea/ritrova un vocabolo "usato dall'agente" (source=agent_used) per l'Ernte."""
    de = (de or "").strip()
    it = (it or "").strip()
    if not de:
        raise ValueError("agent_used vocab senza termine tedesco")
    item = await session.scalar(
        select(VocabItem).where(
            VocabItem.de == de,
            VocabItem.source == VocabSource.agent_used,
            VocabItem.scenario_id == scenario_id,
        )
    )
    if item is None:
        item = VocabItem(de=de, it=it or de, scenario_id=scenario_id, source=VocabSource.agent_used)
        session.add(item)
        await session.flush()
        session.add(VocabProgress(vocab_item_id=item.id, state=VocabState.new))
    return item


_ARTICLE_RE = re.compile(r"^(der|die|das)\s+", re.IGNORECASE)


def lemma_of(de: str) -> str:
    """Lemma normalizzato: toglie l'articolo e minuscolizza (per il matching)."""
    return _ARTICLE_RE.sub("", (de or "").strip()).strip().lower()


async def match_error_vocab(
    session: AsyncSession, fix: str
) -> tuple[int | None, VocabItem | None]:
    """Trova il vocabolo corrispondente alla correzione ``fix`` (matching per lemma)."""
    target = lemma_of(fix)
    if not target:
        return None, None
    rows = (await session.scalars(select(VocabItem))).all()
    for vi in rows:
        if lemma_of(vi.de) == target:
            return vi.id, vi
    return None, None


async def last_user_incomprehensible(session: AsyncSession, lesson_id: int) -> bool:
    """True se l'ultimo messaggio utente del roleplay è stato marcato non comprensibile."""
    last = await session.scalar(
        select(Message)
        .where(Message.lesson_id == lesson_id, Message.phase == LessonPhase.roleplay, Message.role == MessageRole.user)
        .order_by(Message.id.desc())
        .limit(1)
    )
    if last is None or not last.corrections:
        return False
    return last.corrections.get("comprehensible") is False


async def get_harvest_words(session: AsyncSession, lesson_id: int) -> list[dict]:
    """Parole dell'Ernte: richieste via ``[ ]``, errori del Korrektor e parole usate
    dall'agente (tutte già materializzate come ``vocab_items`` durante il roleplay)."""
    msgs = (
        await session.scalars(
            select(Message)
            .where(Message.lesson_id == lesson_id, Message.phase == LessonPhase.roleplay)
            .order_by(Message.id)
        )
    ).all()
    words: list[dict] = []
    for m in msgs:
        for w in m.requested_words or []:
            if w.get("vocab_item_id"):
                words.append(
                    {
                        "de": w.get("de"),
                        "it": w.get("it"),
                        "source": "requested",
                        "vocab_item_id": w.get("vocab_item_id"),
                    }
                )
        if m.role == MessageRole.user and m.corrections:
            for e in m.corrections.get("errors", []):
                if e.get("vocab_item_id"):
                    words.append(
                        {
                            "de": e.get("fix"),
                            "it": e.get("it"),
                            "source": "error",
                            "vocab_item_id": e.get("vocab_item_id"),
                        }
                    )
            for nw in m.corrections.get("new_words_from_agent", []):
                if nw.get("vocab_item_id"):
                    words.append(
                        {
                            "de": nw.get("de"),
                            "it": nw.get("it"),
                            "source": "agent_used",
                            "vocab_item_id": nw.get("vocab_item_id"),
                        }
                    )
    return words


async def get_harvest_corrections(session: AsyncSession, lesson_id: int, limit: int = 3) -> list[dict]:
    """Blocco "Correzioni" dell'Ernte: al massimo ``limit`` errori del Korrektor."""
    msgs = (
        await session.scalars(
            select(Message)
            .where(
                Message.lesson_id == lesson_id,
                Message.phase == LessonPhase.roleplay,
                Message.role == MessageRole.user,
                Message.corrections.is_not(None),
            )
            .order_by(Message.id)
        )
    ).all()
    corrections: list[dict] = []
    for m in msgs:
        for e in (m.corrections or {}).get("errors", []):
            corrections.append(
                {
                    "sentence": e.get("span"),
                    "corrected": e.get("fix"),
                    "rule_it": e.get("rule_it"),
                }
            )
            if len(corrections) >= limit:
                return corrections
    return corrections


async def gather_planner_data(session: AsyncSession, lesson_id: int) -> dict:
    """Dati per il Planer: parole richieste/errate/usate e correzioni della lezione."""
    words = await get_harvest_words(session, lesson_id)
    requested = [w["de"] for w in words if w["source"] == "requested"]
    error_words = [w["de"] for w in words if w["source"] == "error"]
    agent_words = [w["de"] for w in words if w["source"] == "agent_used"]
    corrections = [c["rule_it"] for c in await get_harvest_corrections(session, lesson_id)]
    return {
        "requested": requested,
        "error_words": error_words,
        "agent_words": agent_words,
        "corrections": corrections,
    }


async def scenario_has_completed_lesson(session: AsyncSession, scenario_id: int) -> bool:
    """Vero se esiste almeno una lezione completata per lo scenario (l'Einstieg si comprime)."""
    found = await session.scalar(
        select(Lesson.id)
        .where(Lesson.scenario_id == scenario_id, Lesson.status == LessonStatus.completed)
        .limit(1)
    )
    return found is not None


async def build_lesson_detail(session: AsyncSession, lesson: Lesson) -> dict:
    scenario = await session.get(Scenario, lesson.scenario_id)
    messages = (
        await session.scalars(select(Message).where(Message.lesson_id == lesson.id).order_by(Message.id))
    ).all()
    roleplay_messages = [
        {"role": m.role.value, "content": m.content, "requested_words": m.requested_words}
        for m in messages
        if m.phase == LessonPhase.roleplay
    ]
    warmup_words = None
    if lesson.current_phase == LessonPhase.warmup:
        warmup_words = await pick_warmup_words(session, lesson.scenario_id)
    test_words = None
    if lesson.lesson_type == LessonType.review and lesson.current_phase == LessonPhase.test:
        test_words = await pick_test_words(session, lesson.scenario_id)
    # fase finale: flashcard delle parole dovute oggi (stessa coda della tab Vocabolario)
    karten_words = None
    if lesson.current_phase == LessonPhase.karten:
        karten_words = await pick_karten_words(session, lesson, limit=KARTEN_LIMIT)
    harvest_words = None
    harvest_corrections = None
    if lesson.current_phase == LessonPhase.harvest:
        if lesson.lesson_type == LessonType.review:
            harvest_words = await get_test_harvest_words(session, lesson.id)
        else:
            harvest_words = await get_harvest_words(session, lesson.id)
            harvest_corrections = await get_harvest_corrections(session, lesson.id)
    dialogue_closed = bool((lesson.summary or {}).get("dialogue_closed"))
    return {
        "id": lesson.id,
        "scenario_id": scenario.id,
        "scenario_title_de": scenario.title_de,
        "scenario_title_it": scenario.title_it,
        "role_label": scenario.role_label,
        "lesson_type": lesson.lesson_type.value,
        "status": lesson.status.value,
        "current_phase": lesson.current_phase.value if lesson.current_phase else None,
        "started_at": lesson.started_at,
        "ended_at": lesson.ended_at,
        "key_phrases": scenario.key_phrases or [],
        "swiss_variants": scenario.swiss_variants or [],
        "intro": scenario.intro,
        "intro_collapsed": await scenario_has_completed_lesson(session, scenario.id),
        "warmup_words": warmup_words,
        "roleplay_messages": roleplay_messages,
        "dialogue_closed": dialogue_closed,
        "harvest_words": harvest_words,
        "harvest_corrections": harvest_corrections,
        "requested_words_count": await count_requested_words(session, lesson.id),
        "test_words": test_words,
        "karten_words": karten_words,
    }


async def compute_streak(session: AsyncSession, now: datetime) -> int:
    completed = (
        await session.scalars(
            select(Lesson.ended_at).where(
                Lesson.status == LessonStatus.completed, Lesson.ended_at.is_not(None)
            )
        )
    ).all()
    days = {_local_date(d) for d in completed}
    cursor = _local_date(now)
    if cursor not in days:
        cursor -= timedelta(days=1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


async def compute_progress(session: AsyncSession, now: datetime) -> dict:
    rows = (
        await session.execute(
            select(VocabProgress.state, func.count()).group_by(VocabProgress.state)
        )
    ).all()
    counts = {"new": 0, "seen": 0, "used": 0, "consolidated": 0}
    for state, cnt in rows:
        counts[state.value] = cnt
    total = sum(counts.values())

    completed_lessons = (
        await session.scalar(
            select(func.count()).select_from(Lesson).where(Lesson.status == LessonStatus.completed)
        )
        or 0
    )

    current_lesson = await get_current_lesson(session)
    if current_lesson is not None:
        current_scenario = await session.get(Scenario, current_lesson.scenario_id)
    else:
        last = await session.scalar(select(Lesson).order_by(Lesson.started_at.desc()).limit(1))
        if last is not None:
            current_scenario = await session.get(Scenario, last.scenario_id)
        else:
            current_scenario = await session.scalar(
                select(Scenario).order_by(Scenario.week_number).limit(1)
            )

    completed_scenario_ids = set(
        (
            await session.scalars(
                select(Lesson.scenario_id).where(Lesson.status == LessonStatus.completed)
            )
        ).all()
    )
    scenarios = (await session.scalars(select(Scenario).order_by(Scenario.week_number))).all()
    path = [
        {
            "week": sc.week_number,
            "id": sc.id,
            "title": sc.title_de,
            "subtitle": sc.title_it,
            "completed": sc.id in completed_scenario_ids,
            "current": sc.id == (current_scenario.id if current_scenario else None),
        }
        for sc in scenarios
    ]

    return {
        "total_vocab": total,
        "counts": counts,
        "completed_lessons": completed_lessons,
        "streak": await compute_streak(session, now),
        "current_scenario": {
            "id": current_scenario.id,
            "title_de": current_scenario.title_de,
            "title_it": current_scenario.title_it,
            "week_number": current_scenario.week_number,
        }
        if current_scenario
        else None,
        "path": path,
    }


async def compute_home(session: AsyncSession, now: datetime) -> dict:
    current_lesson = await get_current_lesson(session)
    scenario, planned_type = await plan_next_lesson(session)
    due_queue = await pick_flashcard_queue(session, limit=100, now=now)
    return {
        "user_name": settings.user_name,
        "resume_lesson_id": current_lesson.id if current_lesson else None,
        "next_scenario": {
            "id": scenario.id,
            "title_de": scenario.title_de,
            "title_it": scenario.title_it,
            "role_label": scenario.role_label,
        },
        "lesson_type": (
            current_lesson.lesson_type.value if current_lesson else planned_type.value
        ),
        "due_today": len(due_queue),
        "due_words": [w["de"] for w in due_queue[:3]],
        "streak": await compute_streak(session, now),
        "current_week": scenario.week_number,
    }
