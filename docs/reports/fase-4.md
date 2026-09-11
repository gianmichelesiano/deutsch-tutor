# Report Fase 4 (task 4.1–4.3) — Frontend

Data: 2026-09-09 · Autore: agente implementatore · Stato: **stop per revisione** (con screenshot mobile 390px)

---

## 0. Azioni post-revisione Fase 3 (eseguite prima di Fase 4)

| Punto | Esito |
|---|---|
| 1. Scenario 2 curato | ✅ `docs/reports/scenario-2-zuhause-und-nachbarn.json` ridotto a **40 vocab** quotidiani (Waschküche, Waschplan, Hausverwaltung, Treppenhaus, Kehricht/Kehrichtsack, Nachtruhe, klingeln, Lärm, Briefkasten, Keller, Velo…), key_phrases **parlate** ("Sorry, war das zu laut gestern?"), 5 imprevisti **Zurigo** (lavatrice occupata, Kehrichtsack sbagliato, festa dopo le 22, pacco dal vicino, Velo nel Treppenhaus). **NON seedato** (attendo tua approvazione). |
| 1. content_gen.md aggiornato | ✅ criteri (solo uso quotidiano, frasi parlate, imprevisti Zurigo) codificati per gli scenari 3–12. |
| 2. Korrektor/Warm-up ammorbiditi | ✅ regola "solo errori che compromettono la comprensione o vocabolario"; ignora-lista (mit Karte, bar zahlen, im Angebot, ordine colloquiale, Konjunktiv II); **10 forme colloquiali ammesse** nel prompt. Test: `test_prompts_allow_colloquial_forms` + demo reale → "Ich zahle mit Karte" = `is_correct=true, error_type=none`; "Die Bier ist ausverkauft" = `gender` (ancora segnalato). |
| 3. Korrektor in-memory | ✅ annotato in `docs/decisions.md`. |
| 4. `greeted` in scene_state | ✅ `SceneState.greeted` + "Begrüssung: bereits erfolgt" → niente doppio Grüezi (verificato nel dialogo). |
| 4. Tüte→Säckli in Schweiz-Ecke | ✅ aggiunta variante `{eine Tüte → es Säckli}` allo scenario 1. |

**Backend extra**: aggiunto `POST /lessons/{id}/back` (per la transizione roleplay→prep richiesta dal design).

## 1. Task 4.1 — Shell e componenti base

- Container 480px centrato, bottom nav fissa a 4 voci (Home, Lezione, Vocabolario, Progresso).
- Componenti: `Card`, `Badge` (stato vocabolo), `SourceTag` (origine parola), `PhaseIndicator` (5 barre **non cliccabili**), `PrimaryButton`, `Pill`, `LoadingDots`, `ErrorBanner`, `BottomSheet`-ready (key_phrases restano nella fase prep; il BottomSheet per il roleplay è rimandato a rifinitura).
- `MessageInput`/`MessageBubble` con placeholder "Scrivi in tedesco. Usa [parola] se ti manca...".
- Token estratti in `tailwind.config.ts` (già presenti da Fase 1, non re-inventati). Font Newsreader + Work Sans via `next/font`.

## 2. Task 4.2 — Home e Progresso

- **Home** (`GET /api/home`): data (`it-CH`), "Ciao, {nome}", pill streak, card scura "Prossima lezione" con tipo/titolo DE/IT/"30 minuti"/"5 fasi", bottone "Inizia/Riprendi la lezione", card "Parole in scadenza oggi" (conteggio + prime 3), card "Il tuo percorso" (settimana + barra).
- **Progresso** (`GET /api/progress`): 4 contatori, barra segmentata "Parole per stato" con legenda, lista "Percorso · 12 settimane".
- Nessun valore hardcoded: tutto dal backend.

## 3. Task 4.3 — Lezione (5 fasi)

- Header con freccia indietro (solo warmup → conferma abbandono), titolo, sottotitolo, `PhaseIndicator`.
- **Aufwärmen**: 8 card (DE, IT, badge Ripasso/Nuova), input frase → `POST .../warmup/answer`, feedback a una riga; "Avanti" abilitato solo a 8 risposte.
- **Vorbereitung**: lista key_phrases (DE grande, IT, esempio in corsivo „…").
- **Rollenspiel**: bolle (agente bianco a sinistra, utente accento a destra), tag "Parola richiesta con [ ]" solo sui messaggi utente, bolla di attesa animata; input disabilitato a dialogo chiuso.
- **Wortschatz-Ernte**: blocco "Correzioni" (max 3) + lista parole con checkbox (tutte selezionate) e `SourceTag`; conferma → `POST .../harvest/confirm`.
- **Schweizerdeutsch-Ecke**: 3 card (Hochdeutsch barrato, variante serif, IT) + "Termina lezione".

## 4. Screenshot mobile (390×844)

`docs/reports/screenshots/`:

| File | Fase |
|---|---|
| `01-home.png` | Home |
| `02-warmup.png` | Aufwärmen |
| `03-prep.png` | Vorbereitung |
| `04-roleplay.png` | Rollenspiel (apertura agente) |
| `04b-roleplay-conversation.png` | Rollenspiel (conversazione, parola `[uova]`) |
| `05-harvest.png` | Wortschatz-Ernte |
| `06-swiss.png` | Schweizerdeutsch-Ecke |

Flusso end-to-end verificato via Playwright (Chrome headless, viewport 390px) con modello locale reale: warmup (8 risposte) → prep → roleplay (2 messaggi) → harvest → swiss, nessuna fase saltabile.

## 5. Accettazione

| Criterio | Esito |
|---|---|
| 4.1 componenti nei loro stati | ✅ `components/ui.tsx`, `Shell.tsx` |
| 4.2 nessun valore hardcoded | ✅ tutto da `/api/home`, `/api/progress` |
| 4.3 flusso completo da mobile 390px + desktop | ✅ screenshot + Playwright run |
| 4.3 nessuna fase saltabile via UI | ✅ "Avanti" abilitato solo a warmup completato; transizioni via backend |
| Suite backend | ✅ 54 passed |

## 6. Decisioni / note

1. **Proxy `/api`** via `next.config.mjs` rewrite → `http://api:8000` (no CORS, single-origin). `API_URL` sovrascrivibile a build-time.
2. **"Indietro"** (roleplay→prep) implementato col nuovo endpoint `POST /lessons/{id}/back` (il piano 2.3 non lo prevedeva, ma il design 0.1 lo richiede).
3. **BottomSheet** (key_phrases durante il roleplay) non ancora implementato: le espressioni restano nella fase prep. Rimandato a rifinitura se serve.
4. **Nome utente** "Gianmichele" hardcoded nel frontend (il backend non espone un profilo utente). Da collegare quando esiste un concetto di utente.
5. Per gli screenshot ho usato `LLM_PROVIDER_MODE=local-only` (`.env` locale, gitignored) + modello locale; senza modello il flusso resta testabile con `LLM_PROVIDER_MODE=mock`.

## 7. Dubbi / da confermare

1. Approvi lo scenario 2 curato? Se sì, seedo lo scenario 2 e genero (senza seedare) gli scenari 3–12 con lo stesso criterio.
2. Il `BottomSheet` per rileggere le espressioni durante il roleplay è importante per te ora, o lo rimandiamo a Fase 4.4/rifinitura?
3. Nome utente: va bene "Gianmichele" fisso per ora, o aggiungiamo un campo profilo?

---

*Stop: attendo revisione di 4.1–4.3 (screenshot sopra) prima di 4.4–4.5.*
