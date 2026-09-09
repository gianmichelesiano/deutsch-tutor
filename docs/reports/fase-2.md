# Report Fase 2 — Motore didattico (backend, senza LLM)

Data: 2026-09-09 · Autore: agente implementatore

## Correzioni Fase 1 applicate (da revisione)

1. **Scenari 2–12** allineati alla sequenza definitiva (2 Zuhause und Nachbarn, 3 Schule: Elternabend und Lehrpersonen, 4 Wochenende mit Freunden, 5 Beim Arzt und in der Apotheke, 6 Büro und Small Talk, 7 Öffentlicher Verkehr und SBB, 8 Feste/Einladungen/Geschenke, 9 Im Restaurant, 10 Probleme: Reklamation/Reparatur/Hausverwaltung, 11 Meinungen und Erzählen, 12 Wiederholung) con titoli IT e descrizioni provvisorie.
2. **`--update`** al seed: `python -m app.seed --update` (o `make seed-update`) sovrascrive `key_phrases/swiss_variants/imprevisti/goals` (+ title/description/role_label) degli scenari esistenti.
3. **`package-lock.json`** generato e committato; `web/Dockerfile` passa a `npm ci`.
4. `gender` = articolo (der/die/das) e prefisso `/api` confermati (nessuna modifica necessaria).

## Cosa ho fatto

**Task 2.1 — Spaced repetition (`app/srs.py`, puro)**
- Intervalli `1 → 3 → 7 → 21` (capped), errore → torna a 1 giorno + `lapses += 1`.
- Consolidazione: 3 usi corretti in **3 lezioni diverse** (contati su `review_events` per `lesson_id` distinti). Il self-grading flashcard avanza l'intervallo ma **non** conta per la consolidazione (`correct_uses` fermo).
- `pick_due`/`rank` con priorità: dovuto → lapses alto → origine requested/error → più recente.
- Date sempre iniettate (`now`). Test: 11 casi (4 intervalli, reset, consolidazione, flashcard, is_due, ranking).

**Task 2.2 — Macchina a stati (`app/lesson_state.py`, pura) + schema**
- `warmup → prep → roleplay → harvest → swiss → completed`; salto consentito solo `swiss` (`harvest` + `skip_swiss`); indietro solo `roleplay → prep`; regola `> 6` → `variant`.
- Migrazione `0002`: colonna `lessons.current_phase` (il task 1.2 non la prevedeva ma 2.2 la richiede). Test: 8 casi.

**Task 2.3 — API REST (13 endpoint sotto `/api`)**
- `POST /lessons`, `GET /lessons/{id}`, `GET /lessons/current`, `POST .../advance`, `.../warmup/answer`, `.../roleplay/message`, `.../harvest/confirm`, `.../abandon`, `GET /vocab`, `GET /vocab/review-queue`, `POST /vocab/{id}/review`, `GET /progress`, `GET /home`.
- `app/services.py` (DB), `app/llm.py` (`MockLlmClient` deterministico), `app/parser.py` (parser `[ ]`), `app/schemas.py` (Pydantic), `app/routers/*`.
- Test d'integrazione del flusso completo (warmup→prep→roleplay→harvest→swiss→completed) con LLM mockato + test abandon/current.

## Accettazione

| Criterio | Esito |
|---|---|
| 2.1 test con date fittizie (4 intervalli, reset, consolidazione) | ✅ `tests/test_srs.py` 11 passed |
| 2.2 test transizioni + regola > 6 | ✅ `tests/test_lesson_state.py` 8 passed |
| 2.3 OpenAPI generato | ✅ 14 path sotto `/api` (FastAPI auto) |
| 2.3 integration test flusso completo con LLM mockato | ✅ `tests/test_api_integration.py` 2 passed |
| Suite completa | ✅ 23 unit + 3 integration passed |

## Decisioni prese (routine)

1. **SRS puro** (`srs.py` senza DB, date iniettate) come richiesto; il layer DB (`services.py`) costruisce `Progress`/`Candidate` e chiama le funzioni pure.
2. **"Dovuto" per la coda ripasso** = parole `seen`/`used` con `next_review_at <= now`. Le parole `new` **non** entrano nella coda flashcard (vengono introdotte nel warmup). → su DB solo seed, "parole in scadenza" = 0.
3. **Bootstrap warm-up**: alla prima lezione non c'è backlog di ripasso → le 8 parole sono tutte "nuove" (riempio gli slot di ripasso dal pool nuovo).
4. **Parole richieste `[ ]`**: parser deterministico + `vocab_items(source=requested)` con `de` = placeholder (il termine tedesco arriva dall'agente in Fase 3).
5. **harvest/confirm**: confermate → `seen` + dovute subito; deselezionate → `consolidated` (già note, fuori dal ripasso).
6. **`dialogue_closed`** salvato in `lessons.summary` (JSONB), nessuna nuova colonna.
7. **Planner semplificato** (`plan_next_lesson`): ciclo base→variant→incident→review→scenario successivo; regola > 6 → `variant` stesso scenario; abbandonata → `base` stesso scenario. Planner completo in Fase 3.
8. **`NullPool`** sull'engine (app single-user + evita connessioni legate a loop precedenti nei test asyncio) e **loop scope "session"** in pytest.
9. **Streak** in timezone `Europe/Zurich` (configurabile via `settings.timezone`).
10. **Ricoperta casuale del 10%** delle parole consolidate: **non implementata** (non richiesta dall'accettazione 2.1; annotata come rimanenza).

## Dubbi / punti da confermare

1. **Semantica "dovuto"** per le parole `new` (escluse dalla coda ripasso): interpretazione mia, da confermare (alternativa: includerle → "40 parole in scadenza" su seed fresco).
2. **`harvest`: deselezionata → `consolidated`** è una scelta pragmatica (la "già nota" esce dal ripasso); Fase 3 con Korrektor/harvest LLM la rifinirà.
3. **`de` placeholder** per le parole richieste finché non c'è l'agente reale (Fase 3).
4. **Planner semplificato**: la logica di avanzamento settimanale (4 lezioni/scenario) è una versione base; il Planer (task 3.4) la completerà.
5. **Downgrade migrazione 0002** scritto ma non eseguito (l'accettazione richiede solo l'upgrade da zero).

## ⚠️ Da verificare manualmente / problemi noti

1. **Il container `web` NON parte**: la porta host `:3000` è occupata da un dev server di un **altro progetto** (`ngft-ops-frontend`, `next-server` PID sul host). Non l'ho terminato perché non mio. Quando liberi la `:3000`, `docker compose up -d web` lo avvia. (La Fase 2 è solo backend, quindi non blocca.)
2. OpenAPI interattiva: http://localhost:8000/docs (14 path sotto `/api`).
3. `make test` (23 unit) e `make test-integration` (3 integration) nel container.
4. Prova reale della lezione via UI: arriva in Fase 4; per ora si può pilotare l'API con curl (sequenza in `tests/test_api_integration.py`).
5. Rivedere i titoli/descrizioni IT degli scenari 6–12 (provvisori, in attesa del Planer).

## Decisioni aperte (segnalate, NON decise)

Nessuna nuova rispetto al piano. Promemoria: modello locale/parametri roleplay, interruzione Korrektor su `comprehensible=false`, max turni roleplay (12), data in Home (sì), flashcard self-grading (v1) — tutte Fase 3/4.

---

*Stop: attendo revisione prima della Fase 3 (agenti LLM).*
