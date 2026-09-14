import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import agents, korrektor, lesson_state, services
from app.config import settings
from app.db import get_session
from app.deps import get_llm
from app.llm import LlmClient
from app.models import (
    Lesson,
    LessonPhase,
    LessonStatus,
    LessonType,
    Message,
    MessageRole,
    ReviewResult,
    ReviewSource,
    Scenario,
    UserSentence,
    VocabItem,
    VocabState,
)
from app.parser import parse_requested_terms
from app.schemas import (
    AdvanceIn,
    HarvestConfirmIn,
    LessonCreateIn,
    LessonDetail,
    RoleplayMessageIn,
    RoleplayMessageOut,
    TestAnswerIn,
    TestAnswerOut,
    WarmupAnswerIn,
    WarmupAnswerOut,
)
from app.services import build_lesson_detail, utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix=settings.api_prefix, tags=["lessons"])


@router.post("/lessons", response_model=LessonDetail)
async def create_lesson(
    body: LessonCreateIn = LessonCreateIn(), session: AsyncSession = Depends(get_session)
):
    current = await services.get_current_lesson(session)
    if current is not None:
        return await build_lesson_detail(session, current)

    if body.scenario_id is not None:
        # selezione manuale dal Percorso: tutti gli scenari sono sbloccati, salta il Planer
        scenario = await session.get(Scenario, body.scenario_id)
        if scenario is None:
            raise HTTPException(status_code=404, detail="scenario non trovato")
        lesson_type = LessonType.base
    else:
        scenario, lesson_type = await services.plan_next_lesson(session)
    lesson = Lesson(
        scenario_id=scenario.id,
        lesson_type=lesson_type,
        status=LessonStatus.in_progress,
        current_phase=LessonPhase(lesson_state.first_phase(lesson_type.value)),
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
        new_phase = lesson_state.advance_phase(
            lesson.current_phase.value, lesson_type=lesson.lesson_type.value, skip_swiss=body.skip_swiss
        )
    except lesson_state.InvalidTransition as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if new_phase == "completed":
        lesson.status = LessonStatus.completed
        lesson.ended_at = utcnow()
        lesson.current_phase = None
        # Planer (cloud): riassunto della lezione (parole nuove, errori, raccomandazione)
        try:
            scenario = await session.get(Scenario, lesson.scenario_id)
            data = await services.gather_planner_data(session, lesson.id)
            planner = await llm.complete(
                "planner",
                agents.build_planner_messages(scenario, data),
                schema=agents.PlannerOutput,
                session=session,
            )
            summary = dict(lesson.summary or {})
            summary["new_words"] = planner.get("new_words", [])
            summary["recurring_errors"] = planner.get("recurring_errors", [])
            summary["recommendation"] = planner.get("recommendation", "")
            lesson.summary = summary
        except Exception:  # il Planer non deve bloccare il completamento
            logger.exception("Planer fallito per la lezione %s", lesson.id)
    else:
        if new_phase == "harvest":
            # attende i Korrektor pendenti della lezione prima di leggere le correzioni
            await korrektor.wait_pending(lesson.id)
        lesson.current_phase = LessonPhase(new_phase)
        if new_phase == "roleplay":
            has_msgs = await session.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.lesson_id == lesson.id, Message.phase == LessonPhase.roleplay)
            )
            if not has_msgs:
                scenario = await session.get(Scenario, lesson.scenario_id)
                msgs = agents.build_roleplay_messages(
                    scenario, [], max_turns=settings.max_roleplay_turns
                )
                reply = await llm.complete(
                    "roleplay", msgs, schema=agents.RoleplayReply, session=session
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
        "warmup_feedback",
        agents.build_warmup_messages(vocab.de, vocab.it, body.sentence),
        schema=agents.WarmupFeedback,
        session=session,
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
    scenario = await session.get(Scenario, lesson.scenario_id)

    # 1. Parser deterministico per [ ] → vocab_items(source=requested), placeholder DE
    terms = parse_requested_terms(body.content)
    requested = []
    for term in terms:
        item = await services.get_or_create_requested_vocab(session, lesson.scenario_id, term)
        requested.append({"it": term, "de": item.de, "vocab_item_id": item.id})

    # 2. Stato della scena precedente (dallo summary) → iniettato nel prompt
    prev_scene = (lesson.summary or {}).get("scene_state")

    # 3. Gesprächspartner (locale) con ultimi turni + stato della scena
    history = await services.roleplay_history(session, lesson.id)
    user_turns = sum(1 for m in history if m["role"] == "user") + 1
    react = await services.last_user_incomprehensible(session, lesson.id)
    msgs = agents.build_roleplay_messages(
        scenario,
        [*history, {"role": "user", "content": body.content}],
        max_turns=settings.max_roleplay_turns,
        react_incomprehensible=react,
        scene_state=prev_scene,
    )
    reply = await llm.complete(
        "roleplay", msgs, schema=agents.RoleplayReply, session=session
    )

    # 4. Sostituisce il placeholder DE con il lemma fornito dall'agente
    translations = {t.get("it", "").strip().lower(): t for t in reply.get("translations", [])}
    for r in requested:
        tr = translations.get(r["it"].strip().lower())
        if tr and tr.get("lemma"):
            item = await session.get(VocabItem, r["vocab_item_id"])
            if item is not None and services.is_placeholder_de(item):
                item.de = tr["lemma"].strip()
                r["de"] = item.de

    # 5. Chiusura forzata dopo max_turns
    dialogue_closed = bool(reply.get("dialogue_closed")) or user_turns >= settings.max_roleplay_turns

    user_msg = Message(
        lesson_id=lesson.id,
        phase=LessonPhase.roleplay,
        role=MessageRole.user,
        content=body.content,
        requested_words=requested or None,
    )
    session.add(user_msg)
    await session.flush()

    session.add(
        Message(
            lesson_id=lesson.id,
            phase=LessonPhase.roleplay,
            role=MessageRole.agent,
            content=reply["text"],
        )
    )

    summary = dict(lesson.summary or {})
    if reply.get("scene_state"):
        summary["scene_state"] = reply["scene_state"]
    if dialogue_closed:
        summary["dialogue_closed"] = True
    lesson.summary = summary
    await session.commit()

    # 6. Korrektor (cloud) in background: non blocca la risposta del roleplay
    korrektor.schedule(
        korrektor.run(
            lesson.id,
            user_msg.id,
            lesson.scenario_id,
            body.content,
            reply["text"],
            llm,
        ),
        lesson.id,
    )

    return RoleplayMessageOut(
        agent_text=reply["text"],
        dialogue_closed=dialogue_closed,
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

    all_words = (
        await services.get_test_harvest_words(session, lesson.id)
        if lesson.lesson_type == LessonType.review
        else await services.get_harvest_words(session, lesson.id)
    )
    confirmed = set(body.vocab_item_ids)
    now = utcnow()
    for w in all_words:
        vid = w.get("vocab_item_id")
        if vid is None:
            continue
        vocab = await session.get(VocabItem, vid)
        if vocab is None or services.is_placeholder_de(vocab):
            # un placeholder non può essere confermato in harvest (manca il termine DE)
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


@router.post("/lessons/{lesson_id}/test/answer", response_model=TestAnswerOut)
async def test_answer(
    lesson_id: int,
    body: TestAnswerIn,
    session: AsyncSession = Depends(get_session),
):
    lesson = await services.get_lesson_or_404(session, lesson_id)
    if lesson.current_phase != LessonPhase.test:
        raise HTTPException(status_code=400, detail="la lezione non è in fase test")
    vocab = await session.get(VocabItem, body.vocab_item_id)
    if vocab is None:
        raise HTTPException(status_code=404, detail="vocabolo non trovato")

    is_correct = services.lemma_of(body.answer) == services.lemma_of(vocab.de)
    result = ReviewResult.correct if is_correct else ReviewResult.wrong
    await services.apply_review_event(
        session,
        body.vocab_item_id,
        result,
        utcnow(),
        ReviewSource.test,
        lesson.id,
        counts_for_consolidation=True,
    )
    await session.commit()
    return TestAnswerOut(
        vocab_item_id=body.vocab_item_id,
        is_correct=is_correct,
        correct_de=vocab.de,
        it=vocab.it,
    )


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


@router.post("/lessons/{lesson_id}/back", response_model=LessonDetail)
async def back_lesson(lesson_id: int, session: AsyncSession = Depends(get_session)):
    lesson = await services.get_lesson_or_404(session, lesson_id)
    if lesson.current_phase is None:
        raise HTTPException(status_code=400, detail="lezione senza fase corrente")
    try:
        new_phase = lesson_state.back_phase(lesson.current_phase.value)
    except lesson_state.InvalidTransition as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    lesson.current_phase = LessonPhase(new_phase)
    await session.commit()
    return await build_lesson_detail(session, lesson)
