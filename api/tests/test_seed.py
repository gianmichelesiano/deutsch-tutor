import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Scenario, VocabItem
from app.seed import load_seed_content, run_seed
from app.seed_data import SCENARIOS

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

    # Contenuto atteso: 40 scenario 1 + 40 scenario 2 + i JSON generati.
    assert after_first_scenarios == 12
    generated_vocab = sum(len(c["vocab"]) for c in load_seed_content())
    assert after_first_vocab == 80 + generated_vocab


def test_seed_content_files_cover_scenarios_3_to_12() -> None:
    """I JSON generati devono essere validi e coprire gli scenari 3–12."""
    contents = load_seed_content()
    slugs = {s["slug"]: s["week_number"] for s in SCENARIOS}
    weeks = sorted(c["week_number"] for c in contents)
    assert weeks == list(range(3, 13))
    for c in contents:
        assert slugs[c["slug"]] == c["week_number"]
        assert c["role_label"]
        assert len(c["key_phrases"]) >= 8
        assert len(c["imprevisti"]) >= 3
        assert len(c["swiss_variants"]) >= 1
        assert len(c["goals"]) >= 3
        assert 30 <= len(c["vocab"]) <= 45, c["slug"]
        des = [v["de"] for v in c["vocab"]]
        assert len(des) == len(set(des)), f"vocab duplicati in {c['slug']}"
        for v in c["vocab"]:
            assert v["de"].strip() and v["it"].strip() and v["example_de"].strip()
