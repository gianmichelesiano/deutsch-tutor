# Piano: fase Karten

Data: 2026-09-17

| # | Passo | File |
|---|---|---|
| 1 | `karten` nell'enum `LessonPhase` | `api/app/models.py` |
| 2 | Migrazione `0006` (`ALTER TYPE ... ADD VALUE 'karten'`) | `api/alembic/versions/0006_add_karten_phase.py` |
| 3 | `PHASES` / `REVIEW_PHASES` + `advance_phase` (karten → completed, skip_swiss → karten) | `api/app/lesson_state.py` |
| 4 | `ReviewQueueItem` prima di `LessonDetail` + campo `karten_words` | `api/app/schemas.py` |
| 5 | `scenario_id` opzionale in `pick_flashcard_queue`, `get_cards_by_ids`, `pick_karten_words`, uso in `build_lesson_detail` | `api/app/services.py` |
| 6 | Tipo `LessonDetail` + fasi/etichette (7 segmenti) | `web/lib/api.ts` |
| 7 | `Flashcard.tsx` condivisa + `lib/vocab.ts` | `web/components/Flashcard.tsx`, `web/lib/vocab.ts` |
| 8 | `KartenPhase.tsx` + rendering e CTA finale | `web/components/screens/lesson/KartenPhase.tsx`, `Lesson.tsx` |
| 9 | Vocabolario e TestPhase sulla carta/helper condivisi | `web/components/screens/Vocab.tsx`, `lesson/TestPhase.tsx` |
| 10 | Test: sequenza fasi, skip_swiss, ripasso, mazzo in fase karten | `api/tests/test_lesson_state.py`, `api/tests/test_api_integration.py` |
| 11 | Migrazione sul DB, `pytest`, `tsc --noEmit`, prova in browser reale | — |
