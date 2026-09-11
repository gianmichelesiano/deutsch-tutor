"""Seed idempotente del database.

Uso:
- ``python -m app.seed``            → crea le righe mancanti (idempotente)
- ``python -m app.seed --update``   → crea + sovrascrive i contenuti degli scenari esistenti

Fonti dei contenuti:
- ``seed_data.SCENARIOS`` / ``seed_data.VOCAB``: scenari 1–2 curati a mano.
- ``seed_content/scenario-NN.json``: scenari 3–12 generati con ``app.content_gen``
  e rivisti; stesso formato dell'output del generatore più ``slug``/``week_number``.
"""
import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import SessionLocal
from app.models import Scenario, VocabItem, VocabProgress, VocabSource, VocabState
from app.seed_data import SCENARIOS, VOCAB

# Campi di contenuto dello scenario sovrascritti da --update (slug e week_number sono identità).
CONTENT_FIELDS = (
    "title_de",
    "title_it",
    "description",
    "role_label",
    "key_phrases",
    "swiss_variants",
    "imprevisti",
    "goals",
)
# Campi forniti dai JSON generati (non toccano titoli/descrizione del seed).
GENERATED_FIELDS = ("role_label", "key_phrases", "swiss_variants", "imprevisti", "goals")

SEED_CONTENT_DIR = Path(__file__).parent / "seed_content"


def load_seed_content(directory: Path = SEED_CONTENT_DIR) -> list[dict]:
    """Carica i JSON ``scenario-NN.json`` (ordinati per nome)."""
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("scenario-*.json"))
    ]


def _has_content(scenario: Scenario) -> bool:
    return bool(scenario.key_phrases or scenario.goals or scenario.imprevisti)


async def run_seed(
    session_factory: async_sessionmaker[AsyncSession] = SessionLocal,
    update: bool = False,
) -> dict[str, int]:
    """Esegue il seed in modo idempotente; ritorna i conteggi.

    - Scenari: check-by-``slug``; con ``update=True`` i campi di contenuto degli
      scenari esistenti vengono sovrascritti (per il Planer, task 3.4).
    - Vocaboli: check-by-(``de``, ``scenario_id``); mai sovrascritti.
    """
    created_scenarios = 0
    updated_scenarios = 0
    created_vocab = 0

    async with session_factory() as session:
        for s_data in SCENARIOS:
            existing = await session.scalar(select(Scenario).where(Scenario.slug == s_data["slug"]))
            if existing is None:
                session.add(Scenario(**s_data))
                created_scenarios += 1
            elif update:
                for field in CONTENT_FIELDS:
                    setattr(existing, field, s_data[field])
                updated_scenarios += 1
        await session.commit()

        # Contenuti generati (scenari 3–12): applicati se lo scenario è ancora vuoto
        # oppure con --update.
        generated = load_seed_content()
        vocab_rows = list(VOCAB)
        for content in generated:
            scenario = await session.scalar(select(Scenario).where(Scenario.slug == content["slug"]))
            if scenario is None:
                continue
            if update or not _has_content(scenario):
                for field in GENERATED_FIELDS:
                    setattr(scenario, field, content.get(field))
                updated_scenarios += 1
            vocab_rows.extend({"scenario_slug": content["slug"], **v} for v in content.get("vocab", []))
        await session.commit()

        scenario_ids: dict[str, int] = {}
        for slug in {v["scenario_slug"] for v in vocab_rows}:
            scenario_ids[slug] = await session.scalar(
                select(Scenario.id).where(Scenario.slug == slug)
            )

        for v_data in vocab_rows:
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

    return {
        "scenarios": created_scenarios,
        "scenarios_updated": updated_scenarios,
        "vocab": created_vocab,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed del database Deutsch-Tutor")
    parser.add_argument(
        "--update",
        action="store_true",
        help="sovrascrive key_phrases/swiss_variants/imprevisti/goals degli scenari esistenti",
    )
    args = parser.parse_args()

    counts = await run_seed(update=args.update)
    print(
        f"Seed completato: {counts['scenarios']} scenari creati, "
        f"{counts['scenarios_updated']} aggiornati, {counts['vocab']} vocaboli creati."
    )


if __name__ == "__main__":
    asyncio.run(main())
