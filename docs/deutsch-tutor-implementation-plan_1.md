# Deutsch-Tutor — Piano di implementazione (v1.1, solo testo)

> v1.1 — integra il design di riferimento `design/Deutsch-Tutor_dc.html` (revisionato il 2026-09-09). Le modifiche rispetto a v1 sono marcate **[v1.1]**.

Documento per l'agente implementatore. Ogni task è autonomo, ha un output verificabile e un criterio di accettazione. Eseguire in ordine; non anticipare task successivi. Al termine di ogni fase produrre un breve report (cosa fatto, decisioni prese, dubbi) per la revisione.

## 0. Contesto e vincoli

**Scopo**: web app personale (single user) per imparare il tedesco (A2→B1) con lezioni da 30 minuti basate su roleplay in scenari quotidiani. Priorità didattica: **vocabolario**. La grammatica viene corretta solo se l'errore compromette la comprensione.

**Metodo validato in chat** (non modificare la struttura senza discuterla):
1. **Aufwärmen (5')** — 8 parole: 5 in ripasso (spaced repetition) + 3 nuove dello scenario. Per ognuna l'utente scrive una frase; feedback di una riga.
2. **Vorbereitung (3')** — scheda con 10 espressioni chiave dello scenario (DE + IT + esempio). Solo lettura.
3. **Rollenspiel (15')** — dialogo in personaggio. L'utente scrive solo in tedesco; se gli manca una parola scrive `[parola in italiano]`: l'agente fornisce il termine tedesco, lo usa nella propria risposta e lo aggiunge alla lista. Errori comprensibili → nessuna correzione, il dialogo continua con *recast* (l'agente riformula correttamente nella risposta). L'agente introduce un imprevisto realistico per dialogo.
4. **Wortschatz-Ernte (4')** — tabella DE/IT con: parole chieste via `[ ]`, parole sbagliate, 5 parole usate dall'agente e probabilmente nuove. L'utente deseleziona quelle già note; le altre entrano in ripasso.
5. **Schweizerdeutsch-Ecke (3')** — 3 varianti svizzere di frasi usate nel dialogo.

**Piano di studi**: 12 settimane, 1 scenario a settimana, ~40 parole target per scenario. 4 lezioni/settimana: base, variante, imprevisto, ripasso+test (15 parole in contesto, "completa la frase").

**Stack obbligato** (già in uso dall'utente):
- Frontend: Next.js (App Router), Tailwind.
- Backend: FastAPI (Python 3.12), Pydantic v2.
- DB: PostgreSQL.
- Deploy: Docker Compose (compatibile con Portainer). Accesso via Tailscale.
- LLM: ibrido. Locale via endpoint OpenAI-compatibile (llama.cpp / DeepSeek); cloud via Anthropic API. Il routing per compito è descritto nel task 3.1.

**Fuori scope v1**: voce (STT/TTS), multi-utente, mobile app nativa, gamification. Progettare però l'interfaccia messaggi in modo che audio in/out sia un layer aggiuntivo (vedi 4.1).

### 0.1 Design di riferimento **[v1.1]**
Il file `design/Deutsch-Tutor_dc.html` è il mockup approvato. È la fonte di verità per layout, gerarchia visiva e copy delle schermate; il presente piano è la fonte di verità per il comportamento. Dove i due divergono, vale il piano (le divergenze note sono elencate qui sotto e nei task di Fase 4).

**Token da estrarre in `tailwind.config`** (non re-inventare colori):
- Sfondo pagina `#EDE6D6`, superficie app `#F6F1E7`, card `#FFFFFF`, bordi `#E7DFD0` / `#D8CFBD`.
- Testo primario `#22281F`, secondario `#6E6559`, muted `#8A8072` / `#A79E8E`.
- Scuro/ink `#2A3324`; accento configurabile, default `#5F8B7A` (alternative: `#C1622D`, `#8A6A2E`, `#4A5A7A`).
- Badge stato vocabolo: `new` `#EFE6D8`/`#8A6A2E`, `seen` `#E9EFE3`/`#55694A`, `used` `#E3EEEA`/`#2E6B58`, `consolidated` `#2A3324`/`#F6F1E7`.
- Tag origine parola in harvest: `requested` "Chiesta" `#EFE6D8`/`#8A6A2E`, `error` "Errore" `#F3E3DE`/`#A0452E`, `agent_used` "Usata dall'agente" `#E3EEEA`/`#2E6B58`.
- Font: **Newsreader** (titoli, serif) e **Work Sans** (UI), via `next/font/google`.
- Raggi: card 16–20px, bottoni 12px, pill 10–20px. Container max-width 480px centrato, bottom nav fissa a 4 voci (Home, Lezione, Vocabolario, Progresso).

**Divergenze design → piano, già decise:**
1. Il mockup è a **colonna singola** (mobile). Il layout a due colonne del v1 (task 4.1) è abbandonato: correzioni e materiale di supporto vanno in un **bottom sheet**, non in una colonna laterale.
2. I 5 indicatori di fase nel mockup sono cliccabili: **non devono esserlo**. La fase avanza solo con il bottone "Avanti" (transizione lato backend). "Indietro" è consentito solo warmup→home (abbandona lezione, con conferma) e prep↔roleplay (rileggere le espressioni; non riapre il warmup).
3. Nel roleplay il mockup mostra il tag "Recast" sui messaggi dell'agente: **non mostrarlo** durante il dialogo (il metodo vieta di segnalare correzioni in roleplay). Mostrare solo il tag "Parola richiesta con [ ]" sui messaggi dell'utente. I recast diventano visibili nella Ernte.
4. Il mockup aggiunge una tab **"Ripassa" con flashcard** (DE davanti, IT dietro, "La so / Non la so"). Si tiene come ripasso rapido tra le lezioni, ma **invertito**: davanti IT + situazione/esempio con la parola oscurata, dietro DE + esempio completo (recupero attivo IT→DE, coerente con il metodo). Il self-grading alimenta lo stesso algoritmo SRS del warmup. Il bottone "Ricomincia" del mockup **non esiste**: la coda la decide l'SRS.
5. La Ernte del mockup ha solo la lista parole: va aggiunto **sopra** un blocco "Correzioni" con al massimo 3 errori (frase tua → frase corretta → regola in una riga), fornito dal Korrektor.
6. Valori hardcoded nel mockup (data, "7 lezioni completate", 5 scenari nel percorso, streak 5) vengono tutti dal backend.

**Non presente nel design, da progettare in coerenza con i token** (task 4.4): lezione di tipo `review` (test 15 parole "completa la frase"), stati di caricamento durante le chiamate LLM, stati di errore/fallback, ripresa di una lezione `in_progress`, chiusura del roleplay da parte dell'agente.

---

## Fase 1 — Fondamenta

### 1.1 Scaffolding repository
- Monorepo: `/web` (Next.js), `/api` (FastAPI), `/infra` (docker-compose, .env.example), `/docs`.
- `docker-compose.yml` con servizi `web`, `api`, `db` (Postgres 16). Healthcheck su `api`.
- README con comandi: up, migrate, seed, test.
- **Accettazione**: `docker compose up` → frontend su :3000 risponde, `GET /api/health` → 200, DB raggiungibile.

### 1.2 Schema DB (Alembic)
Tabelle minime:
- `scenarios` — id, slug, title_de, title_it, week_number, description, role_label (es. "Verkäuferin am Supermarkt"), key_phrases (JSONB: lista di {de, it, example}), swiss_variants (JSONB: lista di {standard, swiss, it} **[v1.1]**), imprevisti (JSONB: lista di stringhe), goals (JSONB: lista di stringhe).
- `vocab_items` — id, de, it, gender (nullable), plural (nullable), separable (bool), example_de, scenario_id (nullable), source (enum: `curated`, `requested`, `error`, `agent_used`), created_at.
- `vocab_progress` — vocab_item_id (PK), state (enum: `new`, `seen`, `used`, `consolidated`), correct_uses (int), last_reviewed_at, next_review_at, interval_days (int), lapses (int).
- `review_events` **[v1.1]** — id, vocab_item_id, source (enum: `warmup`, `flashcard`, `roleplay`, `test`), result (enum: `correct`, `wrong`), lesson_id (nullable), created_at. Serve a calcolare i "3 usi corretti in 3 lezioni diverse" e le statistiche.
- `lessons` — id, scenario_id, lesson_type (enum: `base`, `variant`, `incident`, `review`), started_at, ended_at, status (enum: `in_progress`, `completed`, `abandoned`), summary (JSONB).
- `messages` — id, lesson_id, phase (enum: `warmup`, `prep`, `roleplay`, `harvest`, `swiss`), role (enum: `user`, `agent`, `system`), content (text), corrections (JSONB, nullable), requested_words (JSONB, nullable), created_at.
- `user_sentences` — id, vocab_item_id, lesson_id, sentence, is_correct (bool), feedback (text), created_at.
- **Accettazione**: migrazione applicata da zero; ERD in `/docs/schema.md`.

### 1.3 Seed contenuti
- Seed dei 12 scenari con titolo e descrizione; contenuti completi (key_phrases, swiss_variants, imprevisti, ~40 vocab curated) **solo per lo scenario 1 "Im Supermarkt"**. Gli altri li generiamo dopo con il Planer (task 3.4).
- Includere nel seed i vocaboli già raccolti nella lezione di test: `der Einkaufswagen, die Kasse, das Regal, abwiegen (separabile), im Angebot, die Quittung, ausverkauft, Hätten Sie…?, sechs Eier, brauchen, das Frühstück, der Zopf, die Mischung, einpacken (separabile), sammeln, das Bargeld / bar, zurück, gleich da drüben, das Bier, die Äpfel`.
- **Accettazione**: `make seed` idempotente; scenario 1 completo in DB.

---

## Fase 2 — Motore didattico (backend, senza LLM)

### 2.1 Spaced repetition
- Algoritmo semplice e deterministico (non SM-2 completo): intervalli `1 → 3 → 7 → 21` giorni. Risposta corretta → intervallo successivo; errore → torna a 1 giorno, `lapses += 1`. Dopo 3 usi corretti in 3 lezioni diverse → `state = consolidated`, esce dal ripasso salvo ripescaggio casuale (10% delle parole di ripasso).
- Funzione `pick_warmup_words(n_review=5, n_new=3, scenario_id)` → dà priorità a: `next_review_at` scaduto, poi `lapses` alto, poi `requested`/`error` recenti.
- Funzione `pick_flashcard_queue(limit=20)` **[v1.1]** → parole con `next_review_at <= now`, stesso ordine di priorità; usata dalla tab Ripassa e dal contatore "Parole in scadenza oggi" in Home. Il self-grading della flashcard applica la stessa regola (corretto → intervallo successivo, errore → reset), ma **non** conta per la consolidazione (`correct_uses` avanza solo con uso in frase: warmup, roleplay, test).
- **Accettazione**: test unitari con date fittizie che coprono i quattro intervalli, il reset su errore e la consolidazione.

### 2.2 Macchina a stati della lezione
- Stati: `warmup → prep → roleplay → harvest → swiss → completed`. Transizioni esplicite via API; nessuno stato saltabile tranne `swiss` (opzionale se il tempo è finito). Transizione all'indietro consentita solo `roleplay → prep` (e ritorno) **[v1.1]**. Una sola lezione `in_progress` alla volta; `POST /lessons` con una lezione aperta restituisce quella.
- Timer indicativo per fase salvato lato client; il backend registra solo `started_at`/`ended_at`.
- Regola di avanzamento del piano: se in un `roleplay` i `requested_words` sono > 6, la lezione successiva resta sullo stesso scenario (`lesson_type` = `variant`) invece di avanzare.
- **Accettazione**: test sulle transizioni e sulla regola > 6.

### 2.3 API REST
- `POST /lessons` — crea lezione (sceglie scenario e tipo secondo il piano).
- `GET /lessons/{id}` — stato, fase corrente, messaggi.
- `POST /lessons/{id}/warmup/answer` — frase utente per una parola → feedback (LLM, task 3.2) + aggiornamento progress.
- `POST /lessons/{id}/advance` — passa alla fase successiva.
- `POST /lessons/{id}/roleplay/message` — messaggio utente → risposta agente (LLM, task 3.3) con estrazione `[ ]`.
- `POST /lessons/{id}/harvest/confirm` — lista vocab_item_id da tenere.
- `GET /vocab` — lista con stato e prossimo ripasso.
- `GET /progress` — parole per stato, streak lezioni, scenario corrente, lezioni completate, percorso 12 settimane con stato per scenario.
- `GET /lessons/current` **[v1.1]** — lezione `in_progress` se esiste (per la ripresa e per la tab "Lezione" della nav).
- `GET /home` **[v1.1]** — payload aggregato per la Home: prossima lezione (scenario, tipo), `due_today` (conteggio + prime 3 parole), streak, settimana corrente.
- `GET /vocab/review-queue` e `POST /vocab/{id}/review` **[v1.1]** — coda flashcard e self-grading (`result: correct|wrong`).
- `POST /lessons/{id}/abandon` **[v1.1]** — abbandono esplicito dalla lezione.
- **Accettazione**: OpenAPI generato; test d'integrazione del flusso completo con LLM mockato.

---

## Fase 3 — Agenti LLM

### 3.1 Layer LLM e routing
- Un'unica interfaccia `complete(task: Literal[...], messages, schema: Optional[BaseModel])` con routing per compito:
  - `roleplay` → **locale** (bassa latenza, molte chiamate, contenuto semplice).
  - `warmup_feedback`, `corrector`, `harvest` → **cloud** (serve precisione grammaticale e output strutturato affidabile).
  - `planner`, `content_gen` → **cloud**.
- Fallback automatico locale→cloud su errore/timeout; log di ogni chiamata (task, modello, token, latenza) in tabella `llm_calls`.
- Tutti gli output strutturati validati con Pydantic; retry una volta con messaggio d'errore se il JSON non valida.
- Prompt in file `.md` versionati in `/api/prompts/`, non hardcoded.
- **Accettazione**: switch di provider via env; test con provider fake.

### 3.2 Agente Warm-up
- Input: parola, frase dell'utente, livello. Output JSON: `{is_correct, corrected_sentence, feedback_it (max 120 caratteri), error_type (enum: none|separable_verb|case|gender|plural|word_order|vocab|other)}`.
- Regola: un solo punto per frase, quello più utile. Tono asciutto.
- **Accettazione**: 10 casi di test presi dalla lezione pilota (es. "Ich abwiege die banane" → separable_verb, "Die bier ist ausverkauft" → gender).

### 3.3 Agente Gesprächspartner + Korrektor
- **Gesprächspartner** (locale): system prompt con scenario, ruolo, key_phrases, imprevisto da inserire, livello A2/B1. Regole ferme: risposte di 1–3 frasi, Alltagsdeutsch parlato, mai spiegazioni grammaticali, mai uscire dal personaggio, recast degli errori nella propria risposta, se l'utente scrive `[parola]` fornire il termine tedesco e usarlo subito. Chiude il dialogo con un saluto quando gli obiettivi dello scenario (lista `goals` nel prompt) sono raggiunti o dopo N turni.
- **Korrektor** (cloud, asincrono, non blocca il dialogo): riceve ogni messaggio utente, ritorna `{comprehensible: bool, errors: [{span, fix, type, rule_it (max 80 caratteri)}], new_words_from_agent: [...]}`. Le correzioni **non** vengono mostrate durante il roleplay (nessun tag "Recast" in UI); si accumulano per la fase harvest, che ne mostra al massimo 3 nel blocco "Correzioni" **[v1.1]**.
- Parser deterministico per `[…]` prima della chiamata LLM; le parole richieste sono salvate come `vocab_items(source=requested)`.
- **Accettazione**: dialogo di 8 turni sullo scenario 1 senza rotture di personaggio; test parser `[ ]`.

### 3.4 Agente Planer / generatore contenuti
- A fine lezione: aggiorna `vocab_progress`, produce `lessons.summary` (parole nuove, errori ricorrenti, raccomandazione per la prossima lezione).
- Generazione contenuti scenario (per gli scenari 2–12): dato titolo e descrizione → key_phrases, ~40 vocab, imprevisti, varianti svizzere, in JSON validato. Revisione umana prima del seed (comando CLI che stampa il JSON e chiede conferma).
- **Accettazione**: generazione scenario 2 "Zuhause und Nachbarn" completata e revisionata.

---

## Fase 4 — Frontend **[v1.1: riscritta sul design]**

Implementare le schermate del mockup `design/Deutsch-Tutor_dc.html` con Next.js App Router + Tailwind, usando i token di 0.1. Prima di scrivere componenti: aprire il mockup nel browser e riprodurre fedelmente spaziature, tipografia e copy in italiano. Le divergenze elencate in 0.1 prevalgono sul mockup.

### 4.1 Shell e componenti base
- Container 480px centrato, bottom nav fissa (Home, Lezione, Vocabolario, Progresso). La voce "Lezione" apre la lezione `in_progress` se esiste, altrimenti ne crea una.
- Componenti condivisi: `Card`, `Badge` (stato vocabolo), `SourceTag` (origine parola), `PhaseIndicator` (5 barre + label, **non cliccabile**), `BottomSheet`, `PrimaryButton`, `Pill`.
- `MessageInput` con astrazione `InputSource` (`text` ora, `voice` dopo): il roleplay riceve solo stringhe. `MessageBubble` con slot opzionale per audio. Placeholder del roleplay: "Scrivi in tedesco. Usa [parola] se ti manca...".
- Stati globali: `LoadingDots` per attesa LLM (bolla agente animata nel roleplay, spinner inline nel warmup), `ErrorBanner` con "Riprova" per errori API/LLM.
- **Accettazione**: Storybook o pagina `/dev/components` con tutti i componenti nei loro stati.

### 4.2 Home e Progresso
- **Home** (da `GET /home`): intestazione con data e "Ciao, {nome}"; pill streak; card scura "Prossima lezione · Tipo {tipo}" con titolo DE/IT, pill "30 minuti" e "5 fasi", bottone "Inizia la lezione" (o "Riprendi la lezione" se `in_progress`); card "Parole in scadenza oggi" con conteggio, prime 3 parole e tap → tab Ripassa; card "Il tuo percorso" con "Settimana N di 12" e barra.
- **Progresso** (da `GET /progress`): 4 contatori (parole totali, consolidate, lezioni completate, serie), barra segmentata "Parole per stato" con legenda, lista "Percorso · 12 settimane" con tutti e 12 gli scenari (corrente evidenziato, completati in ink, futuri attenuati).
- **Accettazione**: nessun valore hardcoded; con DB solo seed la Home mostra scenario 1, 0 streak, parole in scadenza reali.

### 4.3 Lezione (5 fasi)
- Header: freccia indietro (→ conferma "Abbandonare la lezione?" solo in warmup; altrove disabilitata), titolo scenario, sottotitolo "Lezione {tipo} · Scenario N". `PhaseIndicator` sotto.
- **Aufwärmen**: lista di 8 card, ognuna con parola DE, traduzione IT, badge "Ripasso"/"Nuova", input "Scrivi una frase in tedesco...". Invio con Enter/bottone → `POST .../warmup/answer`, la card si blocca e mostra il feedback (una riga, colore neutro se corretta, ambra se corretta con nota, rosso attenuato se errata). "Avanti" abilitato solo con 8 risposte inviate.
- **Vorbereitung**: lista key_phrases (DE grande, IT sotto, esempio in corsivo tra virgolette basse „…"). Solo lettura. Durante il roleplay la stessa lista è raggiungibile da un'icona nell'header che apre il `BottomSheet`.
- **Rollenspiel**: sottotitolo "Gioco di ruolo · {role_label}"; bolle (agente bianche a sinistra, utente colore accento a destra); tag "Parola richiesta con [ ]" **solo** sui messaggi utente che lo contengono; nessun tag sui messaggi agente. Bolla di attesa animata mentre l'agente risponde. Quando l'agente chiude il dialogo (flag `dialogue_closed` nella risposta), l'input si disabilita e "Avanti" diventa primario.
- **Wortschatz-Ernte**: blocco "Correzioni" (0–3 card: frase tua barrata leggera → frase corretta → regola in una riga); sotto, lista parole con checkbox scura (tutte selezionate di default), DE — IT e `SourceTag`. "Avanti" → `POST .../harvest/confirm` con le selezionate.
- **Schweizerdeutsch-Ecke**: 3 card con Hochdeutsch (muted), variante svizzera (grande, serif) e IT. Bottone finale "Termina lezione" → `completed` → Home con toast "Lezione completata · +N parole".
- **Accettazione**: flusso completo di una lezione da browser mobile (viewport 390px) e desktop; nessuna fase saltabile via UI; ripresa corretta di una lezione interrotta ricaricando la pagina.

### 4.4 Vocabolario (tab Ripassa + Elenco)
- **Ripassa**: da `GET /vocab/review-queue`. Header "Carta X di Y" + badge stato + barra progresso. Carta con flip 3D: **fronte** IT + frase d'esempio con la parola sostituita da "____" e "Tocca per girare"; **retro** DE (serif grande) + esempio completo. Dopo il flip: bottoni "Non la so" / "La so" → `POST /vocab/{id}/review`. A coda vuota: card "Ripasso completato" con "Hai rivisto tutte le N parole di oggi." e link alla Home (nessun "Ricomincia").
- **Elenco**: campo "Cerca una parola...", pill filtro (Tutte, Nuovo, Visto, Usato, Consolidato), lista con DE/IT e badge stato. Tap su una riga → `BottomSheet` con genere/plurale/separabile, esempio, frasi dell'utente (`user_sentences`) e prossimo ripasso.
- **Accettazione**: ripasso di 6 parole aggiorna `next_review_at` correttamente; filtro e ricerca funzionanti.

### 4.5 Schermate non coperte dal design
Da disegnare con gli stessi token, mantenendo la struttura a card:
- **Lezione `review`** (4ª della settimana): al posto di Vorbereitung+Rollenspiel, un test di 15 frasi "completa con la parola giusta" (input libero, feedback immediato, punteggio finale). Le fasi warmup, Ernte (con gli errori del test) e Schweiz restano.
- **Stati vuoti**: nessuna parola in scadenza, vocabolario vuoto.
- **Accettazione**: mock statici approvati prima dell'implementazione (uno screenshot per schermata nel report di fase).

---

## Fase 5 — Rifinitura

### 5.1 Test finale end-to-end
- Una lezione completa reale sullo scenario 1, poi confronto con la lezione pilota fatta in chat: stesse fasi, stessa qualità di recast e di feedback. Annotare le differenze in `/docs/pilot-comparison.md`.

### 5.2 Backup e osservabilità
- Dump giornaliero del DB (cron nel container o script host).
- Pagina `/admin/llm` con costi/latency per task (da `llm_calls`).

---

## Ordine consigliato e checkpoint di revisione

1. Fase 1 completa → **revisione** (schema DB e seed).
2. Fase 2 completa → **revisione** (algoritmo SRS e API).
3. Task 3.1 + 3.3 → **revisione** (qualità del roleplay è il cuore del prodotto).
4. Task 3.2 + 3.4 → revisione.
5. Task 4.1–4.3 → **revisione** (uso reale dall'iPhone).
6. Task 4.4–4.5 → revisione.
7. Fase 5.

## Decisioni aperte (da non decidere autonomamente)
- Modello locale specifico e parametri (temperatura, max token) per il roleplay.
- Se il Korrektor debba eventualmente interrompere il dialogo quando `comprehensible = false`.
- Numero massimo di turni del roleplay prima della chiusura forzata (proposta: 12).
- **[v1.1]** Se la Home debba mostrare la data (il mockup la ha; è decorativa) — proposta: sì, da `Intl.DateTimeFormat('it-CH')`.
- **[v1.1]** Se le flashcard debbano richiedere di **digitare** la parola invece del self-grading — proposta: v1 self-grading, v1.1 digitazione opzionale.
