"""Layer LLM — interfaccia unica + mock per Fase 2.

In Fase 3 questo modulo diventa il routing locale/cloud per task (task 3.1);
per ora espone un ``MockLlmClient`` deterministico usato dai test di
integrazione e dal flusso senza LLM reale.
"""
from __future__ import annotations

from typing import Any


class LlmClient:
    """Interfaccia unica per le chiamate LLM (task 3.1)."""

    async def complete(self, task: str, messages: list[dict], schema: Any = None) -> Any:
        raise NotImplementedError


class MockLlmClient(LlmClient):
    """Mock deterministico.

    - ``warmup_feedback``: risposta sempre corretta (tono asciutto).
    - ``roleplay``: risposta fissa; il dialogo si chiude dopo ``close_after_turns``
      messaggi dell'utente (contati dalla cronologia passata in ``messages``).
    """

    def __init__(self, close_after_turns: int = 4):
        self.close_after_turns = close_after_turns

    async def complete(self, task: str, messages: list[dict], schema: Any = None) -> Any:
        if task == "warmup_feedback":
            return {
                "is_correct": True,
                "corrected_sentence": None,
                "feedback_it": "Ok.",
                "error_type": "none",
            }
        if task == "roleplay":
            user_turns = sum(1 for m in messages if m["role"] == "user")
            closed = user_turns >= self.close_after_turns
            if user_turns == 0:
                text = "Grüezi! Kann ich Ihnen helfen?"
            elif closed:
                text = "Auf Wiedersehen und einen schönen Tag!"
            else:
                text = "Gerne! Darf es sonst noch etwas sein?"
            return {"text": text, "dialogue_closed": closed}
        raise NotImplementedError(f"mock: task '{task}' non implementato")
