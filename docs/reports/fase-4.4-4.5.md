# Report Fase 4.4–4.5 — Vocabolario + schermate fuori design

Data: 2026-09-09 · Autore: agente implementatore · Stato: **stop per revisione** (mock statici 4.5 non implementati)

---

## 0. Chiusura dubbi aperti di Fase 4

| # | Domanda Fase 4 | Esito |
|---|---|---|
| 1 | Seed scenario 2? | ✅ Seedato (`seed_data.py`, 40 vocab quotidiani, `role_label: Nachbarin`). |
| 2 | BottomSheet espressioni durante il roleplay? | ✅ Implementato (icona libro in header roleplay → `BottomSheet` con key_phrases, il dialogo non si perde). |
| 3 | Nome utente hardcoded? | ✅ Risolto: `user_name` è un setting backend (`USER_NAME`, default `Gianmichele`) esposto in `GET /api/home`; il frontend usa `data.user_name`, nessun valore hardcoded. |

## 1. Scenari 3–12 (generazione contenuti)

- Generati e validi: **3, 4, 6, 7, 8, 9, 11** → `docs/reports/scenario-N.json` (bozze da rivedere, **non seedate**).
- **5, 10, 12** falliti (JSON troncato dal modello locale). Come mitigazione ho **spezzato** `content_gen` in più chiamate piccole (meta → 1 chiamata; vocab → 2 blocchi da 20) invece di un unico JSON gigante; i test restano verdi (54 passed). La rigenerazione dei 3 mancanti è **rimandata** su tua indicazione (segnata come completata per ora).

## 2. Task 4.4 — Vocabolario

- **Ripassa**: coda da `GET /api/vocab/review-queue`, carta flip 3D (fronte IT + frase con `____`, retro DE), self-grading `POST /api/vocab/{id}/review`, stato vuoto "Ripasso completato". (Già presente da 4.1–4.3.)
- **Elenco**: ricerca + pill filtro (Tutte/Nuovo/Visto/Usato/Consolidato) + lista con badge. Nuovo: tap su riga → `BottomSheet` dettaglio con genere/plurale/separabile, esempio, prossimo ripasso e frasi dell'utente.
- **Backend**: nuovo `GET /api/vocab/{id}` (vocab + progress + `user_sentences`).

## 3. Task 4.5 — Schermate non coperte dal design (SOLO mock statici)

Mock statici disegnati con gli stessi token (Newsreader/Work Sans, palette da `tailwind.config.ts`), **NON implementati** (stop prima dell'implementazione, come richiesto). Screenshot 390×844 in `docs/reports/screenshots/`:

| File | Schermata |
|---|---|
| `07-review-lesson.png` | Lezione `review` — test "Completa la frase" (15 frasi, feedback immediato, punteggio) |
| `08-home-empty.png` | Stato vuoto: nessuna parola in scadenza (Home) |
| `09-vocab-empty.png` | Stato vuoto: vocabolario vuoto (Elenco) |

### Proposta progettuale (da approvare prima di implementare)

1. **Lezione `review`** (4ª della settimana): fasi = Aufwärmen → **Test** → Ernte → Schweiz (4 fasi, non 5: il test sostituisce Vorbereitung+Rollenspiel). Test di 15 frasi "completa la parola giusta": input libero, feedback immediato (corretta/errore), punteggio "N corrette · M errori" in alto. Gli errori del test alimentano la Ernte (con le parole sbagliate come sorgenti), Schweiz invariata.
2. **Stato vuoto Home**: quando `due_today = 0`, card "Parole in scadenza" mostra "Nessuna parola in scadenza" + icona spunta, senza lista di chip.
3. **Stato vuoto Vocabolario**: quando `GET /api/vocab` è vuoto, card dashed "Nessuna parola ancora" con invito a completare la prima lezione.

## 4. Accettazione

| Criterio | Esito |
|---|---|
| 4.4 ripasso aggiorna `next_review_at`; filtro/ricerca funzionanti | ✅ (già verificato in 4.1–4.3) |
| 4.4 `BottomSheet` dettaglio con `user_sentences` | ✅ `Vocab.tsx` + `GET /api/vocab/{id}` |
| 4.5 mock statici approvati prima dell'implementazione | ⏳ **in attesa di approvazione** (3 screenshot sopra) |
| Suite backend | ✅ 54 passed |

## 5. Note / da confermare

1. Approvi i 3 mock statici? Se sì, implemento la lezione `review` e i due stati vuoti (poi revisione finale 4.4–4.5).
2. Scenari 5/10/12 da rigenerare con la nuova generazione "a blocchi" quando vuoi (serve il modello locale `ds4-server` attivo).
3. Gli scenari 3–12 generati restano **bozze non seedate**: li rivedi uno per uno e poi li seedo.

---

*Stop: attendo approvazione dei mock statici 4.5 prima di implementarli.*
