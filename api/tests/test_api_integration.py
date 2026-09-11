import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import engine
from app.deps import get_llm
from app.llm import LlmClient, MockLlmClient
from app.main import app
from app.seed import load_seed_content
from app.seed_data import VOCAB

pytestmark = pytest.mark.integration


@pytest.fixture
async def clean_db():
    """Riporta il DB allo stato di seed: vocab curati 'new', nessuna lezione.

    Distruttivo: consentito solo sul DB di test (vedi conftest.py).
    """
    assert str(engine.url.database).endswith("_test"), f"rifiuto TRUNCATE su {engine.url.database}"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE review_events, user_sentences, messages, lessons "
                "RESTART IDENTITY CASCADE"
            )
        )
        await conn.execute(text("DELETE FROM vocab_progress"))
        await conn.execute(text("DELETE FROM vocab_items WHERE source != 'curated'"))
        await conn.execute(
            text(
                "INSERT INTO vocab_progress "
                "(vocab_item_id, state, correct_uses, last_reviewed_at, next_review_at, interval_days, lapses) "
                "SELECT id, 'new', 0, NULL, NULL, 0, 0 FROM vocab_items"
            )
        )
    yield


@pytest.fixture
def mock_llm():
    app.dependency_overrides[get_llm] = lambda: MockLlmClient(close_after_turns=2)
    yield
    app.dependency_overrides.clear()


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_full_lesson_flow(clean_db, mock_llm):
    async with _client() as client:
        # 1. crea lezione
        r = await client.post("/api/lessons")
        assert r.status_code == 200
        lesson = r.json()
        lesson_id = lesson["id"]
        assert lesson["current_phase"] == "warmup"
        assert lesson["status"] == "in_progress"
        assert len(lesson["warmup_words"]) == 8

        # una sola lezione in_progress alla volta
        r2 = await client.post("/api/lessons")
        assert r2.json()["id"] == lesson_id

        # 2. warmup: 8 risposte (il mock le valuta corrette)
        for w in lesson["warmup_words"]:
            r = await client.post(
                f"/api/lessons/{lesson_id}/warmup/answer",
                json={"vocab_item_id": w["vocab_item_id"], "sentence": "Ich kaufe das."},
            )
            assert r.status_code == 200
            assert r.json()["is_correct"] is True

        # 3. advance → prep → roleplay
        r = await client.post(f"/api/lessons/{lesson_id}/advance", json={})
        assert r.json()["current_phase"] == "prep"
        r = await client.post(f"/api/lessons/{lesson_id}/advance", json={})
        assert r.json()["current_phase"] == "roleplay"
        assert len(r.json()["roleplay_messages"]) == 1  # apertura dell'agente

        # 4. roleplay: 2 turni (il mock chiude al 2°)
        r = await client.post(
            f"/api/lessons/{lesson_id}/roleplay/message", json={"content": "Ich suche [uova]."}
        )
        assert r.status_code == 200
        assert r.json()["requested_words"][0]["it"] == "uova"
        r = await client.post(
            f"/api/lessons/{lesson_id}/roleplay/message", json={"content": "Danke, das ist alles."}
        )
        assert r.json()["dialogue_closed"] is True

        # 5. advance → harvest
        r = await client.post(f"/api/lessons/{lesson_id}/advance", json={})
        assert r.json()["current_phase"] == "harvest"
        harvest = r.json()["harvest_words"]
        assert len(harvest) == 1
        assert harvest[0]["source"] == "requested"

        # 6. harvest confirm
        ids = [w["vocab_item_id"] for w in harvest]
        r = await client.post(
            f"/api/lessons/{lesson_id}/harvest/confirm", json={"vocab_item_ids": ids}
        )
        assert r.status_code == 200
        assert r.json()["confirmed"] == 1

        # 7. advance → swiss → completed
        r = await client.post(f"/api/lessons/{lesson_id}/advance", json={})
        assert r.json()["current_phase"] == "swiss"
        r = await client.post(f"/api/lessons/{lesson_id}/advance", json={})
        assert r.json()["status"] == "completed"
        assert r.json()["current_phase"] is None

        # 8. GET lesson
        r = await client.get(f"/api/lessons/{lesson_id}")
        assert r.json()["status"] == "completed"

        # 9. endpoint aggregati
        r = await client.get("/api/progress")
        assert r.status_code == 200
        seeded = len(VOCAB) + sum(len(c["vocab"]) for c in load_seed_content())
        assert r.json()["total_vocab"] == seeded + 1  # curati + generati + 1 richiesta
        assert r.json()["completed_lessons"] == 1

        r = await client.get("/api/home")
        assert r.status_code == 200
        assert r.json()["streak"] >= 0

        r = await client.get("/api/vocab")
        assert r.status_code == 200
        assert len(r.json()) == seeded + 1

        # 10. flashcard review sulla parola richiesta (ora "seen" e dovuta)
        queue = (await client.get("/api/vocab/review-queue")).json()
        assert any(q["id"] == ids[0] for q in queue)
        r = await client.post(f"/api/vocab/{ids[0]}/review", json={"result": "correct"})
        assert r.status_code == 200
        assert r.json()["id"] == ids[0]


@pytest.mark.asyncio
async def test_review_lesson_test_flow(clean_db, mock_llm):
    async with _client() as client:
        lesson_id = (await client.post("/api/lessons")).json()["id"]
        # salta il ciclo base→variant→incident: imposta direttamente una lezione review in fase test
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE lessons SET lesson_type = 'review', current_phase = 'test' WHERE id = :lid"),
                {"lid": lesson_id},
            )

        r = await client.get(f"/api/lessons/{lesson_id}")
        assert r.status_code == 200
        test_words = r.json()["test_words"]
        assert len(test_words) == 15

        # una risposta corretta (lemma) e una sbagliata
        w_ok = test_words[0]
        w_ko = test_words[1]
        lemma_ok = w_ok["de"].replace("der ", "").replace("die ", "").replace("das ", "")
        r = await client.post(
            f"/api/lessons/{lesson_id}/test/answer",
            json={"vocab_item_id": w_ok["vocab_item_id"], "answer": lemma_ok},
        )
        assert r.json()["is_correct"] is True
        r = await client.post(
            f"/api/lessons/{lesson_id}/test/answer",
            json={"vocab_item_id": w_ko["vocab_item_id"], "answer": "xyzqwertz"},
        )
        assert r.json()["is_correct"] is False

        # advance test -> harvest: la parola sbagliata diventa source="error"
        r = await client.post(f"/api/lessons/{lesson_id}/advance", json={})
        assert r.json()["current_phase"] == "harvest"
        harvest = r.json()["harvest_words"]
        assert [w["vocab_item_id"] for w in harvest] == [w_ko["vocab_item_id"]]
        assert harvest[0]["source"] == "error"


@pytest.mark.asyncio
async def test_abandon_and_current(clean_db, mock_llm):
    async with _client() as client:
        r = await client.post("/api/lessons")
        lesson_id = r.json()["id"]

        r = await client.get("/api/lessons/current")
        assert r.json()["lesson"]["id"] == lesson_id

        r = await client.post(f"/api/lessons/{lesson_id}/abandon")
        assert r.json()["status"] == "abandoned"

        r = await client.get("/api/lessons/current")
        assert r.json()["lesson"] is None


class _NoTranslationsMock(LlmClient):
    """Mock senza traduzioni: le parole richieste restano placeholder."""

    async def complete(self, task, messages, schema=None, session=None, **kwargs):
        if task == "warmup_feedback":
            return {"is_correct": True, "corrected_sentence": None, "feedback_it": "Ok.", "error_type": "none"}
        if task == "roleplay":
            return {"text": "Grüezi!", "dialogue_closed": False, "translations": []}
        if task == "corrector":
            return {"comprehensible": True, "errors": [], "new_words_from_agent": []}
        raise NotImplementedError(task)


@pytest.mark.asyncio
async def test_placeholder_not_confirmable_nor_queued(clean_db):
    app.dependency_overrides[get_llm] = lambda: _NoTranslationsMock()
    try:
        async with _client() as client:
            r = await client.post("/api/lessons")
            lesson_id = r.json()["id"]
            for w in r.json()["warmup_words"]:
                await client.post(
                    f"/api/lessons/{lesson_id}/warmup/answer",
                    json={"vocab_item_id": w["vocab_item_id"], "sentence": "Ich kaufe das."},
                )
            await client.post(f"/api/lessons/{lesson_id}/advance", json={})
            await client.post(f"/api/lessons/{lesson_id}/advance", json={})

            r = await client.post(
                f"/api/lessons/{lesson_id}/roleplay/message", json={"content": "Ich suche [uova]."}
            )
            wid = r.json()["requested_words"][0]["vocab_item_id"]
            assert r.json()["requested_words"][0]["de"] == "uova"  # ancora placeholder

            await client.post(f"/api/lessons/{lesson_id}/advance", json={})  # harvest
            r = await client.post(
                f"/api/lessons/{lesson_id}/harvest/confirm", json={"vocab_item_ids": [wid]}
            )

            vocab = (await client.get("/api/vocab")).json()
            word = next(v for v in vocab if v["id"] == wid)
            assert word["state"] == "new"  # un placeholder non può essere confermato

            queue = (await client.get("/api/vocab/review-queue")).json()
            assert all(q["id"] != wid for q in queue)
    finally:
        app.dependency_overrides.clear()


class _CorrectorErrorMock(LlmClient):
    """Mock che segnala un errore del Korrektor su «Das Bier» (consolidata)."""

    async def complete(self, task, messages, schema=None, session=None, **kwargs):
        if task == "warmup_feedback":
            return {"is_correct": True, "corrected_sentence": None, "feedback_it": "Ok.", "error_type": "none"}
        if task == "roleplay":
            return {"text": "Grüezi!", "dialogue_closed": False, "translations": []}
        if task == "corrector":
            return {
                "comprehensible": True,
                "errors": [
                    {"span": "Die bier", "fix": "Das Bier", "type": "gender", "rule_it": "Articolo neutro."}
                ],
                "new_words_from_agent": [],
            }
        raise NotImplementedError(task)


@pytest.mark.asyncio
async def test_consolidated_downgraded_on_corrector_error(clean_db):
    async with engine.begin() as conn:
        vid = (
            await conn.execute(text("SELECT id FROM vocab_items WHERE de = 'das Bier'"))
        ).scalar()
        await conn.execute(
            text(
                "UPDATE vocab_progress SET state='consolidated', correct_uses=3, interval_days=21 "
                "WHERE vocab_item_id = :vid"
            ),
            {"vid": vid},
        )

    app.dependency_overrides[get_llm] = lambda: _CorrectorErrorMock()
    try:
        async with _client() as client:
            lesson_id = (await client.post("/api/lessons")).json()["id"]
            # salta il warmup: vai direttamente in roleplay (evita il ripescaggio SRS)
            async with engine.begin() as conn:
                await conn.execute(
                    text("UPDATE lessons SET current_phase = 'roleplay' WHERE id = :lid"),
                    {"lid": lesson_id},
                )
            await client.post(
                f"/api/lessons/{lesson_id}/roleplay/message",
                json={"content": "Ich mochte das Bier kaufen."},
            )
            # advance roleplay -> harvest: attende il Korrektor pendente (background)
            await client.post(f"/api/lessons/{lesson_id}/advance", json={})

            async with engine.connect() as conn:
                res = await conn.execute(
                    text("SELECT state, lapses FROM vocab_progress WHERE vocab_item_id = :vid"),
                    {"vid": vid},
                )
                state, lapses = res.one()
            assert state == "used"
            assert lapses == 1
    finally:
        app.dependency_overrides.clear()
