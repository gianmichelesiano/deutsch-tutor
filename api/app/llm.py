"""Layer LLM (task 3.1): interfaccia unica ``complete`` + routing locale/cloud.

- ``roleplay`` → locale (llama.cpp / endpoint OpenAI-compatibile, bassa latenza).
- ``warmup_feedback``, ``corrector``, ``harvest``, ``planner``, ``content_gen`` → cloud
  (Anthropic, precisione grammaticale e output strutturato).
- Fallback automatico locale→cloud su errore/timeout.
- Ogni chiamata è loggata in ``llm_calls`` (task, provider, modello, token, latenza).
- Output strutturati validati con Pydantic; retry una volta se il JSON non valida.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.models import LlmCall

TASK_PROVIDER: dict[str, str] = {
    "roleplay": "local",
    "warmup_feedback": "cloud",
    "corrector": "cloud",
    "harvest": "cloud",
    "planner": "cloud",
    "content_gen": "cloud",
}


class LlmError(Exception):
    pass


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class GenerationResult:
    text: str
    provider: str
    model: str
    usage: Usage = field(default_factory=Usage)
    latency_ms: float = 0.0


class LlmClient:
    """Interfaccia unica per le chiamate LLM.

    Ritorna sempre un ``dict``: per i task con ``schema`` è il risultato della
    validazione Pydantic (``model_dump``), altrimenti il JSON parsato dal testo.
    """

    async def complete(
        self,
        task: str,
        messages: list[dict],
        schema: type[BaseModel] | None = None,
        session: Any = None,
        **kwargs: Any,
    ) -> dict:
        raise NotImplementedError


def _extract_json(text: str) -> str:
    """Estrae l'oggetto JSON dal testo, tollerando blocchi ```json ...```."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _try_parse(text: str, schema: type[BaseModel] | None) -> tuple[Any, str | None]:
    json_str = _extract_json(text)
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    if schema is None:
        return data, None
    try:
        return schema.model_validate(data).model_dump(), None
    except ValidationError as exc:
        return None, str(exc)


class OpenAICompatProvider:
    """Provider OpenAI-compatibile (llama.cpp / DeepSeek / ollama)."""

    name = "local"

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        timeout: float = 30.0,
        thinking_disabled: bool = False,
        repeat_penalty: float = 0.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.thinking_disabled = thinking_disabled
        self.repeat_penalty = repeat_penalty

    async def generate(
        self, model: str, messages: list[dict], temperature: float, max_tokens: int
    ) -> GenerationResult:
        if not self.base_url:
            raise LlmError("LOCAL_LLM_BASE_URL non configurato")
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.thinking_disabled:
            # ds4/llama.cpp: disattiva il reasoning del modello (non-standard, ignorato
            # dagli altri endpoint OpenAI-compatibili che non lo conoscono).
            payload["thinking"] = {"type": "disabled"}
        if self.repeat_penalty > 0:
            payload["repeat_penalty"] = self.repeat_penalty
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise LlmError(f"local unavailable: {exc}") from exc
        latency = (time.perf_counter() - start) * 1000
        if resp.status_code >= 400:
            raise LlmError(f"local HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        text = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage") or {}
        return GenerationResult(
            text=text,
            provider=self.name,
            model=model,
            usage=Usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
            latency_ms=latency,
        )


class AnthropicProvider:
    """Provider cloud Anthropic (Messages API)."""

    name = "cloud"

    def __init__(self, api_key: str, timeout: float = 30.0):
        self.api_key = api_key
        self.timeout = timeout

    @staticmethod
    def _split(messages: list[dict]) -> tuple[str, list[dict]]:
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        convo = [m for m in messages if m.get("role") != "system"]
        return "\n".join(system_parts), convo

    async def generate(
        self, model: str, messages: list[dict], temperature: float, max_tokens: int
    ) -> GenerationResult:
        if not self.api_key:
            raise LlmError("ANTHROPIC_API_KEY non configurato")
        system, convo = self._split(messages)
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": convo,
        }
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise LlmError(f"cloud unavailable: {exc}") from exc
        latency = (time.perf_counter() - start) * 1000
        if resp.status_code >= 400:
            raise LlmError(f"cloud HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        usage = data.get("usage") or {}
        return GenerationResult(
            text=text,
            provider=self.name,
            model=model,
            usage=Usage(usage.get("input_tokens", 0), usage.get("output_tokens", 0)),
            latency_ms=latency,
        )


class RoutingLlmClient(LlmClient):
    """Routing per task con fallback locale→cloud e logging su ``llm_calls``."""

    def __init__(self, settings: Any):
        self.settings = settings
        self.local = OpenAICompatProvider(
            settings.local_llm_base_url,
            api_key=settings.local_llm_api_key,
            timeout=settings.llm_timeout_seconds,
            thinking_disabled=settings.local_llm_thinking_disabled,
            repeat_penalty=settings.local_llm_repeat_penalty,
        )
        self.cloud = AnthropicProvider(
            settings.anthropic_api_key,
            timeout=settings.llm_timeout_seconds,
        )

    def _task_config(self, task: str) -> dict:
        if task == "roleplay":
            return {
                "provider": "local",
                "model": self.settings.local_llm_model,
                "temperature": self.settings.roleplay_temperature,
                "max_tokens": self.settings.roleplay_max_tokens,
            }
        return {
            "provider": "cloud",
            "model": self.settings.anthropic_model,
            "temperature": self.settings.cloud_temperature,
            "max_tokens": self.settings.cloud_max_tokens,
        }

    def _provider_for(self, task: str) -> str:
        mode = self.settings.llm_provider_mode
        if mode == "local-only":
            return "local"
        if mode == "cloud-only":
            return "cloud"
        return TASK_PROVIDER.get(task, "cloud")

    async def _generate_valid(
        self,
        provider: str,
        cfg: dict,
        messages: list[dict],
        schema: type[BaseModel] | None,
    ) -> tuple[GenerationResult, dict]:
        gen = self.local if provider == "local" else self.cloud
        result = await gen.generate(
            cfg["model"], messages, cfg["temperature"], cfg["max_tokens"]
        )
        value, err = _try_parse(result.text, schema)
        if err is None:
            return result, value
        # retry una volta con il messaggio d'errore
        retry_messages = messages + [
            {"role": "assistant", "content": result.text},
            {
                "role": "user",
                "content": (
                    "La tua risposta precedente non era un JSON valido. "
                    f"Antworte NUR mit gültigem JSON. Fehler: {err}"
                ),
            },
        ]
        result2 = await gen.generate(
            cfg["model"], retry_messages, cfg["temperature"], cfg["max_tokens"]
        )
        value2, err2 = _try_parse(result2.text, schema)
        if err2 is None:
            return result2, value2
        raise LlmError(f"JSON non valido dopo retry: {err2}")

    async def complete(
        self,
        task: str,
        messages: list[dict],
        schema: type[BaseModel] | None = None,
        session: Any = None,
        **kwargs: Any,
    ) -> dict:
        cfg = self._task_config(task)
        if "temperature" in kwargs:
            cfg["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            cfg["max_tokens"] = kwargs["max_tokens"]

        primary = self._provider_for(task)
        if primary != cfg["provider"]:
            # modalità forzata (local-only / cloud-only): allinea il modello al provider
            cfg["provider"] = primary
            cfg["model"] = (
                self.settings.local_llm_model if primary == "local" else self.settings.anthropic_model
            )
        try:
            result, value = await self._generate_valid(primary, cfg, messages, schema)
        except LlmError as exc:
            if primary == "local" and self.settings.llm_provider_mode == "auto":
                # fallback locale -> cloud
                try:
                    cloud_cfg = dict(cfg, provider="cloud", model=self.settings.anthropic_model)
                    result, value = await self._generate_valid("cloud", cloud_cfg, messages, schema)
                except LlmError as exc2:
                    await self._log(session, task, None, ok=False, error=str(exc2))
                    raise
            else:
                await self._log(session, task, None, ok=False, error=str(exc))
                raise
        await self._log(session, task, result, ok=True, error=None)
        return value

    async def _log(
        self,
        session: Any,
        task: str,
        result: GenerationResult | None,
        *,
        ok: bool,
        error: str | None,
    ) -> None:
        if session is None:
            return
        session.add(
            LlmCall(
                task=task,
                provider=result.provider if result else self._provider_for(task),
                model=result.model if result else "unknown",
                prompt_tokens=result.usage.prompt_tokens if result else 0,
                completion_tokens=result.usage.completion_tokens if result else 0,
                latency_ms=int(result.latency_ms) if result else 0,
                ok=ok,
                error=error,
            )
        )


class MockLlmClient(LlmClient):
    """Mock deterministico (test + ``LLM_PROVIDER_MODE=mock``).

    - ``warmup_feedback``: risposta sempre corretta (tono asciutto).
    - ``roleplay``: risposta fissa; il dialogo si chiude dopo ``close_after_turns``
      messaggi dell'utente.
    - ``corrector``: nessun errore, nessuna parola nuova (neutro per i test).
    """

    def __init__(self, close_after_turns: int = 4):
        self.close_after_turns = close_after_turns

    async def complete(
        self,
        task: str,
        messages: list[dict],
        schema: type[BaseModel] | None = None,
        session: Any = None,
        **kwargs: Any,
    ) -> dict:
        if task == "warmup_feedback":
            return {
                "is_correct": True,
                "corrected_sentence": None,
                "feedback_it": "Ok.",
                "error_type": "none",
            }
        if task == "corrector":
            return {"comprehensible": True, "errors": [], "new_words_from_agent": []}
        if task == "planner":
            return {"new_words": [], "recurring_errors": [], "recommendation": ""}
        if task == "roleplay":
            from app.parser import parse_requested_terms

            last_user = next(
                (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
            )
            translations = [
                {"it": t, "de_in_context": f"das {t}", "lemma": f"das {t}"}
                for t in parse_requested_terms(last_user)
            ]
            user_turns = sum(1 for m in messages if m["role"] == "user")
            closed = user_turns >= self.close_after_turns
            if user_turns == 0:
                text = "Grüezi! Kann ich Ihnen helfen?"
            elif closed:
                text = "Uf Wiederluege und einen schönen Tag!"
            else:
                text = "Gerne! Darf es sonst noch etwas sein?"
            return {
                "text": text,
                "dialogue_closed": closed,
                "translations": translations,
                "scene_state": {
                    "items": ["Eier"],
                    "total_chf": 8.5,
                    "payment": "bar",
                    "incident_done": False,
                    "goals_done": ["Nach einem Produkt fragen"],
                    "greeted": True,
                },
            }
        raise NotImplementedError(f"mock: task '{task}' non implementato")
