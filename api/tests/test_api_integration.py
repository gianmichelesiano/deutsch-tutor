import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import engine
from app.deps import get_llm
from app.llm import MockLlmClient
from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
async def clean_db():
    """Riporta il DB allo stato di seed: 40 vocab curati 'new', nessuna lezione."""
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
        assert r.json()["total_vocab"] == 41  # 40 curati + 1 richiesta
        assert r.json()["completed_lessons"] == 1

        r = await client.get("/api/home")
        assert r.status_code == 200
        assert r.json()["streak"] >= 0

        r = await client.get("/api/vocab")
        assert r.status_code == 200
        assert len(r.json()) == 41

        # 10. flashcard review sulla parola richiesta (ora "seen" e dovuta)
        queue = (await client.get("/api/vocab/review-queue")).json()
        assert any(q["id"] == ids[0] for q in queue)
        r = await client.post(f"/api/vocab/{ids[0]}/review", json={"result": "correct"})
        assert r.status_code == 200
        assert r.json()["id"] == ids[0]


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
