from fastapi import APIRouter, FastAPI

from app.config import settings

app = FastAPI(title="Deutsch-Tutor API", version="0.1.0")

router = APIRouter(prefix=settings.api_prefix)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(router)
