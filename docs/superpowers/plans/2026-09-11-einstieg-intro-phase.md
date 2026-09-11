# Fase "Einstieg" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere una prima fase di lezione "Einstieg" con racconto della situazione in tedesco, mini-dialogo e note pragmatiche in italiano, statica per scenario e compressa dopo la prima lezione completata dello scenario.

**Architecture:** `intro` diventa un valore dell'enum `lesson_phase_enum` e la prima fase di `PHASES` (non del ripasso). Il contenuto vive in `scenarios.intro` (JSONB), generato una volta da `app.content_gen` e salvato nei JSON `api/app/seed_content/scenario-NN.json` che il seed applica. Il frontend viene spezzato in un file per fase e riceve `IntroPhase`.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic + Pydantic v2 (api), pytest (asyncio auto), Next.js App Router + Tailwind (web), Docker Compose. LLM: DeepSeek via provider OpenAI-compatibile (`LLM_PROVIDER_MODE=local-only`).

**Spec:** `docs/superpowers/specs/2026-09-11-einstieg-intro-phase-design.md`

## Global Constraints

- Tutti i comandi backend girano nel container: `docker compose exec -T api <cmd>` dalla root del repo. Il codice `api/app`, `api/tests`, `api/prompts`, `api/alembic` è montato, nessun rebuild necessario.
- I test usano il DB `deutsch_tutor_test` (vedi `api/tests/conftest.py`). Mai lanciare TRUNCATE sul DB live.
- Il container `web` NON monta il codice: fino al Task 8 ogni verifica visiva richiede `docker compose build web && docker compose up -d web`. Il typecheck si fa sull'host: `cd web && npx tsc --noEmit -p .`.
- Lingua dei contenuti: Hochdeutsch (Schweizer Standarddeutsch, `ss` non `ß`). Niente Schweizerdeutsch fuori da `swiss_variants.swiss`. Copy UI in italiano, titoli di fase in tedesco come le fasi esistenti.
- Commit: messaggi in italiano, formato `feat|fix|refactor|docs|test: …`, chiusi da `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Prima del Task 1 il WIP pre-esistente va messo in un commit di baseline (Task 0).
- Nessun `TODO`, nessun placeholder nei contenuti generati.

---

### Task 0: Baseline del lavoro pre-esistente

**Files:**
- Nessuna modifica: solo commit di ciò che è già nel working tree (fasi 3–4, DeepSeek, scenari 3–12, conftest).

- [ ] **Step 1: Verifica che nulla di sensibile venga committato**

Run: `git status --short | grep -v '^??' ; git status --short | grep '^??' ; git check-ignore .env && echo ".env ignorato"`
Expected: `.env ignorato`; nessun file `*.env` non ignorato tra gli untracked.

- [ ] **Step 2: Commit baseline**

```bash
git add -A
git commit -m "chore: baseline fasi 3-4 + DeepSeek + scenari 3-12 + DB di test separato

Stato del working tree prima della fase Einstieg. Include: layer LLM su DeepSeek,
contenuti generati per gli scenari 3-12 (api/app/seed_content), test isolati su
deutsch_tutor_test, frontend fasi 4.x.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 1: Macchina a stati con `intro`

**Files:**
- Modify: `api/app/lesson_state.py`
- Test: `api/tests/test_lesson_state.py`

**Interfaces:**
- Produces: `PHASES == ("intro", "warmup", "prep", "roleplay", "harvest", "swiss")`; `back_phase("warmup") == "intro"`; `first_phase(lesson_type: str) -> str` che ritorna `"intro"` per i tipi non-review e `"warmup"` per `"review"`.

- [ ] **Step 1: Aggiorna i test esistenti e aggiungi i nuovi**

In `api/tests/test_lesson_state.py` sostituisci `test_phase_order`, `test_back_only_from_roleplay`, `test_back_from_other_phases_raises` e aggiungi `test_first_phase`:

```python
from app.lesson_state import first_phase  # aggiungi all'import esistente


def test_phase_order() -> None:
    assert PHASES == ("intro", "warmup", "prep", "roleplay", "harvest", "swiss")
    assert REVIEW_PHASES == ("warmup", "test", "harvest", "swiss")


def test_back_allowed_transitions() -> None:
    assert back_phase("roleplay") == "prep"
    assert back_phase("warmup") == "intro"


def test_back_from_other_phases_raises() -> None:
    for phase in ("intro", "prep", "harvest", "swiss", "completed"):
        with pytest.raises(InvalidTransition):
            back_phase(phase)


def test_first_phase_by_lesson_type() -> None:
    assert first_phase("base") == "intro"
    assert first_phase("variant") == "intro"
    assert first_phase("incident") == "intro"
    assert first_phase("review") == "warmup"
```

Controlla che `REVIEW_PHASES` e `InvalidTransition` siano importati in testa al file (aggiungili se mancano). `test_full_forward_sequence` parte da `PHASES[0]`: verifica che usi `PHASES[0]` e non la stringa `"warmup"`; se usa la stringa, sostituiscila con `PHASES[0]`.

- [ ] **Step 2: Esegui i test, devono fallire**

Run: `docker compose exec -T api python -m pytest tests/test_lesson_state.py -q`
Expected: FAIL (`ImportError: first_phase`, poi assert su `PHASES`).

- [ ] **Step 3: Implementa**

In `api/app/lesson_state.py`:

```python
"""Macchina a stati della lezione — puro, senza DB.

Stati: intro → warmup → prep → roleplay → harvest → swiss → completed.
- Il ripasso (``review``) non ha ``intro``: warmup → test → harvest → swiss.
- Nessuno stato saltabile tranne ``swiss`` (opzionale: da ``harvest`` con
  ``skip_swiss`` si va direttamente a ``completed``).
- Transizioni all'indietro consentite: ``roleplay → prep`` e ``warmup → intro``.
"""
from __future__ import annotations

PHASES: tuple[str, ...] = ("intro", "warmup", "prep", "roleplay", "harvest", "swiss")
REVIEW_PHASES: tuple[str, ...] = ("warmup", "test", "harvest", "swiss")
TERMINAL = "completed"
REPEAT_SCENARIO_THRESHOLD = 6

BACK_TRANSITIONS: dict[str, str] = {"roleplay": "prep", "warmup": "intro"}
```

Aggiungi dopo `phases_for`:

```python
def first_phase(lesson_type: str) -> str:
    """Fase iniziale di una nuova lezione (``intro``; ``warmup`` per il ripasso)."""
    return phases_for(lesson_type)[0]
```

Sostituisci `back_phase`:

```python
def back_phase(current: str) -> str:
    """Transizione all'indietro: ``roleplay → prep`` e ``warmup → intro``."""
    try:
        return BACK_TRANSITIONS[current]
    except KeyError as exc:
        raise InvalidTransition(f"indietro non consentito da {current}") from exc
```

- [ ] **Step 4: Esegui i test**

Run: `docker compose exec -T api python -m pytest tests/test_lesson_state.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/lesson_state.py api/tests/test_lesson_state.py
git commit -m "feat(lesson): fase intro nella macchina a stati + back warmup->intro

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Modello e migrazione (`LessonPhase.intro`, `scenarios.intro`)

**Files:**
- Modify: `api/app/models.py` (enum `LessonPhase`, classe `Scenario`)
- Create: `api/alembic/versions/0005_add_intro_phase_and_scenario_intro.py`

**Interfaces:**
- Produces: `LessonPhase.intro`; `Scenario.intro: Mapped[dict | None]` (JSONB, nullable).

- [ ] **Step 1: Modello**

In `api/app/models.py`, enum `LessonPhase`: aggiungi `intro = "intro"` come primo membro. Nella classe `Scenario`, dopo `goals`:

```python
    intro: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 2: Migrazione**

Crea `api/alembic/versions/0005_add_intro_phase_and_scenario_intro.py`:

```python
"""add lesson_phase_enum 'intro' + scenarios.intro

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE lesson_phase_enum ADD VALUE IF NOT EXISTS 'intro'")
    op.add_column("scenarios", sa.Column("intro", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("scenarios", "intro")
    # PostgreSQL non supporta la rimozione di un valore da un enum in modo semplice.
```

- [ ] **Step 3: Applica al DB live e verifica**

Run: `docker compose exec -T api alembic upgrade head && docker compose exec -T db psql -U deutsch deutsch_tutor -tAc "select column_name from information_schema.columns where table_name='scenarios' and column_name='intro'; select unnest(enum_range(NULL::lesson_phase_enum));"`
Expected: `intro` tra le colonne e tra i valori dell'enum.

- [ ] **Step 4: Suite completa (il conftest migra anche il DB di test)**

Run: `docker compose exec -T api python -m pytest -q`
Expected: PASS (60 test). Se `test_api_integration` fallisce per la fase iniziale, è atteso solo dopo il Task 5: qui `create_lesson` è ancora in `warmup`.

- [ ] **Step 5: Commit**

```bash
git add api/app/models.py api/alembic/versions/0005_add_intro_phase_and_scenario_intro.py
git commit -m "feat(db): valore enum intro + colonna scenarios.intro (migrazione 0005)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Generatore contenuti: schema, prompt, `generate_intro`

**Files:**
- Create: `api/prompts/content_gen_intro.md`
- Modify: `api/app/agents.py` (schemi + builder)
- Modify: `api/app/content_gen.py` (`dialect_hits`, `generate_intro`, `generate`)
- Test: `api/tests/test_content_gen.py`, `api/tests/test_agents.py`

**Interfaces:**
- Consumes: `prompts.render(name, **values)`, `agents._level()`, `content_gen.dialect_hits(content) -> list[str]`, `content_gen.META_ATTEMPTS`.
- Produces: `agents.ContentGenIntro` (Pydantic: `situation: list[IntroLine]`, `dialog: list[IntroTurn]`, `notes_it: list[str]`), `agents.build_content_gen_intro_messages(scenario) -> list[dict]`, `content_gen.generate_intro(client, scenario) -> dict`. `dialect_hits` controlla anche `intro.situation[].de` e `intro.dialog[].de` quando `content` ha la chiave `intro` oppure è direttamente un intro (ha `situation`).

- [ ] **Step 1: Test del validatore e del builder**

Aggiungi a `api/tests/test_content_gen.py`:

```python
def test_dialect_hits_covers_intro_fields():
    intro = {
        "situation": [{"de": "Ich bin im Coop.", "it": "Sono alla Coop."}, {"de": "Ich bi im Coop.", "it": "x"}],
        "dialog": [{"speaker": "Ich", "de": "Grüezi, wie gaht's?", "it": "x"}],
        "notes_it": ["Si usa il Sie."],
    }
    hits = dialect_hits(intro)
    assert "Ich bi im Coop." in hits
    assert "Grüezi, wie gaht's?" in hits
    assert "Ich bin im Coop." not in hits
    # anche quando l'intro è annidato in un contenuto completo
    assert dialect_hits({"role_label": "Kellnerin", "key_phrases": [], "imprevisti": [], "goals": [], "intro": intro}) == hits
```

Aggiungi a `api/tests/test_agents.py`:

```python
def test_content_gen_intro_messages_mention_scenario_and_role():
    sc = _scenario()
    msgs = agents.build_content_gen_intro_messages(sc)
    assert msgs[0]["role"] == "system"
    assert sc.title_de in msgs[0]["content"]
    assert "Verkäuferin am Supermarkt" in msgs[0]["content"]
    assert "Hochdeutsch" in msgs[0]["content"]
    assert msgs[-1]["role"] == "user"
```

Verifica che `_scenario()` in `test_agents.py` esponga `role_label`, `title_de`, `title_it`, `description` (aggiungi `description="..."` al `SimpleNamespace` se manca).

- [ ] **Step 2: Esegui, devono fallire**

Run: `docker compose exec -T api python -m pytest tests/test_content_gen.py tests/test_agents.py -q`
Expected: FAIL (`AttributeError: build_content_gen_intro_messages`; `dialect_hits` non trova i campi intro).

- [ ] **Step 3: Prompt**

Crea `api/prompts/content_gen_intro.md`:

```
Du bist ein Lehrplan-Generator für eine Deutsch-Lern-App (Niveau $level, Schweizer Kontext, Zürich). Erzeuge den EINSTIEG eines Szenarios: eine kurze Situationsbeschreibung, einen Beispieldialog und Hinweise auf Italienisch.

Szenario: „$title_de" ($title_it)
Beschreibung: $description
Gesprächspartner im Rollenspiel: $role

SPRACHE (wichtigste Regel):
- Alle "de"-Felder auf HOCHDEUTSCH (Schweizer Standarddeutsch: „ss" statt „ß"; Helvetismen wie Velo, Znüni, Franken, Grüezi sind erwünscht).
- KEIN Schweizerdeutsch, KEIN Dialekt. RICHTIG: „Grüezi, wie geht's?" · „Kommen Sie doch rein." FALSCH: „Grüezi, wie gaht's?" · „Chömed Sie doch ine."
- Alle "it"-Felder und "notes_it" auf Italienisch, natürlich und kurz.

INHALT:
- "situation": 5 bis 8 kurze Sätze in der ICH-Perspektive des Lernenden (Niveau $level): wo bin ich, was will ich, wer steht mir gegenüber, was passiert typischerweise. Jeder Satz {de, it}. Konkret für Zürich (Migros/Coop, Franken, SBB, …), nichts Allgemeines.
- "dialog": 4 bis 6 Repliken eines typischen Gesprächs, abwechselnd "Ich" (der Lernende) und "$role". Jede Replik {speaker, de, it}. speaker ist genau "Ich" oder "$role". Kurze, gesprochene Sätze.
- "notes_it": 2 bis 3 Hinweise auf Italienisch für einen Italiener in Zürich: Register (Sie/du), Schweizer Gewohnheiten, was der Gesprächspartner erwartet. Keine Grammatikregeln.

Antworte AUSSCHLIESSLICH mit gültigem JSON: {"situation": [...], "dialog": [...], "notes_it": [...]}. Kein Markdown, kein weiterer Text.
```

- [ ] **Step 4: Schemi e builder in `agents.py`**

Dopo `ContentGenVocabChunk`:

```python
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
```

Dopo `build_content_gen_meta_messages`:

```python
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
```

- [ ] **Step 5: `dialect_hits` e `generate_intro` in `content_gen.py`**

Sostituisci `dialect_hits`:

```python
def dialect_hits(content: dict) -> list[str]:
    """Frasi con marcatori dialettali nei campi che devono essere Hochdeutsch.

    Accetta sia il contenuto completo di uno scenario (con eventuale chiave
    ``intro``) sia un intro da solo (``situation``/``dialog``/``notes_it``).
    """
    texts: list[str] = []
    if "situation" in content or "dialog" in content:
        intro = content
    else:
        intro = content.get("intro") or {}
        texts.append(content.get("role_label") or "")
        texts += [kp.get("de", "") for kp in content.get("key_phrases", [])]
        texts += list(content.get("imprevisti", []))
        texts += list(content.get("goals", []))
    texts += [line.get("de", "") for line in intro.get("situation", [])]
    texts += [turn.get("de", "") for turn in intro.get("dialog", [])]
    return [t for t in texts if _DIALECT.search(t)]
```

Estrai da `generate_meta` la logica di retry in una funzione riusabile e aggiungi `generate_intro`:

```python
async def _generate_hochdeutsch(
    client: RoutingLlmClient, messages: list[dict], schema: type, label: str
) -> dict:
    """Chiama il modello finché il risultato passa ``dialect_hits`` (max META_ATTEMPTS),
    ripassando al modello le frasi in dialetto."""
    last: dict = {}
    for _ in range(META_ATTEMPTS):
        last = await client.complete("content_gen", messages, schema=schema, max_tokens=4096)
        hits = dialect_hits(last)
        if not hits:
            return last
        messages = messages + [
            {"role": "assistant", "content": json.dumps(last, ensure_ascii=False)},
            {
                "role": "user",
                "content": (
                    "Diese Sätze sind Schweizerdeutsch, nicht Hochdeutsch: "
                    + " · ".join(f"„{h}“" for h in hits)
                    + ". Schreibe das GANZE JSON neu, alle deutschen Felder ausser "
                    "swiss_variants.swiss auf Hochdeutsch (z.B. „wie geht's“ statt „wie gaht's“)."
                ),
            },
        ]
    raise RuntimeError(
        f"{label} ancora in dialetto dopo {META_ATTEMPTS} tentativi: {dialect_hits(last)[:3]}"
    )


async def generate_meta(client: RoutingLlmClient, scenario: dict) -> dict:
    """Meta (role_label, key_phrases, imprevisti, swiss_variants, goals) in Hochdeutsch."""
    s = SimpleNamespace(**scenario)
    return await _generate_hochdeutsch(
        client, agents.build_content_gen_meta_messages(s), agents.ContentGenMeta,
        f"meta di «{scenario['title_de']}»",
    )


async def generate_intro(client: RoutingLlmClient, scenario: dict) -> dict:
    """Einstieg (situation, dialog, notes_it) in Hochdeutsch. ``scenario`` deve avere
    ``role_label`` (usa quello generato dalla meta se il seed non lo ha)."""
    s = SimpleNamespace(**scenario)
    return await _generate_hochdeutsch(
        client, agents.build_content_gen_intro_messages(s), agents.ContentGenIntro,
        f"intro di «{scenario['title_de']}»",
    )
```

In `generate`, dopo `meta = await generate_meta(client, scenario)` aggiungi:

```python
    meta["intro"] = await generate_intro(client, {**scenario, "role_label": meta.get("role_label")})
```

In `write_to_db`, dopo `sc.goals = content.get("goals", [])` aggiungi `sc.intro = content.get("intro")`.

- [ ] **Step 6: Esegui i test**

Run: `docker compose exec -T api python -m pytest tests/test_content_gen.py tests/test_agents.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add api/prompts/content_gen_intro.md api/app/agents.py api/app/content_gen.py api/tests/test_content_gen.py api/tests/test_agents.py
git commit -m "feat(content_gen): generazione Einstieg (situazione, dialogo, note) con validazione Hochdeutsch

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Seed con `intro` e generazione per gli scenari 1–12

**Files:**
- Modify: `api/app/seed.py` (`GENERATED_FIELDS`, applicazione parziale dei campi)
- Modify: `api/tests/test_seed.py`
- Create: `api/app/seed_content/scenario-01.json`, `api/app/seed_content/scenario-02.json` (solo `slug`, `week_number`, `intro`)
- Modify: `api/app/seed_content/scenario-03.json` … `scenario-12.json` (aggiunta chiave `intro`)

**Interfaces:**
- Consumes: `content_gen.generate_intro(client, scenario)`, `seed.load_seed_content()`.
- Produces: ogni JSON 1–12 ha `intro` valido; il seed applica per ogni file solo i campi presenti (`GENERATED_FIELDS = ("role_label", "key_phrases", "swiss_variants", "imprevisti", "goals", "intro")`), un campo alla volta se vuoto sullo scenario oppure con `--update`.

- [ ] **Step 1: Aggiorna il test dei file JSON**

In `api/tests/test_seed.py` sostituisci `test_seed_content_files_cover_scenarios_3_to_12` con:

```python
def _assert_valid_intro(intro: dict, slug: str) -> None:
    assert 5 <= len(intro["situation"]) <= 8, slug
    assert 4 <= len(intro["dialog"]) <= 6, slug
    assert 2 <= len(intro["notes_it"]) <= 3, slug
    for line in intro["situation"]:
        assert line["de"].strip() and line["it"].strip(), slug
    speakers = {t["speaker"] for t in intro["dialog"]}
    assert "Ich" in speakers and len(speakers) == 2, f"{slug}: speaker {speakers}"
    for turn in intro["dialog"]:
        assert turn["de"].strip() and turn["it"].strip(), slug
    for note in intro["notes_it"]:
        assert note.strip(), slug


def test_seed_content_files_cover_all_scenarios() -> None:
    """Scenari 1-2: solo intro (vocab e meta sono in seed_data). Scenari 3-12: contenuto completo."""
    contents = load_seed_content()
    slugs = {s["slug"]: s["week_number"] for s in SCENARIOS}
    weeks = sorted(c["week_number"] for c in contents)
    assert weeks == list(range(1, 13))
    for c in contents:
        assert slugs[c["slug"]] == c["week_number"]
        _assert_valid_intro(c["intro"], c["slug"])
        if c["week_number"] <= 2:
            assert "vocab" not in c and "key_phrases" not in c
            continue
        assert c["role_label"]
        assert len(c["key_phrases"]) >= 8
        assert len(c["imprevisti"]) >= 3
        assert len(c["swiss_variants"]) >= 1
        assert len(c["goals"]) >= 3
        assert 30 <= len(c["vocab"]) <= 45, c["slug"]
        des = [v["de"] for v in c["vocab"]]
        assert len(des) == len(set(des)), f"vocab duplicati in {c['slug']}"
        for v in c["vocab"]:
            assert v["de"].strip() and v["it"].strip() and v["example_de"].strip()
```

`test_seed_is_idempotent` usa `sum(len(c["vocab"]) ...)`: cambia in `sum(len(c.get("vocab", [])) for c in load_seed_content())`. Stessa modifica in `api/tests/test_api_integration.py` alla riga che calcola `seeded` (`len(c.get("vocab", []))`).

- [ ] **Step 2: Esegui, deve fallire**

Run: `docker compose exec -T api python -m pytest tests/test_seed.py::test_seed_content_files_cover_all_scenarios -q`
Expected: FAIL (`weeks == [3..12]`, manca `intro`).

- [ ] **Step 3: Seed: applicazione parziale dei campi**

In `api/app/seed.py`:

```python
GENERATED_FIELDS = ("role_label", "key_phrases", "swiss_variants", "imprevisti", "goals", "intro")
```

Sostituisci il blocco "Contenuti generati" dentro `run_seed` con:

```python
        # Contenuti generati (scenari 1-12): ogni campo presente nel JSON viene applicato
        # se lo scenario non lo ha ancora, oppure sempre con --update. I vocaboli (solo
        # scenari 3-12) si aggiungono alla lista da inserire.
        generated = load_seed_content()
        vocab_rows = list(VOCAB)
        for content in generated:
            scenario = await session.scalar(select(Scenario).where(Scenario.slug == content["slug"]))
            if scenario is None:
                continue
            touched = False
            for field in GENERATED_FIELDS:
                if field not in content:
                    continue
                if update or not getattr(scenario, field):
                    setattr(scenario, field, content[field])
                    touched = True
            if touched:
                updated_scenarios += 1
            vocab_rows.extend({"scenario_slug": content["slug"], **v} for v in content.get("vocab", []))
        await session.commit()
```

Rimuovi la funzione `_has_content` (non più usata).

- [ ] **Step 4: Script di generazione intro per 1–12**

Crea `api/app/gen_intro.py` (CLI riusabile, come `content_gen`):

```python
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
        print(f"[{week}] {scenario['title_de']}: situation={len(intro['situation'])} dialog={len(intro['dialog'])} notes={len(intro['notes_it'])}")


if __name__ == "__main__":
    asyncio.run(main())
```

Nota: per gli scenari 1–2 `scenario["role_label"]` in `seed_data.py` è già impostato ("Verkäuferin am Supermarkt", "Nachbarin"). Se in `seed_data.py` è `None`, lo script usa il fallback.

- [ ] **Step 5: Genera**

Run: `docker compose exec -T api python -m app.gen_intro`
Expected: 12 righe `[n] …: situation=5..8 dialog=4..6 notes=2..3`. Tempo: ~15 s a scenario. Se uno fallisce con `RuntimeError … dialetto`, rilancia solo quello: `docker compose exec -T api python -m app.gen_intro --scenario N`.

- [ ] **Step 6: Revisione rapida dei contenuti**

Run:
```bash
python3 - <<'EOF'
import json, glob
for f in sorted(glob.glob('api/app/seed_content/*.json')):
    d = json.load(open(f)); i = d['intro']
    print(f"\n### {d['week_number']} {d['slug']}")
    print("SIT:", " / ".join(l['de'] for l in i['situation'][:3]))
    print("DLG:", " / ".join(f"{t['speaker']}: {t['de']}" for t in i['dialog'][:3]))
    print("NOTE:", " / ".join(i['notes_it']))
EOF
```
Expected: frasi in Hochdeutsch, dialogo con speaker "Ich" e ruolo dello scenario, note in italiano pertinenti. Se un intro è fuori tema, rigeneralo con `--scenario N`.

- [ ] **Step 7: Test e seed sul DB live**

Run: `docker compose exec -T api python -m pytest tests/test_seed.py -q && docker compose exec -T api python -m app.seed && docker compose exec -T db psql -U deutsch deutsch_tutor -tAc "select week_number, jsonb_array_length(intro->'situation') from scenarios order by 1;"`
Expected: test PASS; `Seed completato: 0 scenari creati, 12 aggiornati, 0 vocaboli creati`; 12 righe con 5–8.

- [ ] **Step 8: Commit**

```bash
git add api/app/seed.py api/app/gen_intro.py api/app/seed_content api/tests/test_seed.py api/tests/test_api_integration.py
git commit -m "feat(seed): Einstieg per gli scenari 1-12 (JSON generati) + applicazione parziale dei campi

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: API: lezione parte in `intro`, `LessonDetail.intro` e `intro_collapsed`

**Files:**
- Modify: `api/app/routers/lessons.py` (`create_lesson`)
- Modify: `api/app/services.py` (`build_lesson_detail`, nuova `scenario_has_completed_lesson`)
- Modify: `api/app/schemas.py` (`LessonDetail`)
- Test: `api/tests/test_api_integration.py`

**Interfaces:**
- Consumes: `lesson_state.first_phase(lesson_type)`, `LessonPhase.intro`, `Scenario.intro`.
- Produces: `LessonDetail.intro: dict | None`, `LessonDetail.intro_collapsed: bool`; `services.scenario_has_completed_lesson(session, scenario_id) -> bool`.

- [ ] **Step 1: Test di integrazione**

In `api/tests/test_api_integration.py`, in `test_full_lesson_flow` sostituisci il blocco "1. crea lezione":

```python
        # 1. crea lezione: parte dall'Einstieg (intro), prima lezione dello scenario → completa
        r = await client.post("/api/lessons")
        assert r.status_code == 200
        lesson = r.json()
        lesson_id = lesson["id"]
        assert lesson["current_phase"] == "intro"
        assert lesson["status"] == "in_progress"
        assert lesson["intro"] is not None
        assert len(lesson["intro"]["situation"]) >= 5
        assert lesson["intro_collapsed"] is False
        assert lesson["warmup_words"] is None

        # 1b. avanti → warmup, indietro → intro, avanti → warmup
        r = await client.post(f"/api/lessons/{lesson_id}/advance", json={})
        lesson = r.json()
        assert lesson["current_phase"] == "warmup"
        assert len(lesson["warmup_words"]) == 8
        r = await client.post(f"/api/lessons/{lesson_id}/back", json={})
        assert r.json()["current_phase"] == "intro"
        r = await client.post(f"/api/lessons/{lesson_id}/advance", json={})
        lesson = r.json()
        assert lesson["current_phase"] == "warmup"
        assert len(lesson["warmup_words"]) == 8
```

Alla fine dello stesso test, dopo il blocco "9. endpoint aggregati", aggiungi:

```python
        # 10. seconda lezione dello stesso scenario: intro compressa
        r = await client.post("/api/lessons")
        assert r.status_code == 200
        second = r.json()
        assert second["scenario_id"] == lesson["scenario_id"]
        assert second["current_phase"] == "intro"
        assert second["intro_collapsed"] is True
```

Cerca nel file ogni altro test che dopo `POST /api/lessons` assume `current_phase == "warmup"` o usa subito `warmup_words`/`warmup/answer`: inserisci prima `await client.post(f"/api/lessons/{lesson_id}/advance", json={})` (una volta). I test che forzano `UPDATE lessons SET lesson_type='review', current_phase='test'` via SQL non cambiano. Se un test crea una lezione `review` (`lesson_type='review'`) tramite `POST /api/lessons` dopo aver impostato lo stato del planner, verifica che parta in `warmup`:

```python
        assert r.json()["current_phase"] == "warmup"
```

- [ ] **Step 2: Esegui, deve fallire**

Run: `docker compose exec -T api python -m pytest tests/test_api_integration.py -q`
Expected: FAIL (`current_phase == 'warmup'`, chiave `intro` assente).

- [ ] **Step 3: Schema**

In `api/app/schemas.py`, classe `LessonDetail`, dopo `swiss_variants: list[dict]`:

```python
    intro: dict | None = None
    intro_collapsed: bool = False
```

- [ ] **Step 4: Services**

In `api/app/services.py` aggiungi prima di `build_lesson_detail`:

```python
async def scenario_has_completed_lesson(session: AsyncSession, scenario_id: int) -> bool:
    """Vero se esiste almeno una lezione completata per lo scenario (l'Einstieg si comprime)."""
    found = await session.scalar(
        select(Lesson.id)
        .where(Lesson.scenario_id == scenario_id, Lesson.status == LessonStatus.completed)
        .limit(1)
    )
    return found is not None
```

In `build_lesson_detail`, nel dict di ritorno dopo `"swiss_variants": …`:

```python
        "intro": scenario.intro,
        "intro_collapsed": await scenario_has_completed_lesson(session, scenario.id),
```

- [ ] **Step 5: Router**

In `api/app/routers/lessons.py`, `create_lesson`: sostituisci `current_phase=LessonPhase.warmup,` con

```python
        current_phase=LessonPhase(lesson_state.first_phase(lesson_type.value)),
```

- [ ] **Step 6: Suite completa**

Run: `docker compose exec -T api python -m pytest -q`
Expected: PASS.

- [ ] **Step 7: Verifica manuale sul live (nessuna lezione aperta: `resume_lesson_id` è null)**

Run: `curl -s -X POST http://localhost:8000/api/lessons | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['current_phase'], d['intro_collapsed'], len(d['intro']['situation']))"`
Expected: `intro False 5..8`. Poi rimetti il live pulito (la lezione è di prova): `curl -s -X POST http://localhost:8000/api/lessons/<id>/abandon`. Nota: una lezione `abandoned` fa ripartire il planner da `base`, quindi lo stato utente non cambia.

- [ ] **Step 8: Commit**

```bash
git add api/app/routers/lessons.py api/app/services.py api/app/schemas.py api/tests/test_api_integration.py
git commit -m "feat(api): nuova lezione parte in intro; LessonDetail.intro + intro_collapsed

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Frontend: tipi API e refactor di `Lesson.tsx` in un file per fase

**Files:**
- Modify: `web/lib/api.ts` (`LessonDetail`, `PHASES`, `PHASE_LABELS`, nuovi tipi `Intro*`)
- Create: `web/components/screens/lesson/WarmupPhase.tsx`, `TestPhase.tsx`, `PrepPhase.tsx`, `RoleplayPhase.tsx`, `HarvestPhase.tsx`, `SwissPhase.tsx`, `KeyPhraseCard.tsx`
- Modify: `web/components/screens/Lesson.tsx` (diventa orchestratore: importa le fasi)

**Interfaces:**
- Produces: `IntroLine {de, it}`, `IntroTurn {speaker, de, it}`, `LessonIntro {situation: IntroLine[]; dialog: IntroTurn[]; notes_it: string[]}`; `LessonDetail.intro: LessonIntro | null`, `LessonDetail.intro_collapsed: boolean`, `current_phase` include `"intro"`; `PHASES = ["intro","warmup","prep","roleplay","harvest","swiss"]`, `PHASE_LABELS.intro = "Einstieg"`. Ogni fase esporta una funzione con la stessa firma che aveva dentro `Lesson.tsx`. `KeyPhraseCard({kp}: {kp: KeyPhrase})` rende la card usata sia in `PrepPhase` sia nel bottom sheet.

- [ ] **Step 1: Tipi in `web/lib/api.ts`**

Dopo `SwissVariant` aggiungi:

```ts
export interface IntroLine {
  de: string;
  it: string;
}

export interface IntroTurn {
  speaker: string;
  de: string;
  it: string;
}

export interface LessonIntro {
  situation: IntroLine[];
  dialog: IntroTurn[];
  notes_it: string[];
}
```

In `LessonDetail`: `current_phase: "intro" | "warmup" | "prep" | "roleplay" | "harvest" | "swiss" | "test" | null;` e dopo `swiss_variants` aggiungi `intro: LessonIntro | null;` e `intro_collapsed: boolean;`.

`PHASES` e `PHASE_LABELS`:

```ts
export const PHASES = ["intro", "warmup", "prep", "roleplay", "harvest", "swiss"] as const;
export const PHASE_LABELS: Record<string, string> = {
  intro: "Einstieg",
  warmup: "Aufwärmen",
  prep: "Vorbereitung",
  roleplay: "Rollenspiel",
  harvest: "Ernte",
  swiss: "Schweiz",
};
```

- [ ] **Step 2: Sposta le fasi in file separati (nessun cambio di comportamento)**

Crea `web/components/screens/lesson/KeyPhraseCard.tsx`:

```tsx
import type { KeyPhrase } from "@/lib/api";

export function KeyPhraseCard({ kp }: { kp: KeyPhrase }) {
  return (
    <div className="mb-2.5 rounded-[14px] border border-border bg-card p-3.5">
      <div className="flex justify-between">
        <div className="font-serif text-base font-semibold">{kp.de}</div>
        <div className="text-[13px] text-muted">{kp.it}</div>
      </div>
      <div className="mt-1.5 text-[13px] italic text-secondary">„{kp.example}"</div>
    </div>
  );
}
```

Per ciascuna funzione `WarmupPhase`, `TestPhase`, `PrepPhase`, `RoleplayPhase`, `HarvestPhase`, `SwissPhase` in `Lesson.tsx`: taglia la funzione (con le interfacce e gli helper che usa solo lei: `WarmupState` → WarmupPhase; `TestState`, `escapeRegex`, `blankExample` → TestPhase) e incollala in `web/components/screens/lesson/<Nome>.tsx` con `"use client";` in testa, `export function …`, e gli import necessari da `@/lib/api` e `@/components/ui`. `PrepPhase` usa `KeyPhraseCard`:

```tsx
"use client";

import type { LessonDetail } from "@/lib/api";
import { KeyPhraseCard } from "./KeyPhraseCard";

export function PrepPhase({ lesson }: { lesson: LessonDetail }) {
  return (
    <div>
      <div className="font-serif text-xl font-semibold">Vorbereitung</div>
      <div className="mb-4 text-[13px] text-muted">Preparazione · le espressioni chiave dello scenario</div>
      {lesson.key_phrases.map((kp, i) => <KeyPhraseCard key={i} kp={kp} />)}
    </div>
  );
}
```

In `Lesson.tsx` importa le fasi:

```tsx
import { WarmupPhase } from "./lesson/WarmupPhase";
import { TestPhase } from "./lesson/TestPhase";
import { PrepPhase } from "./lesson/PrepPhase";
import { RoleplayPhase } from "./lesson/RoleplayPhase";
import { HarvestPhase } from "./lesson/HarvestPhase";
import { SwissPhase } from "./lesson/SwissPhase";
import { KeyPhraseCard } from "./lesson/KeyPhraseCard";
```

e nel bottom sheet "Espressioni chiave" sostituisci il markup ripetuto con `{lesson.key_phrases.map((kp, i) => <KeyPhraseCard key={i} kp={kp} />)}`. Rimuovi gli import ora inutilizzati (`useRef`, `TestWord`, `WarmupWord`, `SourceTag`, …): `tsc` li segnala solo se `noUnusedLocals` è attivo, quindi controlla a mano gli import in testa.

- [ ] **Step 3: Typecheck**

Run: `cd web && npx tsc --noEmit -p . && cd ..`
Expected: nessun errore.

- [ ] **Step 4: Build immagine e verifica che la lezione si apra**

Run: `docker compose build web 2>&1 | grep -iE "error|failed" ; docker compose up -d web && sleep 5 && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3100`
Expected: nessun error, `200`. Apri `http://localhost:3100`, tab Lezione: la pagina si carica (la fase `intro` non è ancora renderizzata: sotto l'indicatore non c'è contenuto, è atteso fino al Task 7).

- [ ] **Step 5: Commit**

```bash
git add web/lib/api.ts web/components/screens/Lesson.tsx web/components/screens/lesson
git commit -m "refactor(web): Lesson.tsx spezzato in un file per fase; tipi intro in api.ts

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Frontend: `IntroPhase`, indicatore a 6 fasi, Indietro dal warmup

**Files:**
- Create: `web/components/screens/lesson/IntroPhase.tsx`
- Modify: `web/components/ui.tsx` (`PhaseIndicator`)
- Modify: `web/components/screens/Lesson.tsx` (render fase, bottone Indietro, freccia abbandona)

**Interfaces:**
- Consumes: `LessonDetail.intro`, `LessonDetail.intro_collapsed`, `PHASES`, `PHASE_LABELS`, `REVIEW_PHASES`, `REVIEW_PHASE_LABELS` da `@/lib/api`.
- Produces: `IntroPhase({ lesson }: { lesson: LessonDetail })`.

- [ ] **Step 1: `IntroPhase`**

Crea `web/components/screens/lesson/IntroPhase.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { LessonDetail } from "@/lib/api";

export function IntroPhase({ lesson }: { lesson: LessonDetail }) {
  const [expanded, setExpanded] = useState(!lesson.intro_collapsed);
  const intro = lesson.intro;

  if (!intro) {
    return (
      <div>
        <div className="font-serif text-xl font-semibold">Einstieg</div>
        <div className="mb-4 text-[13px] text-muted">La situazione</div>
        <div className="rounded-[14px] border border-dashed border-border p-4 text-sm text-muted">
          Nessuna introduzione per questo scenario. Premi Avanti per iniziare.
        </div>
      </div>
    );
  }

  if (!expanded) {
    return (
      <div>
        <div className="font-serif text-xl font-semibold">Einstieg</div>
        <div className="mb-4 text-[13px] text-muted">La situazione · già letta in una lezione precedente</div>
        <div className="rounded-[14px] border border-border bg-card p-3.5">
          {intro.situation.slice(0, 2).map((line, i) => (
            <div key={i} className="font-serif text-base">{line.de}</div>
          ))}
          <button
            onClick={() => setExpanded(true)}
            className="mt-3 rounded-btn border border-border px-4 py-2 text-sm font-semibold text-primary"
          >
            Rileggi
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="font-serif text-xl font-semibold">Einstieg</div>
      <div className="mb-4 text-[13px] text-muted">La situazione · leggi prima di iniziare</div>

      <div className="mb-3 rounded-[14px] border border-border bg-card p-3.5">
        {intro.situation.map((line, i) => (
          <div key={i} className={i > 0 ? "mt-2.5" : ""}>
            <div className="font-serif text-base leading-snug">{line.de}</div>
            <div className="text-[13px] text-muted">{line.it}</div>
          </div>
        ))}
      </div>

      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Beispieldialog · esempio</div>
      <div className="mb-3 flex flex-col gap-2">
        {intro.dialog.map((turn, i) => {
          const mine = turn.speaker === "Ich";
          return (
            <div key={i} className={`max-w-[85%] ${mine ? "self-end" : "self-start"}`}>
              <div className={`text-[10px] ${mine ? "text-right" : ""} text-muted`}>{turn.speaker}</div>
              <div
                className={`rounded-[14px] px-3 py-2 text-sm ${
                  mine ? "rounded-tr-sm bg-accent text-surface" : "rounded-tl-sm bg-card border border-border"
                }`}
              >
                <div>{turn.de}</div>
                <div className={`mt-0.5 text-[12px] ${mine ? "text-surface/80" : "text-muted"}`}>{turn.it}</div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Da sapere</div>
      <ul className="rounded-[14px] border border-border bg-card p-3.5 pl-7 text-sm text-secondary">
        {intro.notes_it.map((note, i) => (
          <li key={i} className={`list-disc ${i > 0 ? "mt-1.5" : ""}`}>{note}</li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2: `PhaseIndicator` con etichette da `api.ts` e 6 fasi**

In `web/components/ui.tsx` sostituisci `PhaseIndicator`:

```tsx
import { PHASES, PHASE_LABELS, REVIEW_PHASES, REVIEW_PHASE_LABELS } from "@/lib/api";

export function PhaseIndicator({ phase, lessonType = "base" }: { phase: string | null; lessonType?: string }) {
  const isReview = lessonType === "review";
  const phases: readonly string[] = isReview ? REVIEW_PHASES : PHASES;
  const labels: Record<string, string> = isReview ? REVIEW_PHASE_LABELS : PHASE_LABELS;
  const idx = phase ? phases.indexOf(phase) : -1;
  const dense = phases.length >= 6;
  return (
    <div className="flex gap-1.5">
      {phases.map((key, i) => {
        const barColor = i === idx ? "bg-accent" : i < idx ? "bg-ink" : "bg-border";
        const textColor = i === idx ? "text-primary" : "text-faint";
        const weight = i === idx ? "font-semibold" : "font-medium";
        return (
          <div key={key} className="min-w-0 flex-1">
            <div className={`h-1.5 rounded ${barColor}`} />
            <div className={`mt-1.5 truncate text-center ${dense ? "text-[9px]" : "text-[10px]"} ${textColor} ${weight}`}>
              {labels[key]}
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

Aggiungi l'import in testa a `ui.tsx` (verifica che `ui.tsx` non venga importato da `api.ts`, altrimenti c'è un ciclo: `api.ts` non importa componenti, quindi è sicuro).

- [ ] **Step 3: `Lesson.tsx`: render, Indietro, freccia abbandona**

In `Lesson.tsx`:
- import `IntroPhase` da `./lesson/IntroPhase`;
- `const isFirstPhase = phase === "intro" || (isReview && phase === "warmup");` (sostituisce `phase === "warmup"`);
- la freccia "abbandona" in alto: condizione `{(phase === "intro" || phase === "warmup") && (…)}` invece di `{phase === "warmup" && (…)}`;
- render: aggiungi `{phase === "intro" && <IntroPhase lesson={lesson} />}` prima della riga del warmup;
- footer: il bottone "Indietro" compare per `phase === "roleplay" || (phase === "warmup" && !isReview)`:

```tsx
          {phase === "roleplay" || (phase === "warmup" && !isReview) ? (
            <button onClick={goBack} className="flex-1 rounded-btn border border-border bg-card py-3 text-sm font-semibold text-primary">
              Indietro
            </button>
          ) : (
            <div className="flex-1" />
          )}
```

- il bottone Avanti in fase `intro` è sempre abilitato (nessuna condizione aggiuntiva). Il testo resta "Avanti".

- [ ] **Step 4: Typecheck, build, verifica visiva**

Run: `cd web && npx tsc --noEmit -p . && cd .. && docker compose build web 2>&1 | grep -iE "error|failed" ; docker compose up -d web`
Expected: nessun errore.

Verifica in browser (`http://localhost:3100`, viewport mobile 390 px): apri Lezione → fase "Einstieg" con racconto, dialogo a bolle e note; indicatore a 6 voci leggibile; Avanti → Aufwärmen con bottone Indietro; Indietro → Einstieg. Fai uno screenshot della fase completa e salvalo in `docs/reports/screenshots/einstieg-full.png`. Per la versione compressa: completa una lezione oppure, sul DB di test, verifica via API (`intro_collapsed: true` dopo una lezione completata) e controlla il ramo `!expanded` con lo stesso stile della card compressa.

- [ ] **Step 5: Commit**

```bash
git add web/components/screens/lesson/IntroPhase.tsx web/components/ui.tsx web/components/screens/Lesson.tsx docs/reports/screenshots/einstieg-full.png
git commit -m "feat(web): fase Einstieg (situazione, dialogo, note), indicatore a 6 fasi, Indietro dal warmup

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Overlay dev per il web + documentazione

**Files:**
- Modify: `docker-compose.override.yml`
- Modify: `README.md` (sezione comandi), `docs/decisions.md`

- [ ] **Step 1: Overlay dev**

In `docker-compose.override.yml` aggiungi il servizio `web` accanto ad `api`:

```yaml
  web:
    build:
      context: ./web
      target: deps
    command: sh -c "npm run dev -- -H 0.0.0.0 -p 3000"
    environment:
      NODE_ENV: development
      NEXT_TELEMETRY_DISABLED: "1"
    volumes:
      - ./web:/app
      - web_node_modules:/app/node_modules
      - web_next:/app/.next

volumes:
  web_node_modules:
  web_next:
```

Il target `deps` del `web/Dockerfile` ha già `node_modules` installati; il volume `web_node_modules` li conserva separati dal mount del codice. Verifica che il servizio `web` in `docker-compose.yml` non definisca `command` (lo definisce solo l'override).

- [ ] **Step 2: Avvia e verifica il reload**

Run: `docker compose up -d --build web && sleep 15 && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3100 && docker compose logs web --tail 5`
Expected: `200`, log con `Ready in …` di Next dev. Modifica una stringa in `IntroPhase.tsx` (es. il sottotitolo), ricarica: cambia senza rebuild. Ripristina la stringa.

- [ ] **Step 3: Docs**

In `README.md`, sezione comandi, aggiungi:

```
- Dev: `docker compose up -d` monta `api/app` (uvicorn --reload) e `web` (next dev): le modifiche si vedono senza rebuild.
- Produzione (senza override): `docker compose -f docker-compose.yml up -d --build`.
- Contenuti scenari: `docker compose exec -T api python -m app.content_gen --scenario N` (meta+vocab+intro), `python -m app.gen_intro` (solo Einstieg), poi `python -m app.seed --update`.
- Test: `docker compose exec -T api python -m pytest -q` (usa il DB `deutsch_tutor_test`, creato e migrato automaticamente).
```

In `docs/decisions.md` aggiungi:

```
## 2026-09-11 — Fase Einstieg

- Nuova prima fase `intro` (non nel ripasso): racconto della situazione in Hochdeutsch con traduzione, mini-dialogo, note pragmatiche in italiano. Contenuto statico per scenario in `scenarios.intro`, generato da `app.gen_intro`/`app.content_gen` con validazione anti-dialetto, salvato nei JSON del seed. Dopo la prima lezione completata dello scenario l'Einstieg è compresso ("Rileggi").
- Indietro consentito anche `warmup → intro`.
- `Lesson.tsx` spezzato in `components/screens/lesson/` (un file per fase).
- Overlay dev anche per `web` (`next dev` con mount): niente rebuild per le modifiche frontend.
```

- [ ] **Step 4: Suite finale**

Run: `docker compose exec -T api python -m pytest -q && cd web && npx tsc --noEmit -p . && cd ..`
Expected: tutti i test PASS, typecheck pulito.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.override.yml README.md docs/decisions.md
git commit -m "chore(dev): overlay next dev per web; docs Einstieg e comandi

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
