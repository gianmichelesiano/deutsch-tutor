# Report — Fase Karten (2026-09-17)

## Cosa è stato fatto

Settima fase `karten` a fine lezione (dopo Schweiz), con flashcard stile Anki delle parole
da ripassare; "Termina lezione" ora sta lì. Dettagli in
`docs/superpowers/specs/2026-09-17-karten-phase-design.md`.

## Verifiche eseguite

- **Migrazione**: `alembic upgrade head` sul DB reale → `0006 (head)`; `lesson_phase_enum`
  contiene `karten`.
- **Test**: `pytest` nel container api → **67 passed** (unit + integration su Postgres reale).
  Il test di flusso completo verifica che in fase `karten` il mazzo abbia ≤ 12 carte, che le
  prime siano le parole usate nella lezione (ordine di uso) e che non contenga placeholder.
- **Tipi**: `npx tsc --noEmit` nel container web → nessun errore.
- **API live**: lezione reale in fase `karten` → `karten_words` con 12 carte, primi 8 id = parole
  della lezione; `POST /api/vocab/{id}/review` → `state` invariato, `interval_days` 1, `next_review_at` +1g.
- **Browser reale** (Chromium headless via Playwright, viewport 400x880): barra a 7 fasi con
  "Karten" evidenziata, "Carta 1 di 12", carta che gira, pulsanti "La so"/"Non la so",
  "Termina lezione" sulla fase finale; nessuna richiesta 4xx/5xx, nessun errore JS.
  Screenshot in `docs/reports/screenshots/2026-09-17-karten-phase-*.png`
  (presi con la selezione **globale** del mazzo: il sottotitolo dice ancora "parole dovute oggi",
  poi cambiato in "questa lezione e parole dovute").

## Note e limiti

- Con 7 segmenti le etichette della barra si troncano su schermo stretto ("Aufwär…", "Vorberei…").
- Le parole raccolte dal roleplay spesso non hanno `example_de`: la carta le rende senza esempio
  (nessuna riga vuota).
