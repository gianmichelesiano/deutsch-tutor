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
    generated_vocab = sum(len(c.get("vocab", [])) for c in load_seed_content())
    assert after_first_vocab == 80 + generated_vocab


def _assert_valid_intro(intro: dict, slug: str) -> None:
    assert 5 <= len(intro["situation"]) <= 8, slug
    assert 4 <= len(intro["dialog"]) <= 6, slug
    assert 2 <= len(intro["notes_it"]) <= 3, slug
    for line in intro["situation"]:
        assert line["de"].strip() and line["it"].strip(), slug
    speakers = {t["speaker"] for t in intro["dialog"]}
    assert "Ich" in speakers and len(speakers) == 2, f"{slug}: speaker {speakers}"
    for turn in intro["dialog"]:
        assert turn["de"].strip() and turn["it"].strip(), slug
    for note in intro["notes_it"]:
        assert note.strip(), slug


def test_seed_content_files_cover_all_scenarios() -> None:
    """Scenari 1-2: solo intro (vocab e meta sono in seed_data). Scenari 3-12: contenuto completo."""
    contents = load_seed_content()
    slugs = {s["slug"]: s["week_number"] for s in SCENARIOS}
    weeks = sorted(c["week_number"] for c in contents)
    assert weeks == list(range(1, 13))
    for c in contents:
        assert slugs[c["slug"]] == c["week_number"]
        _assert_valid_intro(c["intro"], c["slug"])
        if c["week_number"] <= 2:
            assert "vocab" not in c and "key_phrases" not in c
            continue
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
