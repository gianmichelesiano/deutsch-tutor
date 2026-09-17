# Fase "Karten": flashcard di fine lezione

Data: 2026-09-17 · Stato: approvata

## Obiettivo

La lezione finisce oggi sulla fase Schweiz, con il pulsante "Termina lezione": si esce
senza rivedere nulla. Le flashcard esistono già nella tab Vocabolario (Ripassa), ma non
sono collegate al momento in cui il ripasso serve di più, cioè subito dopo aver usato le
parole in contesto. Si aggiunge una tappa finale **Karten** con le carte di ripasso.

Decisioni prese con l'utente:
- Fase dedicata (non un blocco dentro Schweiz): ha un segmento proprio nella barra,
  sopravvive al reload a metà ripasso (la ripresa è per `current_phase`).
- Mazzo **ibrido**, in ordine di priorità: parole usate in questa lezione → parole dovute
  dello stesso scenario → altre parole dovute globali, fino a 12 carte.
- Nessun endpoint nuovo: le carte si votano con `POST /vocab/{id}/review` esistente.

## Macchina a stati

- `PHASES = ("intro", "warmup", "prep", "roleplay", "harvest", "swiss", "karten")`.
- `REVIEW_PHASES = ("warmup", "test", "harvest", "swiss", "karten")`.
- `advance_phase`: da `karten` → `completed`; `harvest` + `skip_swiss` → `karten`
  (si salta la Svizzera, non le carte). `back_phase` invariato.
- Migrazione Alembic `0006`: `ALTER TYPE lesson_phase_enum ADD VALUE IF NOT EXISTS 'karten'`.
  Le lezioni `in_progress` esistenti restano nella loro fase.

## Selezione delle carte (`services.pick_karten_words`)

1. parole con `review_events` di questa lezione (source ≠ flashcard), in ordine di uso,
   anche se non ancora dovute — esclusi i placeholder (`de == it`);
2. + `pick_flashcard_queue(..., scenario_id=lesson.scenario_id)` (nuovo parametro opzionale,
   default `None` = tutti gli scenari, come per la tab Vocabolario);
3. + `pick_flashcard_queue(...)` globale, per riempire fino a `KARTEN_LIMIT = 12`.

`LessonDetail.karten_words` (stesso schema di `ReviewQueueItem`) è popolato solo quando
`current_phase == "karten"`, come già accade per `warmup_words` / `test_words` / `harvest_words`.

## Effetto sul SRS

Il voto in fase Karten passa da `POST /vocab/{id}/review` con `source=flashcard` e
`counts_for_consolidation=False`: aggiorna intervallo (1→3→7→21) e lapse, ma non aumenta
`correct_uses` e non porta a `used`/`consolidated`. Identico alla tab Vocabolario: la
consolidazione si guadagna solo usando la parola in frase (warmup/roleplay/test).

## Frontend

- `web/components/Flashcard.tsx`: la carta (fronte italiano + esempio bucato, retro tedesco)
  estratta dalla tab Vocabolario e condivisa, così i due posti non divergono.
- `web/lib/vocab.ts`: `escapeRegex` / `blankExample`, prima duplicati in `Vocab.tsx` e `TestPhase.tsx`.
- `web/components/screens/lesson/KartenPhase.tsx`: contatore "Carta N di M", badge stato,
  barra di avanzamento, stati vuoti ("Nessuna carta da ripassare", "Ripasso completato").
- `Lesson.tsx`: `isLastPhase = phase === "karten"` → "Termina lezione" compare sulla nuova fase.
- La carta mostra l'esempio solo se `example_de` non è vuoto (le parole raccolte dal roleplay
  spesso non hanno esempio: prima si vedevano virgolette vuote).
