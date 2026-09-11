"""Korrektor asincrono (task 3.3).

Il Korrektor (cloud) viene eseguito in background così da non bloccare la risposta
del roleplay (che dipende solo dal Gesprächspartner locale). I task sono registrati
per lezione e l'avanzamento verso harvest attende il loro completamento.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from app import agents, services
from app.config import settings
from app.db import SessionLocal
from app.llm import LlmClient
from app.models import Message, Scenario

logger = logging.getLogger(__name__)

_pending: dict[int, set[asyncio.Task]] = defaultdict(set)


def schedule(coro, lesson_id: int) -> None:
    """Programma il task in background e lo registra per la lezione."""
    task = asyncio.create_task(coro)
    _pending[lesson_id].add(task)
    task.add_done_callback(lambda t, lid=lesson_id: _pending[lid].discard(t))


async def wait_pending(lesson_id: int, timeout: float | None = None) -> None:
    """Attende il completamento dei Korrektor pendenti della lezione (best-effort)."""
    tasks = list(_pending.get(lesson_id, ()))
    if not tasks:
        return
    timeout = timeout if timeout is not None else settings.llm_timeout_seconds
    await asyncio.wait(tasks, timeout=timeout)
    _pending.pop(lesson_id, None)


async def run(
    lesson_id: int,
    message_id: int,
    scenario_id: int,
    user_text: str,
    agent_text: str,
    llm: LlmClient,
) -> None:
    """Esegue il Korrektor e salva il risultato su ``Message.corrections`` del turno."""
    try:
        async with SessionLocal() as session:
            scenario = await session.get(Scenario, scenario_id)
            if scenario is None:
                return
            corr = await llm.complete(
                "corrector",
                agents.build_corrector_messages(scenario, user_text, agent_text),
                schema=agents.CorrectorReply,
                session=session,
            )
            enriched_errors = []
            for e in corr.get("errors", []):
                vid, vit = await services.match_error_vocab(session, e.get("fix", ""))
                enriched_errors.append(
                    {**e, "vocab_item_id": vid, "it": vit.it if vit else None}
                )
                if vid is not None:
                    await services.downgrade_consolidated_on_error(session, vid, services.utcnow())

            new_words = []
            for nw in corr.get("new_words_from_agent", []):
                try:
                    item = await services.get_or_create_agent_used_vocab(
                        session, scenario_id, nw.get("de", ""), nw.get("it", "")
                    )
                    new_words.append(
                        {"de": nw.get("de"), "it": nw.get("it"), "vocab_item_id": item.id}
                    )
                except ValueError:
                    continue

            msg = await session.get(Message, message_id)
            if msg is not None:
                msg.corrections = {
                    "comprehensible": corr.get("comprehensible", True),
                    "errors": enriched_errors,
                    "new_words_from_agent": new_words,
                }
            await session.commit()
    except Exception:  # il Korrektor non deve mai far fallire il dialogo
        logger.exception("Korrektor fallito per il messaggio %s della lezione %s", message_id, lesson_id)
