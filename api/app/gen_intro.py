"""Genera l'Einstieg (``intro``) per gli scenari e lo scrive nei JSON del seed.

Uso (nel container, con LLM raggiungibile):
    python -m app.gen_intro              # tutti gli scenari 1-12 senza intro
    python -m app.gen_intro --scenario 5 # uno solo (sovrascrive)
    python -m app.gen_intro --force      # rigenera tutti
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.config import settings
from app.content_gen import generate_intro
from app.llm import RoutingLlmClient
from app.seed import SEED_CONTENT_DIR
from app.seed_data import SCENARIOS


def _path(week: int) -> Path:
    return SEED_CONTENT_DIR / f"scenario-{week:02d}.json"


def _load(week: int, scenario: dict) -> dict:
    path = _path(week)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"slug": scenario["slug"], "week_number": week}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Genera l'Einstieg degli scenari")
    parser.add_argument("--scenario", type=int, help="numero settimana (1..12); default: tutti")
    parser.add_argument("--force", action="store_true", help="rigenera anche se intro esiste")
    args = parser.parse_args()

    settings.llm_timeout_seconds = 600
    client = RoutingLlmClient(settings)
    weeks = [args.scenario] if args.scenario else [s["week_number"] for s in SCENARIOS]
    for week in weeks:
        scenario = next(s for s in SCENARIOS if s["week_number"] == week)
        content = _load(week, scenario)
        if content.get("intro") and not args.force and not args.scenario:
            print(f"[{week}] intro già presente, salto")
            continue
        role = content.get("role_label") or scenario.get("role_label") or "Gesprächspartner"
        intro = await generate_intro(client, {**scenario, "role_label": role})
        content["intro"] = intro
        _path(week).write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"[{week}] {scenario['title_de']}: situation={len(intro['situation'])} "
            f"dialog={len(intro['dialog'])} notes={len(intro['notes_it'])}",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
