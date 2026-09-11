"""Demo: agente Warm-up (3.2) su 10 casi della lezione pilota, modello locale."""
from __future__ import annotations

import asyncio

from app import agents
from app.config import settings
from app.llm import RoutingLlmClient

CASES: list[tuple[str, str, str]] = [
    ("abwiegen", "pesare (separabile)", "Ich abwiege die Banane."),
    ("das Bier", "la birra", "Die Bier ist ausverkauft."),
    ("die Äpfel", "le mele", "Ich kaufe der Äpfel."),
    ("das Bier", "la birra", "Ich brauche zwei Bier."),
    ("mit Karte", "con carta", "Ich möchte bezahlen mit Karte."),
    ("gleich da drüben", "proprio lì", "Die Kasse ist gleich da drüben."),
    ("sechs Eier", "sei uova", "Ich hätte gern sechs Eier."),
    ("ausverkauft", "esaurito", "Der Zopf ist ausverkauft."),
    ("das Baguette", "la baguette", "Ich nehme die Baguette."),
    ("einpacken", "imballare (separabile)", "Können Sie das bitte einpacken das?"),
]


async def main() -> None:
    client = RoutingLlmClient(settings)
    print(f"=== Demo Warm-up — modello locale {settings.local_llm_model} ===\n")
    for i, (de, it, sentence) in enumerate(CASES, 1):
        msgs = agents.build_warmup_messages(de, it, sentence)
        out = await client.complete("warmup_feedback", msgs, schema=agents.WarmupFeedback)
        print(f"{i:2}. «{sentence}»  ({de})")
        print(f"    corretto={out['is_correct']}  tipo={out['error_type']}  → {out['feedback_it']}")
        if out.get("corrected_sentence"):
            print(f"    correzione: {out['corrected_sentence']}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
