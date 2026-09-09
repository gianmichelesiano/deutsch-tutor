"""Servizi DB-backed (Fase 2). Delegano la logica SRS pura a ``app.srs``."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
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


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


async def pick_warmup_words(
    session: AsyncSession,
    scenario_id: int,
    n_review: int = 5,
    n_new: int = 3,
    now: datetime | None = None,
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
                VocabProgress.state.in_([VocabState.seen, VocabState.used]),
                VocabProgress.next_review_at.is_not(None),
                VocabProgress.next_review_at <= now,
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
    review_pick = pick_due(review_candidates, now, n_review)

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
) -> list[dict]:
    """Coda flashcard: parole viste/usate con ``next_review_at`` scaduto, per priorità."""
    now = now or utcnow()
    rows = (
        await session.execute(
            select(VocabItem, VocabProgress)
            .join(VocabProgress, VocabProgress.vocab_item_id == VocabItem.id)
            .where(
                VocabProgress.state.in_([VocabState.seen, VocabState.used]),
                VocabProgress.next_review_at.is_not(None),
                VocabProgress.next_review_at <= now,
            )
        )
    ).all()
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
    picked = pick_due(candidates, now, limit)
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
    """Crea il vocabolo richiesto via ``[ ]`` (source=requested).

    Fase 2: il termine tedesco è un placeholder (= termine italiano); in Fase 3
    arriverà dall'agente LLM.
    """
    de = term
    item = await session.scalar(
        select(VocabItem).where(VocabItem.de == de, VocabItem.scenario_id == scenario_id)
    )
    if item is None:
        item = VocabItem(de=de, it=term, scenario_id=scenario_id, source=VocabSource.requested)
        session.add(item)
        await session.flush()
        session.add(VocabProgress(vocab_item_id=item.id, state=VocabState.new))
    return item


async def get_harvest_words(session: AsyncSession, lesson_id: int) -> list[dict]:
    """Parole dell'Ernte. Fase 2: solo le richieste via ``[ ]`` (errori e parole
    usate dall'agente arrivano in Fase 3 con Korrektor/harvest LLM)."""
    rows = (
        await session.scalars(
            select(Message.requested_words).where(
                Message.lesson_id == lesson_id,
                Message.role == MessageRole.user,
                Message.requested_words.is_not(None),
            )
        )
    ).all()
    words: list[dict] = []
    for rw in rows:
        for w in rw or []:
            words.append(
                {
                    "de": w.get("de"),
                    "it": w.get("it"),
                    "source": "requested",
                    "vocab_item_id": w.get("vocab_item_id"),
                }
            )
    return words


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
    harvest_words = None
    if lesson.current_phase == LessonPhase.harvest:
        harvest_words = await get_harvest_words(session, lesson.id)
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
        "warmup_words": warmup_words,
        "roleplay_messages": roleplay_messages,
        "dialogue_closed": dialogue_closed,
        "harvest_words": harvest_words,
        "requested_words_count": await count_requested_words(session, lesson.id),
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
