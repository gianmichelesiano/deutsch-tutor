# Decisioni registrate

Decisioni di progetto prese durante l'implementazione, con la motivazione. Aggiungere una voce per ogni decisione rilevante.

## 2026-09-09 — Fase 3

### Korrektor in-memory (registro di task asincroni) — accettato per single-user
Il Korrektor gira in background con `asyncio.create_task` e un registro in-memory (`app/korrektor.py`), keyed per lezione; `advance→harvest` attende i pendenti con timeout.
- **Motivo**: app personale single-user, una sola istanza uvicorn; semplice e senza dipendenze extra.
- **Limite**: non sopravvive al restart del processo e non funziona in multi-worker/multi-istanza (i task non sono condivisi).
- **Se mai servirà** (multi-utente o multi-istanza): sostituire con una coda persistente (Redis/Postgres `SELECT ... FOR UPDATE SKIP LOCKED`).

### Thinking disattivato per il roleplay (modello locale reasoning)
DeepSeek V4 Flash è un reasoning model: con `max_tokens=200` consumava i token in `reasoning_content`. `local_llm_thinking_disabled=true` invia `thinking={"type":"disabled"}`.
- **Motivo**: il roleplay deve rispondere in fretta e con JSON conciso; il ragionamento è inutile per frasi brevi in Alltagsdeutsch.

### `repeat_penalty=1.15` (non `frequency_penalty`)
Verificato che il server ds4 accetta entrambi; scelto `repeat_penalty` (convenzione llama.cpp, >1 penalizza).

## 2026-09-11 — Contenuti scenari 3–12 e DB di test separato

- **LLM**: provider "local" puntato a DeepSeek remoto (`https://api.deepseek.com`, modello `deepseek-flash`, chiave in `LOCAL_LLM_API_KEY`). Stesso client OpenAI-compatibile usato prima per llama.cpp. I turni dell'agente vengono inviati come `assistant` (DeepSeek rifiuta ruoli sconosciuti).
- **Scenari 3–12** generati con `app.content_gen` e salvati in `api/app/seed_content/scenario-NN.json`; `app.seed` li carica (contenuti applicati se lo scenario è vuoto o con `--update`; vocaboli mai sovrascritti). Il generatore rifiuta e rigenera la parte "meta" se contiene Schweizerdeutsch (`dialect_hits`, max 3 tentativi con feedback al modello): il dialetto va solo in `swiss_variants.swiss`.
- **Test su DB separato**: `tests/conftest.py` riscrive `DATABASE_URL` verso `<db>_test`, lo crea, migra (Alembic) e seeda. Motivo: i test di integrazione fanno `TRUNCATE lessons, …` e in precedenza giravano sul DB live, cancellando le lezioni reali. La fixture `clean_db` rifiuta di girare su un DB che non termina in `_test`.
