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
cp infra/.env.example .env   # opzionale: i default coprono lo sviluppo locale
make up                      # build + avvio di web (:3000), api (:8000), db
make migrate                 # applica le migrazioni Alembic
make seed                    # popola il DB (idempotente)
```

Verifiche:

- Frontend: http://localhost:3000
- API health: `curl http://localhost:8000/api/health` → `{"status":"ok"}`
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

## Configurazione

Le variabili vivono in `.env` alla root (copia da `infra/.env.example`). I default coprono
lo sviluppo locale.

- `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` — credenziali del DB
- `POSTGRES_PORT` — porta host del DB (default `5433`, per non collidere con un Postgres locale)
- `DATABASE_URL` — usata dall'API (composta automaticamente in Docker)

Le chiavi LLM (Anthropic cloud + endpoint locale OpenAI-compatibile) arrivano in Fase 3.

## Riferimenti

- Piano di implementazione: `docs/deutsch-tutor-implementation-plan_1.md`
- Design di riferimento: `design/Deutsch-Tutor.dc.html`
- Schema DB (ERD): `docs/schema.md`
