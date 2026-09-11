"""Demo: dialogo roleplay reale di 8 turni con il modello locale (scenario 1).

Uso (dentro il container, con il modello locale raggiungibile):
    LOCAL_LLM_BASE_URL=http://host.docker.internal:8008/v1 \
    LOCAL_LLM_MODEL=deepseek-v4-flash \
    python -m app.demo_roleplay

I messaggi utente sono scritti a livello A2 con qualche errore voluto.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app import agents
from app.config import settings
from app.llm import RoutingLlmClient
from app.parser import parse_requested_terms
from app.seed_data import SCENARIOS

USER_TURNS: list[str] = [
    "Grüezi, guten Tag. Ich brauche [uova].",
    "Ja, sechs Eier bitte. Und wo ist das Brot?",
    "Ich möchte auch der Zopf, aber ist heute ausverkauft?",
    "Okay, dann nehme ich die Baguette.",
    "Wie viel kostet das alles? Ich habe nur [contanti].",
    "Ich zahle mit Karte. Können Sie bitte einpacken das?",
    "Ja, eine Tüte brauche ich auch. Danke sehr.",
    "Danke für Ihre Hilfe. Auf Wiedersehen!",
]


async def main() -> None:
    scenario = SimpleNamespace(**SCENARIOS[0])
    client = RoutingLlmClient(settings)
    history: list[dict] = []
    scene_state: dict | None = None

    print(f"=== Rollenspiel «{scenario.title_de}» — modello locale {settings.local_llm_model} ===")
    print(f"=== Ruolo agente: {scenario.role_label} · livello A2/B1 · max {settings.max_roleplay_turns} turni ===")
    print("=== Ort: Zürich, Schweiz (Preise in Franken) ===\n")

    # apertura dell'agente
    opening = await client.complete(
        "roleplay",
        agents.build_roleplay_messages(scenario, [], scene_state=scene_state),
        schema=agents.RoleplayReply,
    )
    print(f"Agente:  {opening['text']}")
    history.append({"role": "agent", "content": opening["text"]})
    if opening.get("scene_state"):
        scene_state = opening["scene_state"]

    for turn in USER_TURNS:
        history.append({"role": "user", "content": turn})
        msgs = agents.build_roleplay_messages(scenario, history, scene_state=scene_state)
        reply = await client.complete("roleplay", msgs, schema=agents.RoleplayReply)
        print(f"\nUtente:  {turn}")
        terms = parse_requested_terms(turn)
        by_it = {t["it"].strip().lower(): t for t in reply.get("translations", [])}
        for term in terms:
            tr = by_it.get(term.strip().lower())
            if tr:
                print(f"         ↳ richiesto: {term} → {tr['lemma']} (nel contesto: {tr['de_in_context']})")
            else:
                print(f"         ↳ richiesto: {term} → (non fornito)")
        print(f"Agente:  {reply['text']}")
        history.append({"role": "agent", "content": reply["text"]})
        if reply.get("scene_state"):
            scene_state = reply["scene_state"]
        if reply.get("dialogue_closed"):
            print("\n[il dialogo è stato chiuso dall'agente]")
            break

    print("\n=== Stato finale della scena ===")
    print(agents.format_scene_state(scene_state))
    print("\n=== fine demo ===")


if __name__ == "__main__":
    asyncio.run(main())
