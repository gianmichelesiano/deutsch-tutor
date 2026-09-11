"""Caricamento dei prompt LLM da file ``.md`` versionati (task 3.1).

I prompt vivono in ``/api/prompts/`` e usano la sintassi ``$variabile`` di
``string.Template`` per l'iniezione dei valori. Il percorso è risolvibile anche
con ``settings.prompts_dir`` (utile per i test).
"""
from __future__ import annotations

from pathlib import Path
from string import Template

from app.config import settings

_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _prompts_dir() -> Path:
    if settings.prompts_dir:
        return Path(settings.prompts_dir)
    return _DEFAULT_DIR


def load(name: str) -> str:
    return (_prompts_dir() / name).read_text(encoding="utf-8")


def render(name: str, **values: object) -> str:
    """Carica ``name`` e sostituisce i placeholder ``$chiave``."""
    template = Template(load(name))
    return template.substitute(**values)


def _bullet(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) or "-"


def format_key_phrases(items: list[dict]) -> str:
    return _bullet(
        [f"{kp['de']} ({kp['it']})" for kp in items if isinstance(kp, dict) and kp.get("de")]
    )


def format_goals(items: list[str]) -> str:
    return _bullet([g for g in items if g])
