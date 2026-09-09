from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import lesson_state, services
from app.config import settings
from app.db import get_session
from app.deps import get_llm
from app.llm import LlmClient
from app.models import (
    Lesson,
    LessonPhase,
    LessonStatus,
    Message,
    MessageRole,
    ReviewResult,
    ReviewSource,
    UserSentence,
    VocabItem,
    VocabState,
)
from app.parser import parse_requested_terms
from app.schemas import (
    AdvanceIn,
    HarvestConfirmIn,
    LessonDetail,
    RoleplayMessageIn,
    RoleplayMessageOut,
    WarmupAnswerIn,
    WarmupAnswerOut,
)
from app.services import build_lesson_detail, utcnow

router = APIRouter(prefix=settings.api_prefix, tags=["lessons"])


@router.post("/lessons", response_model=LessonDetail)
async def create_lesson(session: AsyncSession = Depends(get_session)):
    current = await services.get_current_lesson(session)
    if current is not None:
        return await build_lesson_detail(session, current)

    scenario, lesson_type = await services.plan_next_lesson(session)
    lesson = Lesson(
        scenario_id=scenario.id,
        lesson_type=lesson_type,
        status=LessonStatus.in_progress,
        current_phase=LessonPhase.warmup,
        summary={},
    )
    session.add(lesson)
    await session.commit()
    return await build_lesson_detail(session, lesson)


@router.get("/lessons/current")
async def current_lesson(session: AsyncSession = Depends(get_session)):
    current = await services.get_current_lesson(session)
    if current is None:
        return {"lesson": None}
    return {"lesson": await build_lesson_detail(session, current)}


@router.get("/lessons/{lesson_id}", response_model=LessonDetail)
async def get_lesson(lesson_id: int, session: AsyncSession = Depends(get_session)):
    lesson = await services.get_lesson_or_404(session, lesson_id)
    return await build_lesson_detail(session, lesson)


@router.post("/lessons/{lesson_id}/advance", response_model=LessonDetail)
async def advance_lesson(
    lesson_id: int,
    body: AdvanceIn = AdvanceIn(),
    session: AsyncSession = Depends(get_session),
    llm: LlmClient = Depends(get_llm),
):
    lesson = await services.get_lesson_or_404(session, lesson_id)
    if lesson.status == LessonStatus.completed:
        raise HTTPException(status_code=400, detail="lezione già completata")
    if lesson.current_phase is None:
        raise HTTPException(status_code=400, detail="lezione senza fase corrente")

    try:
        new_phase = lesson_state.advance_phase(lesson.current_phase.value, skip_swiss=body.skip_swiss)
    except lesson_state.InvalidTransition as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if new_phase == "completed":
        lesson.status = LessonStatus.completed
        lesson.ended_at = utcnow()
        lesson.current_phase = None
    else:
        lesson.current_phase = LessonPhase(new_phase)
        if new_phase == "roleplay":
            has_msgs = await session.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.lesson_id == lesson.id, Message.phase == LessonPhase.roleplay)
            )
            if not has_msgs:
                reply = await llm.complete(
                    "roleplay", [{"role": "system", "content": "Starte das Rollenspiel."}]
                )
                session.add(
                    Message(
                        lesson_id=lesson.id,
                        phase=LessonPhase.roleplay,
                        role=MessageRole.agent,
                        content=reply["text"],
                    )
                )

    await session.commit()
    return await build_lesson_detail(session, lesson)


@router.post("/lessons/{lesson_id}/warmup/answer", response_model=WarmupAnswerOut)
async def warmup_answer(
    lesson_id: int,
    body: WarmupAnswerIn,
    session: AsyncSession = Depends(get_session),
    llm: LlmClient = Depends(get_llm),
):
    lesson = await services.get_lesson_or_404(session, lesson_id)
    if lesson.current_phase != LessonPhase.warmup:
        raise HTTPException(status_code=400, detail="la lezione non è in fase warmup")
    vocab = await session.get(VocabItem, body.vocab_item_id)
    if vocab is None:
        raise HTTPException(status_code=404, detail="vocabolo non trovato")

    feedback = await llm.complete(
        "warmup_feedback", [{"role": "user", "content": body.sentence}]
    )
    is_correct = bool(feedback["is_correct"])

    session.add(
        UserSentence(
            vocab_item_id=body.vocab_item_id,
            lesson_id=lesson.id,
            sentence=body.sentence,
            is_correct=is_correct,
            feedback=feedback.get("feedback_it", ""),
        )
    )
    result = ReviewResult.correct if is_correct else ReviewResult.wrong
    await services.apply_review_event(
        session,
        body.vocab_item_id,
        result,
        utcnow(),
        ReviewSource.warmup,
        lesson.id,
        counts_for_consolidation=True,
    )
    await session.commit()

    return WarmupAnswerOut(
        vocab_item_id=body.vocab_item_id,
        is_correct=is_correct,
        corrected_sentence=feedback.get("corrected_sentence"),
        feedback_it=feedback.get("feedback_it", ""),
        error_type=feedback.get("error_type", "none"),
    )


@router.post("/lessons/{lesson_id}/roleplay/message", response_model=RoleplayMessageOut)
async def roleplay_message(
    lesson_id: int,
    body: RoleplayMessageIn,
    session: AsyncSession = Depends(get_session),
    llm: LlmClient = Depends(get_llm),
):
    lesson = await services.get_lesson_or_404(session, lesson_id)
    if lesson.current_phase != LessonPhase.roleplay:
        raise HTTPException(status_code=400, detail="la lezione non è in fase roleplay")

    terms = parse_requested_terms(body.content)
    requested = []
    for term in terms:
        item = await services.get_or_create_requested_vocab(session, lesson.scenario_id, term)
        requested.append({"it": term, "de": item.de, "vocab_item_id": item.id})

    history = await services.roleplay_history(session, lesson.id)
    history.append({"role": "user", "content": body.content})
    reply = await llm.complete("roleplay", history)

    session.add(
        Message(
            lesson_id=lesson.id,
            phase=LessonPhase.roleplay,
            role=MessageRole.user,
            content=body.content,
            requested_words=requested or None,
        )
    )
    session.add(
        Message(
            lesson_id=lesson.id,
            phase=LessonPhase.roleplay,
            role=MessageRole.agent,
            content=reply["text"],
        )
    )
    if reply.get("dialogue_closed"):
        lesson.summary = {**(lesson.summary or {}), "dialogue_closed": True}
    await session.commit()

    return RoleplayMessageOut(
        agent_text=reply["text"],
        dialogue_closed=bool(reply.get("dialogue_closed")),
        requested_words=requested,
    )


@router.post("/lessons/{lesson_id}/harvest/confirm")
async def harvest_confirm(
    lesson_id: int,
    body: HarvestConfirmIn,
    session: AsyncSession = Depends(get_session),
):
    lesson = await services.get_lesson_or_404(session, lesson_id)
    if lesson.current_phase != LessonPhase.harvest:
        raise HTTPException(status_code=400, detail="la lezione non è in fase harvest")

    all_words = await services.get_harvest_words(session, lesson.id)
    confirmed = set(body.vocab_item_ids)
    now = utcnow()
    for w in all_words:
        vid = w.get("vocab_item_id")
        if vid is None:
            continue
        progress = await services.get_or_create_progress(session, vid)
        if vid in confirmed:
            if progress.state == VocabState.new:
                progress.state = VocabState.seen
                progress.next_review_at = now
        else:
            # deselezionata = già nota → esce dal ripasso
            progress.state = VocabState.consolidated
    await session.commit()
    return {"confirmed": len(confirmed)}


@router.post("/lessons/{lesson_id}/abandon")
async def abandon_lesson(lesson_id: int, session: AsyncSession = Depends(get_session)):
    lesson = await services.get_lesson_or_404(session, lesson_id)
    if lesson.status == LessonStatus.completed:
        raise HTTPException(status_code=400, detail="lezione già completata")
    lesson.status = LessonStatus.abandoned
    lesson.ended_at = utcnow()
    lesson.current_phase = None
    await session.commit()
    return {"status": "abandoned"}
