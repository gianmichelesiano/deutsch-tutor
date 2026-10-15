from fastapi import FastAPI

from app.config import settings
from app.routers import deck, lessons, progress, vocab

app = FastAPI(title="Deutsch-Tutor API", version="0.2.0")

app.include_router(lessons.router)
app.include_router(vocab.router)
app.include_router(progress.router)
app.include_router(deck.router)


@app.get(f"{settings.api_prefix}/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
