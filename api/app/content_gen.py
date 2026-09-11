"""Generazione contenuti scenario (task 3.4) — CLI.

Genera key_phrases, vocab, imprevisti, swiss_variants e goals per uno scenario
(scenari 2–12), stampa il JSON per la revisione umana e, con ``--write``, lo
scrive nel DB (lo scenario deve essere già presente dal seed).

Uso (dentro il container, con LLM raggiungibile):
    python -m app.content_gen --scenario 2
    python -m app.content_gen --scenario 2 --write
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from types import SimpleNamespace

from sqlalchemy import select

from app import agents
from app.config import settings
from app.db import SessionLocal
from app.llm import RoutingLlmClient
from app.models import Scenario, VocabItem, VocabProgress, VocabSource, VocabState
from app.seed_data import SCENARIOS

VOCAB_TOTAL = 40
VOCAB_CHUNK = 20
META_ATTEMPTS = 3

# Marcatori tipici di Schweizerdeutsch: se compaiono nei campi in Hochdeutsch la
# risposta viene scartata e rigenerata (il modello tende a scivolare nel dialetto).
_DIALECT = re.compile(
    r"(?<![\w'])(isch|hesch|häsch|het|hät|händ|chömed|chunnsch|chunnt|chönd|chasch|"
    r"gaht|gah|öppis|nöd|nid|nüt|hüt|nonig|scho|zäme|mir\s+mached|mir\s+händ|luege|"
    r"eifach|susch|gsi|gha|cho|acho|au|d'|s'|z')(?!\w)",
    re.IGNORECASE,
)


def dialect_hits(content: dict) -> list[str]:
    """Frasi con marcatori dialettali nei campi che devono essere Hochdeutsch."""
    texts: list[str] = [content.get("role_label") or ""]
    texts += [kp.get("de", "") for kp in content.get("key_phrases", [])]
    texts += list(content.get("imprevisti", []))
    texts += list(content.get("goals", []))
    return [t for t in texts if _DIALECT.search(t)]


async def generate_meta(client: RoutingLlmClient, scenario: dict) -> dict:
    """Meta (role_label, key_phrases, imprevisti, swiss_variants, goals) con retry
    finché il risultato è in Hochdeutsch (max ``META_ATTEMPTS``)."""
    s = SimpleNamespace(**scenario)
    messages = agents.build_content_gen_meta_messages(s)
    last: dict = {}
    for _ in range(META_ATTEMPTS):
        last = await client.complete(
            "content_gen", messages, schema=agents.ContentGenMeta, max_tokens=4096
        )
        hits = dialect_hits(last)
        if not hits:
            return last
        # retry con feedback esplicito: il modello vede cosa ha sbagliato
        messages = messages + [
            {"role": "assistant", "content": json.dumps(last, ensure_ascii=False)},
            {
                "role": "user",
                "content": (
                    "Diese Sätze sind Schweizerdeutsch, nicht Hochdeutsch: "
                    + " · ".join(f"„{h}“" for h in hits)
                    + ". Schreibe das GANZE JSON neu, alle Felder ausser "
                    "swiss_variants.swiss auf Hochdeutsch (z.B. „wie geht's“ statt „wie gaht's“)."
                ),
            },
        ]
    raise RuntimeError(
        f"meta di «{scenario['title_de']}» ancora in dialetto dopo {META_ATTEMPTS} tentativi: "
        f"{dialect_hits(last)[:3]}"
    )


async def generate(client: RoutingLlmClient, scenario: dict) -> dict:
    """Genera il contenuto in più chiamate piccole (meno errori di JSON sul locale)."""
    s = SimpleNamespace(**scenario)
    meta = await generate_meta(client, scenario)
    vocab: list[dict] = []
    exclude: list[str] = []
    seen: set[str] = set()
    for offset in range(0, VOCAB_TOTAL, VOCAB_CHUNK):
        count = min(VOCAB_CHUNK, VOCAB_TOTAL - offset)
        chunk = await client.complete(
            "content_gen",
            agents.build_content_gen_vocab_messages(s, exclude, count),
            schema=agents.ContentGenVocabChunk,
            max_tokens=4096,
        )
        for item in chunk.get("vocab", []):
            de = item.get("de", "").strip()
            if not de or de in seen:
                continue
            seen.add(de)
            vocab.append(item)
            exclude.append(de)
        if not chunk.get("vocab"):
            break
    meta["vocab"] = vocab
    return meta


async def write_to_db(scenario: dict, content: dict) -> dict[str, int]:
    """Aggiorna lo scenario e inserisce i vocaboli curati (idempotente per slug)."""
    async with SessionLocal() as session:
        sc = await session.scalar(select(Scenario).where(Scenario.slug == scenario["slug"]))
        if sc is None:
            raise RuntimeError(f"scenario {scenario['slug']} non presente: esegui prima il seed")

        sc.role_label = content.get("role_label")
        sc.key_phrases = content.get("key_phrases", [])
        sc.swiss_variants = content.get("swiss_variants", [])
        sc.imprevisti = content.get("imprevisti", [])
        sc.goals = content.get("goals", [])

        created = 0
        for v in content.get("vocab", []):
            existing = await session.scalar(
                select(VocabItem).where(
                    VocabItem.de == v["de"], VocabItem.scenario_id == sc.id
                )
            )
            if existing is None:
                item = VocabItem(
                    de=v["de"],
                    it=v["it"],
                    gender=v.get("gender"),
                    plural=v.get("plural"),
                    separable=v.get("separable", False),
                    example_de=v.get("example_de", ""),
                    scenario_id=sc.id,
                    source=VocabSource.curated,
                )
                session.add(item)
                await session.flush()
                session.add(VocabProgress(vocab_item_id=item.id, state=VocabState.new))
                created += 1
        await session.commit()
        return {"vocab_created": created, "vocab_total": len(content.get("vocab", []))}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Genera il contenuto di uno scenario")
    parser.add_argument("--scenario", type=int, required=True, help="numero settimana (2..12)")
    parser.add_argument("--write", action="store_true", help="scrivi nel DB dopo conferma")
    args = parser.parse_args()

    scenario = next((s for s in SCENARIOS if s["week_number"] == args.scenario), None)
    if scenario is None:
        raise SystemExit(f"scenario {args.scenario} non trovato in seed_data")

    client = RoutingLlmClient(settings)
    content = await generate(client, scenario)
    print(json.dumps(content, ensure_ascii=False, indent=2))

    if args.write:
        answer = input("\nConfermi la scrittura nel DB? [y/N] ").strip().lower()
        if answer == "y":
            counts = await write_to_db(scenario, content)
            print(f"Scritto: {counts['vocab_created']}/{counts['vocab_total']} vocaboli creati.")
        else:
            print("Annullato.")


if __name__ == "__main__":
    asyncio.run(main())
