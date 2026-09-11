from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import services
from app.config import settings
from app.db import get_session
from app.models import ReviewResult, ReviewSource, UserSentence, VocabItem, VocabProgress
from app.schemas import ReviewIn, ReviewOut, ReviewQueueItem, VocabItemOut

router = APIRouter(prefix=settings.api_prefix, tags=["vocab"])


@router.get("/vocab", response_model=list[VocabItemOut])
async def list_vocab(session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(
            select(VocabItem, VocabProgress)
            .join(VocabProgress, VocabProgress.vocab_item_id == VocabItem.id)
            .order_by(VocabItem.id)
        )
    ).all()
    return [
        VocabItemOut(
            id=vi.id,
            de=vi.de,
            it=vi.it,
            state=vp.state.value,
            gender=vi.gender,
            plural=vi.plural,
            separable=vi.separable,
            example_de=vi.example_de,
            next_review_at=vp.next_review_at,
        )
        for vi, vp in rows
    ]


@router.get("/vocab/review-queue", response_model=list[ReviewQueueItem])
async def review_queue(session: AsyncSession = Depends(get_session)):
    words = await services.pick_flashcard_queue(session, limit=20)
    return [ReviewQueueItem(**w) for w in words]


@router.get("/vocab/{vocab_id}")
async def get_vocab(vocab_id: int, session: AsyncSession = Depends(get_session)):
    vocab = await session.get(VocabItem, vocab_id)
    if vocab is None:
        raise HTTPException(status_code=404, detail="vocabolo non trovato")
    progress = await session.get(VocabProgress, vocab_id)
    sentences = (
        await session.scalars(
            select(UserSentence)
            .where(UserSentence.vocab_item_id == vocab_id)
            .order_by(UserSentence.created_at.desc())
            .limit(10)
        )
    ).all()
    return {
        "id": vocab.id,
        "de": vocab.de,
        "it": vocab.it,
        "gender": vocab.gender,
        "plural": vocab.plural,
        "separable": vocab.separable,
        "example_de": vocab.example_de,
        "state": progress.state.value if progress else "new",
        "next_review_at": progress.next_review_at if progress else None,
        "user_sentences": [
            {"sentence": s.sentence, "is_correct": s.is_correct, "feedback": s.feedback}
            for s in sentences
        ],
    }


@router.post("/vocab/{vocab_id}/review", response_model=ReviewOut)
async def review_vocab(
    vocab_id: int,
    body: ReviewIn,
    session: AsyncSession = Depends(get_session),
):
    if body.result not in ("correct", "wrong"):
        raise HTTPException(status_code=422, detail="result deve essere 'correct' o 'wrong'")
    vocab = await session.get(VocabItem, vocab_id)
    if vocab is None:
        raise HTTPException(status_code=404, detail="vocabolo non trovato")

    result = ReviewResult(body.result)
    progress = await services.apply_review_event(
        session,
        vocab_id,
        result,
        services.utcnow(),
        ReviewSource.flashcard,
        None,
        counts_for_consolidation=False,
    )
    await session.commit()
    return ReviewOut(id=vocab_id, state=progress.state.value, next_review_at=progress.next_review_at)
