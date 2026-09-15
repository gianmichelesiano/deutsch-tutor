# Deutsch-Tutor

Personal (single-user) web app for learning German through 30-minute lessons
built around roleplay in everyday scenarios. Teaching priority: **vocabulary**.

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (App Router) + Tailwind CSS — `web/` |
| Backend | FastAPI (Python 3.12) + Pydantic v2 + SQLAlchemy 2 (async) + Alembic — `api/` |
| DB | PostgreSQL 16 — `db` service |
| Deploy | Docker Compose (Portainer-compatible), accessed over Tailscale |

## Layout

```
web/     Next.js App Router
api/     FastAPI + Alembic + seed
infra/   .env.example
docs/    plan, DB schema, phase reports
```

`docker-compose.yml` sits at the **root** so that plain `docker compose up` works.

## Quick start

```bash
./start.sh                   # starts db + api (:8118) + web (:3100), migrates, seeds, waits for services
```

Options: `--build` (rebuild images), `--logs` (follow logs), `--prod` (no dev override).
Manual equivalent:

```bash
cp infra/.env.example .env   # optional: defaults cover local development
make up                      # build + start web (:3100), api (:8118), db
make migrate                 # apply Alembic migrations
make seed                    # populate the DB (idempotent)
```

Checks:

- Frontend: http://localhost:3100
- API health: `curl http://localhost:8118/api/health` → `{"status":"ok"}`
- DB: `make ps` (the `db` service must be healthy)

## Commands

| Command | Description |
|---|---|
| `make up` | build + start the stack |
| `make down` | stop the stack |
| `make migrate` | `alembic upgrade head` in the `api` container |
| `make seed` | idempotent DB seed |
| `make seed-update` | seed + overwrite the content of existing scenarios (for the Planer) |
| `make test` | unit tests (no DB) |
| `make test-integration` | tests against a real DB (requires `make migrate`) |
| `make reset` | rebuild from scratch, **deleting the data** (volume) |
| `make logs` | follow logs |

### Development

- With `docker-compose.override.yml` present (the local default), `docker compose up -d` mounts the code:
  `api/app` runs under `uvicorn --reload`, `web` under `next dev`. Changes show up without a rebuild.
- Production, without the override: `docker compose -f docker-compose.yml up -d --build`.
- Tests: `docker compose exec -T api python -m pytest -q`. They run against the `deutsch_tutor_test` DB,
  which `api/tests/conftest.py` creates, migrates and seeds automatically. Never against the app DB.

### Scenario content

The content of scenarios 3–12 (and the Einstieg of all of them) lives in `api/app/seed_content/scenario-NN.json`
and is applied by the seed. To regenerate it with the configured model:

```bash
docker compose exec -T api python -m app.content_gen --scenario N   # meta + vocab + intro, prints JSON
docker compose exec -T api python -m app.gen_intro [--scenario N]   # Einstieg only, writes the JSON
docker compose exec -T api python -m app.seed --update              # apply to the DB
```

The generator rejects and regenerates texts written in Schweizerdeutsch: the dialect belongs only in
`swiss_variants.swiss`.

## Configuration

Variables live in `.env` at the root (copy from `infra/.env.example`). The defaults cover
local development.

- `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` — DB credentials
- `POSTGRES_PORT` — host port for the DB (default `5433`, to avoid clashing with a local Postgres)
- `WEB_PORT` — host port for the frontend (default `3100`; `3000` is taken by another project)
- `API_PORT` — host port for the backend (default `8118`; `8000` is too common)
- `DATABASE_URL` — used by the API (composed automatically in Docker)

### LLM

The "local" provider is an OpenAI-compatible endpoint: remote DeepSeek by default, llama.cpp
running locally as an alternative.

- `LOCAL_LLM_BASE_URL` — default `https://api.deepseek.com`; for llama.cpp e.g. `http://host.docker.internal:8008/v1`
- `LOCAL_LLM_API_KEY` — DeepSeek key (https://platform.deepseek.com/api_keys); empty for llama.cpp
- `LOCAL_LLM_MODEL` — default `deepseek-flash`
- `LOCAL_LLM_THINKING_DISABLED` — `true` (default): no reasoning during roleplay
- `LOCAL_LLM_REPEAT_PENALTY` — llama.cpp only (>1 penalizes); `0` = not sent
- `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` — Anthropic cloud (fallback in `auto` mode)
- `LLM_PROVIDER_MODE` — `auto` | `local-only` | `cloud-only` | `mock`

## References

- Implementation plan: `docs/deutsch-tutor-implementation-plan.md`
- Reference design: `design/Deutsch-Tutor.dc.html`
- DB schema (ERD): `docs/schema.md`
