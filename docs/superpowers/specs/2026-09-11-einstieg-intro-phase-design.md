# Fase "Einstieg": introduzione teorica alla lezione

Data: 2026-09-11 · Stato: approvata

## Obiettivo

Oggi la lezione parte dal warmup: l'utente scrive frasi su 8 parole senza conoscere la situazione. La Vorbereitung arriva dopo ed è una lista di key_phrases senza spiegazione. Si aggiunge una prima fase **Einstieg** con un testo breve in tedesco che racconta la situazione, un mini-dialogo modello e note pragmatiche in italiano. Il contenuto è statico per scenario, generato una volta con il generatore contenuti e revisionabile nei JSON del seed.

Decisioni prese con l'utente:
- Nuova prima fase, prima del warmup (non dentro la Vorbereitung).
- Contenuto statico per scenario (nessuna generazione live).
- Formato: racconto della situazione + mini-dialogo + note pragmatiche in italiano. Nessuna mini-grammatica.
- Compare in tutte le lezioni non-review; dopo la prima lezione completata dello scenario è mostrata compressa con "Rileggi".

## Dati

Nuova colonna `scenarios.intro` (JSONB, default `null`):

```json
{
  "situation": [{"de": "Ich bin im Coop und suche Eier.", "it": "Sono alla Coop e cerco le uova."}],
  "dialog": [{"speaker": "Verkäuferin", "de": "Grüezi, kann ich Ihnen helfen?", "it": "Buongiorno, posso aiutarla?"}],
  "notes_it": ["Con il personale si usa sempre il Sie.", "Il Säckli si paga: 5 Rappen."]
}
```

Vincoli:
- `situation`: 5–8 frasi in prima persona, Hochdeutsch livello A2/B1, ognuna con traduzione italiana.
- `dialog`: 4–6 battute alternate tra l'utente ("Ich") e il ruolo dello scenario (`role_label`), ognuna con glossa italiana.
- `notes_it`: 2–3 note in italiano (registro Sie/du, abitudini svizzere, cosa aspettarsi dall'interlocutore).
- Tutti i campi `de` devono passare il validatore anti-dialetto `content_gen.dialect_hits` (esteso ai campi dell'intro).

## Generazione contenuti

- Nuovo prompt `api/prompts/content_gen_intro.md` (stessi criteri di lingua di `content_gen_meta.md`: Hochdeutsch, niente dialetto, contesto Zürich).
- Nuovo schema `agents.ContentGenIntro` e builder `agents.build_content_gen_intro_messages(scenario)`.
- `content_gen.generate_intro(client, scenario)` con retry e feedback come `generate_meta`.
- `content_gen.generate` include `intro` nell'output; CLI `--scenario N` invariato.
- Script una tantum: genera `intro` per gli scenari 1–12 e la scrive nei JSON `api/app/seed_content/scenario-NN.json`. Gli scenari 1 e 2, oggi solo in `seed_data.py`, ottengono un JSON con solo `slug`, `week_number`, `intro` (nessun vocab: il seed li tratta come gli altri, vocab opzionale).
- Seed: `GENERATED_FIELDS` include `intro`; `dialect_hits` non è chiamato nel seed.

## Macchina a stati

- `PHASES = ("intro", "warmup", "prep", "roleplay", "harvest", "swiss")`.
- `REVIEW_PHASES` invariato (`warmup, test, harvest, swiss`): il ripasso non ha intro.
- `back_phase`: consentito `roleplay → prep` (esistente) e `warmup → intro` (nuovo).
- `create_lesson`: `current_phase = intro` per tipi non-review, `warmup` per review.
- Migrazione Alembic 0005: `ALTER TYPE lesson_phase_enum ADD VALUE IF NOT EXISTS 'intro'` + `ADD COLUMN scenarios.intro JSONB NULL`. Le lezioni `in_progress` esistenti restano nella loro fase.

## API

`LessonDetail` guadagna:
- `intro: dict | None` — il JSON dello scenario.
- `intro_collapsed: bool` — vero se esiste una lezione `completed` per lo stesso scenario.

Nessun endpoint nuovo: `advance` e `back` bastano. `back` da `warmup` porta a `intro`.

## Frontend

- `Lesson.tsx` viene spezzato in `web/components/screens/lesson/` con un file per fase (`IntroPhase`, `WarmupPhase`, `TestPhase`, `PrepPhase`, `RoleplayPhase`, `HarvestPhase`, `SwissPhase`) più `Lesson.tsx` orchestratore. Nessun cambio di comportamento nel refactor.
- `IntroPhase`: titolo "Einstieg" · sottotitolo "La situazione · leggi prima di iniziare". Tre blocchi: racconto (frase DE, sotto IT in muted), dialogo (bolle con speaker; le battute "Ich" allineate a destra con colore accento), note (lista puntata). Se `intro_collapsed`: card con le prime due frasi DE e bottone "Rileggi" che espande.
- `PHASES`/`PHASE_LABELS` in `web/lib/api.ts` includono `intro: "Einstieg"`. Indicatore fasi: 6 voci, testo più piccolo; scroll orizzontale se non stanno in 390 px.
- Bottone "Indietro" visibile anche in `warmup` (porta a `intro`); la freccia "abbandona" resta in `intro` e `warmup`.
- Overlay dev per il web in `docker-compose.override.yml`: mount `./web` e `next dev`, così le modifiche si vedono senza rebuild.

## Test

- `test_lesson_state`: sequenza con `intro`, `back_phase("warmup") == "intro"`, review senza intro.
- `test_seed`: ogni JSON 1–12 ha `intro` valido (conteggi e campi non vuoti).
- `test_content_gen`: `dialect_hits` copre `situation[].de` e `dialog[].de`.
- `test_api_integration`: lezione nuova parte in `intro`; `intro_collapsed` falso alla prima lezione dello scenario, vero alla seconda; `back` da `warmup` → `intro`; review parte in `warmup`.
- Frontend: `tsc --noEmit`, screenshot mobile della fase Einstieg (completa e compressa).

## Fuori scope

- Rifare lo scenario 12 "Wiederholung" come vero ripasso.
- Messaggi d'errore dettagliati nel frontend.
