# Deutsch-Tutor

App web personale (single user) per imparare il tedesco (A2→B1) con lezioni da 30 minuti
basate su roleplay in scenari quotidiani. Priorità didattica: **vocabolario**.

## Stack

| Livello | Tecnologia |
|---|---|
| Frontend | Next.js (App Router) + Tailwind CSS — `web/` |
| Backend | FastAPI (Python 3.12) + Pydantic v2 + SQLAlchemy 2 (async) + Alembic — `api/` |
| DB | PostgreSQL 16 — servizio `db` |
| Deploy | Docker Compose (compatibile Portainer), accesso via Tailscale |

## Struttura

```
web/     Next.js App Router
api/     FastAPI + Alembic + seed
infra/   .env.example
docs/    piano, schema DB, report di fase
```

`docker-compose.yml` è alla **root** per far funzionare letteralmente `docker compose up`.

## Avvio rapido

```bash
./start.sh                   # avvia db + api (:8118) + web (:3100), migra, seeda, attende i servizi
```

Opzioni: `--build` (rebuild immagini), `--logs` (segue i log), `--prod` (senza override dev).
Equivalente manuale:

```bash
cp infra/.env.example .env   # opzionale: i default coprono lo sviluppo locale
make up                      # build + avvio di web (:3100), api (:8118), db
make migrate                 # applica le migrazioni Alembic
make seed                    # popola il DB (idempotente)
```

Verifiche:

- Frontend: http://localhost:3100
- API health: `curl http://localhost:8118/api/health` → `{"status":"ok"}`
- DB: `make ps` (il servizio `db` deve risultare healthy)

## Comandi

| Comando | Descrizione |
|---|---|
| `make up` | build + avvio dello stack |
| `make down` | ferma lo stack |
| `make migrate` | `alembic upgrade head` nel container `api` |
| `make seed` | seed idempotente del DB |
| `make seed-update` | seed + sovrascrive i contenuti degli scenari esistenti (per il Planer) |
| `make test` | test unitari (senza DB) |
| `make test-integration` | test su DB reale (richiede `make migrate`) |
| `make reset` | ricostruisce da zero, **cancellando i dati** (volume) |
| `make logs` | segue i log |

### Sviluppo

- Con `docker-compose.override.yml` presente (default in locale), `docker compose up -d` monta il codice:
  `api/app` gira con `uvicorn --reload`, `web` con `next dev`. Le modifiche si vedono senza rebuild.
- Produzione, senza override: `docker compose -f docker-compose.yml up -d --build`.
- Test: `docker compose exec -T api python -m pytest -q`. Girano sul DB `deutsch_tutor_test`,
  creato, migrato e seedato automaticamente da `api/tests/conftest.py`. Mai sul DB dell'app.

### Contenuti degli scenari

I contenuti degli scenari 3–12 (e l'Einstieg di tutti) vivono in `api/app/seed_content/scenario-NN.json`
e vengono applicati dal seed. Per rigenerarli con il modello configurato:

```bash
docker compose exec -T api python -m app.content_gen --scenario N   # meta + vocab + intro, stampa JSON
docker compose exec -T api python -m app.gen_intro [--scenario N]   # solo Einstieg, scrive il JSON
docker compose exec -T api python -m app.seed --update              # applica al DB
```

Il generatore rifiuta e rigenera i testi in Schweizerdeutsch: il dialetto va solo in `swiss_variants.swiss`.

## Configurazione

Le variabili vivono in `.env` alla root (copia da `infra/.env.example`). I default coprono
lo sviluppo locale.

- `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` — credenziali del DB
- `POSTGRES_PORT` — porta host del DB (default `5433`, per non collidere con un Postgres locale)
- `WEB_PORT` — porta host del frontend (default `3100`, la `3000` è usata da un altro progetto)
- `API_PORT` — porta host del backend (default `8118`, la `8000` è troppo comune)
- `DATABASE_URL` — usata dall'API (composta automaticamente in Docker)

### LLM

Il provider "local" è un endpoint OpenAI-compatibile: di default DeepSeek remoto, in alternativa
llama.cpp in locale.

- `LOCAL_LLM_BASE_URL` — default `https://api.deepseek.com`; per llama.cpp es. `http://host.docker.internal:8008/v1`
- `LOCAL_LLM_API_KEY` — chiave DeepSeek (https://platform.deepseek.com/api_keys); vuota per llama.cpp
- `LOCAL_LLM_MODEL` — default `deepseek-flash`
- `LOCAL_LLM_THINKING_DISABLED` — `true` (default): niente reasoning nel roleplay
- `LOCAL_LLM_REPEAT_PENALTY` — solo llama.cpp (>1 penalizza); `0` = non inviata
- `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` — cloud Anthropic (fallback in modalità `auto`)
- `LLM_PROVIDER_MODE` — `auto` | `local-only` | `cloud-only` | `mock`

## Riferimenti

- Piano di implementazione: `docs/deutsch-tutor-implementation-plan.md`
- Design di riferimento: `design/Deutsch-Tutor.dc.html`
- Schema DB (ERD): `docs/schema.md`
