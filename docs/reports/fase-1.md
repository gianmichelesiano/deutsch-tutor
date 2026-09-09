# Report Fase 1 — Fondamenta

Data: 2026-09-09 · Autore: agente implementatore

## Cosa ho fatto

**Task 1.1 — Scaffolding repository**
- Monorepo in `deutsch-tutor/` con `web/` (Next.js App Router + Tailwind), `api/` (FastAPI + Pydantic v2 + SQLAlchemy 2 async + Alembic), `infra/` (`.env.example`), `docs/`.
- `docker-compose.yml` con 3 servizi: `db` (postgres:16-alpine), `api` (uvicorn, healthcheck), `web` (Next.js standalone).
- `Makefile` (`up/down/migrate/seed/test/test-integration/reset/logs/ps`) e `README.md` con i comandi.

**Task 1.2 — Schema DB (Alembic)**
- 8 enum native Postgres + 7 tabelle (`scenarios`, `vocab_items`, `vocab_progress`, `review_events`, `lessons`, `messages`, `user_sentences`), migrazione `0001_initial`.
- ERD in `docs/schema.md` (Mermaid + tabelle + enum).

**Task 1.3 — Seed contenuti**
- Seed idempotente (`app/seed.py` + `app/seed_data.py`): 12 scenari (titolo+descrizione), scenario 1 "Im Supermarkt" completo (10 key_phrases, 3 swiss_variants, 5 imprevisti, 4 goals, 40 vocaboli curati di cui i 20 della lezione pilota).
- Test: `test_health.py` (unit) e `test_seed.py` (integration).

## Accettazione dei task

| Criterio | Esito |
|---|---|
| `docker compose up` → web :3000 risponde | ✅ HTTP 200 (`<title>Deutsch-Tutor</title>`) |
| `GET /api/health` → 200 | ✅ `{"status":"ok"}` |
| DB raggiungibile | ✅ `db` healthy; migrate/seed funzionano |
| Migrazione applicata da zero | ✅ volume nuovo + `alembic upgrade head` → 7 tabelle + 8 enum |
| ERD in `/docs/schema.md` | ✅ |
| `make seed` idempotente | ✅ run 1 → "12 scenari, 40 vocaboli"; run 2 → "0, 0" |
| Scenario 1 completo in DB | ✅ 10/3/5/4 + 40 vocab |
| Test unitari / integrazione | ✅ 1 passed + 1 passed |

## Decisioni prese (routine, non "decisioni aperte")

1. **`docker-compose.yml` alla root** (non in `infra/`) per far funzionare letteralmente `docker compose up` come da accettazione; `infra/` contiene `.env.example`. *Deviazione strutturale documentata.*
2. **SQLAlchemy async** (`asyncpg`) + **Alembic async** (`env.py` con `asyncio.run`), coerente con le chiamate LLM async di Fase 3.
3. **Enum native Postgres** (8 tipi), come da piano ("enum").
4. **Prefisso API `/api`**: il piano scrive `/api/health` ma le route di Fase 2 senza prefisso; ho interpretato che tutte le route stiano sotto `/api` (quindi `/api/lessons`, ecc.).
5. **`de` include l'articolo** ("der Einkaufswagen") come nel design e nella lista seed; **`gender` = articolo** ("der"/"die"/"das") o `None`.
6. **Seed check-then-insert** (per `slug` e per `de`+`scenario_id`): idempotente ma non aggiorna righe esistenti.
7. **Dev deps nell'immagine api** (`pip install ".[dev]"`) per far girare `make test` nel container.
8. **Web**: build produzione `output: standalone`, `npm install` (nessun `package-lock.json` committato, per ora).
9. **Titoli scenari 6-12 provvisori** (2-5 dal mockup); descrizioni/`role_label` saranno rifiniti dal Planer (task 3.4).
10. **`llm_calls` NON creata**: non prevista dal task 1.2, arriva in Fase 3.
11. **Commit**: 1 commit `chore` per i documenti di partenza + 3 commit atomici `task 1.1/1.2/1.3`.

## Decisioni aperte (segnalate, NON decise)

Nessuna delle "Decisioni aperte" del piano ricade nella Fase 1. Promemoria per le fasi successive (uso i default proposti, non li ho scelti io):

- Modello locale specifico e parametri per il roleplay → Fase 3.
- Se il Korrektor interrompa il dialogo con `comprehensible=false` → Fase 3.
- Max turni roleplay (proposta: 12) → Fase 3.
- Home mostra la data (proposta: sì, `Intl.DateTimeFormat('it-CH')`) → Fase 4.
- Flashcard self-grading vs digitazione (proposta: v1 self-grading) → Fase 4.

## Dubbi

1. **Prefisso `/api`** (decisione 4 sopra): da confermare esplicitamente che le route di Fase 2 saranno `/api/lessons`, `/api/vocab`, ecc.
2. **`gender` come articolo** vs `m/f/n`: ho scelto "der/die/das" perché direttamente visualizzabile nel detail sheet (4.4) e coerente con la lista seed.
3. **`npm install` senza lockfile**: build riproducibile solo parzialmente; se serve, genero e committo `package-lock.json`.
4. Warning di deprecazione non bloccanti in pytest (Starlette `TestClient`/httpx e alias `anyio.abc.BlockingPortal`): da rivalutare in Fase 2.

## Cosa verificare manualmente

1. Aprire **http://localhost:3000** → placeholder "Deutsch-Tutor" (Fondamenta in corso, Fase 1).
2. `curl http://localhost:8000/api/health` → `{"status":"ok"}`.
3. `docker compose ps` → tutti e 3 i servizi `Up`/`healthy`.
4. `make reset` (opzionale) per un rebuild pulito da zero.
5. Rivedere i **titoli/descrizioni degli scenari 6-12** (provvisori, in attesa del Planer).
6. Validare lo **schema** (enum native, JSONB, FKs) contro le attese prima di procedere a Fase 2.

---

*Stop: attendo revisione prima di iniziare la Fase 2 (motore didattico).*
