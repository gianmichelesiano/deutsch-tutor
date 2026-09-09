from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import services
from app.config import settings
from app.db import get_session

router = APIRouter(prefix=settings.api_prefix, tags=["progress"])


@router.get("/progress")
async def progress(session: AsyncSession = Depends(get_session)):
    return await services.compute_progress(session, services.utcnow())


@router.get("/home")
async def home(session: AsyncSession = Depends(get_session)):
    return await services.compute_home(session, services.utcnow())
