from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import services
from app.config import settings
from app.db import get_session
from app.models import ReviewResult, ReviewSource, VocabItem, VocabProgress
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
