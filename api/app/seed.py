"""Seed idempotente del database.

Uso: ``python -m app.seed`` (o ``make seed``).
"""
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import SessionLocal
from app.models import Scenario, VocabItem, VocabProgress, VocabSource, VocabState
from app.seed_data import SCENARIOS, VOCAB


async def run_seed(
    session_factory: async_sessionmaker[AsyncSession] = SessionLocal,
) -> dict[str, int]:
    """Esegue il seed in modo idempotente; ritorna i conteggi inseriti.

    Non aggiorna le righe già esistenti: l'idempotenza è garantita dal
    controllo per-chiave (slug per gli scenari, ``de``+``scenario_id`` per i vocaboli).
    """
    created_scenarios = 0
    created_vocab = 0

    async with session_factory() as session:
        for s_data in SCENARIOS:
            existing = await session.scalar(select(Scenario).where(Scenario.slug == s_data["slug"]))
            if existing is None:
                session.add(Scenario(**s_data))
                created_scenarios += 1
        await session.commit()

        scenario_ids: dict[str, int] = {}
        for slug in {v["scenario_slug"] for v in VOCAB}:
            scenario_ids[slug] = await session.scalar(
                select(Scenario.id).where(Scenario.slug == slug)
            )

        for v_data in VOCAB:
            scenario_id = scenario_ids[v_data["scenario_slug"]]
            existing = await session.scalar(
                select(VocabItem).where(
                    VocabItem.de == v_data["de"],
                    VocabItem.scenario_id == scenario_id,
                )
            )
            if existing is None:
                item = VocabItem(
                    de=v_data["de"],
                    it=v_data["it"],
                    gender=v_data.get("gender"),
                    plural=v_data.get("plural"),
                    separable=v_data.get("separable", False),
                    example_de=v_data.get("example_de", ""),
                    scenario_id=scenario_id,
                    source=VocabSource.curated,
                )
                session.add(item)
                await session.flush()
                session.add(VocabProgress(vocab_item_id=item.id, state=VocabState.new))
                created_vocab += 1
        await session.commit()

    return {"scenarios": created_scenarios, "vocab": created_vocab}


async def main() -> None:
    counts = await run_seed()
    print(
        f"Seed completato: {counts['scenarios']} scenari creati, "
        f"{counts['vocab']} vocaboli creati."
    )


if __name__ == "__main__":
    asyncio.run(main())
