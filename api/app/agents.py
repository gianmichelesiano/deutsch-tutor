"""Agenti LLM (task 3.3): Gesprächspartner + Korrektor.

Costruiscono i messaggi (da ``app/prompts``) e definiscono gli schemi Pydantic
di output validati dal layer LLM. Il Gesprächspartner non interrompe mai il
dialogo e non corregge esplicitamente; le correzioni sono accumulate dal
Korrektor per la fase harvest.
"""
from __future__ import annotations

from pydantic import BaseModel

from app import prompts

LEVEL = "A2/B1"
HISTORY_TURNS = 6  # solo gli ultimi 6 messaggi di cronologia vengono passati al modello


class Translation(BaseModel):
    it: str
    de_in_context: str
    lemma: str  # forma base completa di articolo, es. "das Bargeld"


class SceneState(BaseModel):
    items: list[str] = []
    total_chf: float | None = None
    payment: str | None = None  # "bar" | "karte" | None
    incident_done: bool = False
    goals_done: list[str] = []
    greeted: bool = False  # evita il doppio saluto


class RoleplayReply(BaseModel):
    text: str
    dialogue_closed: bool = False
    translations: list[Translation] = []
    scene_state: SceneState | None = None


class Correction(BaseModel):
    span: str
    fix: str
    type: str
    rule_it: str


class NewWord(BaseModel):
    de: str
    it: str


class CorrectorReply(BaseModel):
    comprehensible: bool = True
    errors: list[Correction] = []
    new_words_from_agent: list[NewWord] = []


class WarmupFeedback(BaseModel):
    is_correct: bool
    corrected_sentence: str | None = None
    feedback_it: str = ""
    error_type: str = "none"


class PlannerOutput(BaseModel):
    new_words: list[str] = []
    recurring_errors: list[str] = []
    recommendation: str = ""


class ContentGenItem(BaseModel):
    de: str
    it: str
    gender: str | None = None
    plural: str | None = None
    separable: bool = False
    example_de: str = ""


class ContentGenMeta(BaseModel):
    role_label: str | None = None
    key_phrases: list[dict] = []
    imprevisti: list[str] = []
    swiss_variants: list[dict] = []
    goals: list[str] = []


class ContentGenVocabChunk(BaseModel):
    vocab: list[ContentGenItem] = []


class IntroLine(BaseModel):
    de: str
    it: str


class IntroTurn(BaseModel):
    speaker: str
    de: str
    it: str


class ContentGenIntro(BaseModel):
    situation: list[IntroLine]
    dialog: list[IntroTurn]
    notes_it: list[str]


def _level() -> str:
    return LEVEL


_ROLE_MAP = {"agent": "assistant"}


def _last_turns(history: list[dict], n: int = HISTORY_TURNS) -> list[dict]:
    """Ultimi ``n`` turni, con i ruoli interni mappati su quelli OpenAI standard
    (``agent`` → ``assistant``: gli endpoint strict come DeepSeek rifiutano ruoli
    sconosciuti)."""
    turns = history[-n:] if len(history) > n else history
    return [{**m, "role": _ROLE_MAP.get(m["role"], m["role"])} for m in turns]


def format_scene_state(scene_state: dict | None) -> str:
    """Rende lo stato della scena leggibile per il system prompt."""
    if not scene_state:
        return "- (noch nichts passiert)"
    lines: list[str] = []
    items = scene_state.get("items") or []
    if items:
        lines.append(f"- Artikel im Korb: {', '.join(items)}")
    total = scene_state.get("total_chf")
    if total is not None:
        lines.append(f"- Gesamtpreis: {total} Franken")
    payment = scene_state.get("payment")
    if payment:
        lines.append(f"- Zahlungsweise: {payment}")
    if scene_state.get("incident_done"):
        lines.append("- Zwischenfall: bereits behandelt")
    if scene_state.get("greeted"):
        lines.append("- Begrüssung: bereits erfolgt (nicht noch einmal grüssen)")
    goals = scene_state.get("goals_done") or []
    if goals:
        lines.append(f"- Ziele erreicht: {', '.join(goals)}")
    return "\n".join(lines) if lines else "- (noch nichts passiert)"


def build_roleplay_messages(
    scenario: object,
    history: list[dict],
    *,
    max_turns: int = 12,
    react_incomprehensible: bool = False,
    scene_state: dict | None = None,
) -> list[dict]:
    """Messaggi per il Gesprächspartner (locale).

    ``history`` sono i turni già avvenuti (``[{"role", "content"}, ...]``) senza
    system; ne vengono passati solo gli ultimi ``HISTORY_TURNS``. Lo ``scene_state``
    (stato della scena del turno precedente) è iniettato come "Stand der Szene".
    Se la cronologia è vuota (apertura) viene aggiunto un trigger utente.
    """
    system = prompts.render(
        "roleplay_system.md",
        role=scenario.role_label or "Gesprächspartner",
        scenario_de=scenario.title_de,
        scenario_it=scenario.title_it,
        level=_level(),
        imprevisto=(scenario.imprevisti or ["eine kleine Überraschung"])[0],
        goals=prompts.format_goals(scenario.goals or []),
        key_phrases=prompts.format_key_phrases(scenario.key_phrases or []),
        scene_state=format_scene_state(scene_state),
        max_turns=max_turns,
    )
    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(_last_turns(history))
    if react_incomprehensible:
        messages.append(
            {
                "role": "system",
                "content": (
                    "Der letzte Satz des Lernenden war nicht verständlich. "
                    "Reagiere in deiner Rolle höflich nachfragend, zum Beispiel "
                    "„Wie bitte? Meinen Sie …?“. Bleib dabei in der Rolle."
                ),
            }
        )
    if not any(m["role"] == "user" for m in messages):
        messages.append({"role": "user", "content": "Beginne das Gespräch."})
    return messages


def build_corrector_messages(
    scenario: object,
    user_message: str,
    agent_reply: str,
) -> list[dict]:
    """Messaggi per il Korrektor (cloud): istruzioni di sistema + contenuto utente."""
    system = prompts.render(
        "corrector.md",
        role=scenario.role_label or "Gesprächspartner",
        scenario_de=scenario.title_de,
        level=_level(),
    )
    user = (
        "Nachricht des Lernenden:\n"
        f"«{user_message}»\n\n"
        "Antwort der Lehrperson:\n"
        f"«{agent_reply}»"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_warmup_messages(vocab_de: str, vocab_it: str, sentence: str) -> list[dict]:
    """Messaggi per l'agente Warm-up (cloud): word + frase da giudicare."""
    system = prompts.render("warmup_feedback.md", level=_level())
    user = f"Wort: {vocab_de} ({vocab_it})\nSatz des Lernenden:\n«{sentence}»"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_planner_messages(scenario: object, lesson_data: dict) -> list[dict]:
    """Messaggi per il Planer (cloud): riassunto della lezione completata."""
    system = prompts.render(
        "planner.md",
        level=_level(),
        scenario_de=scenario.title_de,
        scenario_it=scenario.title_it,
        goals=prompts.format_goals(scenario.goals or []),
        requested=", ".join(lesson_data.get("requested", [])) or "-",
        error_words=", ".join(lesson_data.get("error_words", [])) or "-",
        agent_words=", ".join(lesson_data.get("agent_words", [])) or "-",
        corrections=", ".join(lesson_data.get("corrections", [])) or "-",
    )
    user = "Erstelle die Zusammenfassung für die abgeschlossene Lektion."
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_content_gen_meta_messages(scenario: object) -> list[dict]:
    """Messaggi per il generatore di contenuti: parte "meta" (frasi, imprevisti, goals)."""
    system = prompts.render(
        "content_gen_meta.md",
        level=_level(),
        title_de=scenario.title_de,
        title_it=scenario.title_it,
        description=scenario.description,
    )
    user = "Erzeuge den Meta-Teil des Szenarios."
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_content_gen_intro_messages(scenario: object) -> list[dict]:
    """Messaggi per il generatore di contenuti: parte "Einstieg" (situazione, dialogo, note)."""
    system = prompts.render(
        "content_gen_intro.md",
        level=_level(),
        title_de=scenario.title_de,
        title_it=scenario.title_it,
        description=scenario.description,
        role=scenario.role_label or "Gesprächspartner",
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "Erzeuge den Einstieg des Szenarios."},
    ]


def build_content_gen_vocab_messages(
    scenario: object, exclude: list[str], count: int
) -> list[dict]:
    """Messaggi per il generatore di contenuti: un blocco di ``count`` vocaboli."""
    system = prompts.render(
        "content_gen_vocab.md",
        level=_level(),
        title_de=scenario.title_de,
        title_it=scenario.title_it,
        description=scenario.description,
        exclude=", ".join(exclude) if exclude else "-",
        count=count,
    )
    user = f"Erzeuge {count} Vokabeln für das Szenario."
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
