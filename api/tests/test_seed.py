import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Scenario, VocabItem
from app.seed import run_seed

pytestmark = pytest.mark.integration


async def _count(model) -> int:
    async with SessionLocal() as session:
        result = await session.execute(select(func.count()).select_from(model))
        return result.scalar_one()


@pytest.mark.asyncio
async def test_seed_is_idempotent() -> None:
    await run_seed()
    after_first_scenarios = await _count(Scenario)
    after_first_vocab = await _count(VocabItem)

    await run_seed()
    after_second_scenarios = await _count(Scenario)
    after_second_vocab = await _count(VocabItem)

    # Idempotenza: la seconda esecuzione non cambia nulla.
    assert after_first_scenarios == after_second_scenarios
    assert after_first_vocab == after_second_vocab

    # Contenuto atteso.
    assert after_first_scenarios == 12
    assert after_first_vocab == 40
