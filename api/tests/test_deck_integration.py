from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.config import settings
from app.db import SessionLocal, engine
from app.deck_import import Row, import_rows
from app.main import app
from app.models import DeckCard

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
ROWS = [
    Row("das Baby, -s", "il bebè", "Anglicismi", "", ""),
    Row("die Band, -s", "la band", "Anglicismi", "", ""),
    Row("das Ziel, -e", "l'obiettivo", "Wortschatz", "Das ist mein Ziel.", "È il mio obiettivo."),
]
AGAIN, GOOD, EASY = 1, 3, 4


@pytest.fixture
async def deck(monkeypatch):
    assert str(engine.url.database).endswith("_test"), f"rifiuto TRUNCATE su {engine.url.database}"
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE deck_reviews, deck_cards, deck_notes RESTART IDENTITY CASCADE"))
    clock = {"now": NOW}
    monkeypatch.setattr("app.routers.deck.utcnow", lambda: clock["now"])
    monkeypatch.setattr("app.routers.deck._rng", None)  # niente fuzz: intervalli esatti
    monkeypatch.setattr(settings, "deck_new_per_day", 20)
    async with SessionLocal() as session:
        await import_rows(session, ROWS)
    yield clock


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _answer(client, card_id: int, rating: int) -> dict:
    r = await client.post(f"/api/deck/cards/{card_id}/answer", json={"rating": rating})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_reimport_is_idempotent_and_keeps_progress(deck):
    async with _client() as client:
        first = (await client.get("/api/deck/next")).json()["card"]
        await _answer(client, first["id"], EASY)
    changed = [ROWS[0], ROWS[1], Row("das Ziel, -e", "l'obiettivo", "Wortschatz", "Neues Beispiel.", "Nuovo esempio.")]
    async with SessionLocal() as session:
        assert await import_rows(session, changed) == {"created": 0, "updated": 1}
        cards = (await session.scalars(select(DeckCard).order_by(DeckCard.id))).all()
    assert len(cards) == 6
    assert cards[0].state.value == "review" and cards[0].interval_days == 4


@pytest.mark.asyncio
async def test_queue_order_burying_and_summary(deck):
    async with _client() as client:
        nxt = (await client.get("/api/deck/next")).json()
        card = nxt["card"]
        assert (card["de"], card["direction"]) == ("das Baby, -s", "de_it")
        assert nxt["counts"] == {"new": 6, "learning": 0, "review": 0}
        assert nxt["previews"] == ["1m", "1m", "10m", "4g"]

        # la gemella IT→DE di "Baby" slitta a domani: arriva la nota successiva
        nxt = await _answer(client, card["id"], EASY)
        assert (nxt["card"]["de"], nxt["card"]["direction"]) == ("die Band, -s", "de_it")
        assert nxt["counts"]["new"] == 4

        nxt = await _answer(client, nxt["card"]["id"], GOOD)  # Band → learning, +10m
        assert nxt["card"]["de"] == "das Ziel, -e"
        nxt = await _answer(client, nxt["card"]["id"], AGAIN)  # Ziel → learning, +1m

        # nuove finite (tutte gemelle sepolte): learning in anticipo, prima la più vicina
        assert nxt["counts"] == {"new": 0, "learning": 2, "review": 0}
        assert nxt["card"]["de"] == "das Ziel, -e"

        s = (await client.get("/api/deck/summary")).json()
        assert s["total_notes"] == 3
        assert s["cards"] == {"new": 3, "learning": 2, "review": 1, "relearning": 0}
        assert s["reviewed_today"] == 3 and s["notes_started"] == 3

        # domani: gemelle disponibili, learning scadute per prime
        deck["now"] = NOW + timedelta(days=1)
        nxt = (await client.get("/api/deck/next")).json()
        assert nxt["card"]["state"] == "learning"
        assert nxt["counts"] == {"new": 3, "learning": 2, "review": 0}

        # tra 4 giorni "Baby" DE→IT è in ripasso
        deck["now"] = NOW + timedelta(days=4)
        nxt = (await client.get("/api/deck/next")).json()
        assert nxt["counts"]["review"] == 1


@pytest.mark.asyncio
async def test_new_per_day_limit(deck, monkeypatch):
    monkeypatch.setattr(settings, "deck_new_per_day", 1)
    async with _client() as client:
        nxt = (await client.get("/api/deck/next")).json()
        assert nxt["counts"]["new"] == 1
        nxt = await _answer(client, nxt["card"]["id"], EASY)
        assert nxt == {"card": None, "counts": {"new": 0, "learning": 0, "review": 0}, "previews": []}
        # l'utente sceglie un altro mazzo: +1 nuova oltre il limite
        nxt = (await client.get("/api/deck/next", params={"extra": 1})).json()
        assert nxt["counts"]["new"] == 1 and nxt["card"]["state"] == "new"


@pytest.mark.asyncio
async def test_answer_validation(deck):
    async with _client() as client:
        assert (await client.post("/api/deck/cards/1/answer", json={"rating": 5})).status_code == 422
        assert (await client.post("/api/deck/cards/9999/answer", json={"rating": 3})).status_code == 404


@pytest.mark.asyncio
async def test_new_cards_follow_frequency_rank(deck):
    # Ziel più usata, Baby seconda, Band senza rank → in coda
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE deck_notes SET freq_rank = 1 WHERE de = 'das Ziel, -e'"))
        await conn.execute(text("UPDATE deck_notes SET freq_rank = 2 WHERE de = 'das Baby, -s'"))
    async with _client() as client:
        seen = []
        nxt = (await client.get("/api/deck/next")).json()
        for _ in range(3):
            seen.append(nxt["card"]["de"])
            nxt = await _answer(client, nxt["card"]["id"], EASY)
    assert seen == ["das Ziel, -e", "das Baby, -s", "die Band, -s"]


@pytest.mark.asyncio
async def test_notes_list_filters_search_and_counts(deck):
    async with _client() as client:
        r = (await client.get("/api/deck/notes")).json()
        assert r["notes"] == [] and r["total"] == 0  # default: solo parole iniziate
        assert r["counts"] == {"new": 6, "learning": 0, "review": 0, "mature": 0}

        nxt = (await client.get("/api/deck/next")).json()  # Baby DE→IT
        nxt = await _answer(client, nxt["card"]["id"], EASY)  # → review 4g
        await _answer(client, nxt["card"]["id"], AGAIN)  # Band DE→IT → learning
    async with engine.begin() as conn:  # Ziel: matura e "difficile"
        await conn.execute(
            text(
                "UPDATE deck_cards SET state = 'review', interval_days = 30, lapses = 3, "
                "due = now() + interval '30 days' WHERE note_id = 3 AND direction = 'de_it'"
            )
        )

    async with _client() as client:
        r = (await client.get("/api/deck/notes")).json()
        assert r["total"] == 3
        assert r["counts"] == {"new": 3, "learning": 1, "review": 1, "mature": 1}
        band = next(n for n in r["notes"] if n["de"] == "die Band, -s")
        assert [(c["direction"], c["status"]) for c in band["cards"]] == [("de_it", "learning"), ("it_de", "new")]

        async def des(params: str) -> list[str]:
            return [n["de"] for n in (await client.get(f"/api/deck/notes?{params}")).json()["notes"]]

        assert await des("filter=learning") == ["die Band, -s"]
        assert await des("filter=review") == ["das Baby, -s"]
        assert await des("filter=mature") == await des("filter=leech") == ["das Ziel, -e"]
        assert await des("filter=all&q=OBIETT") == ["das Ziel, -e"]
        assert (await client.get("/api/deck/notes?filter=boh")).status_code == 422


@pytest.mark.asyncio
async def test_theme_filter_themes_and_practice(deck):
    async with _client() as client:
        themes = (await client.get("/api/deck/themes")).json()
        assert themes == [{"theme": "Wortschatz", "notes": 1}, {"theme": "Anglicismi", "notes": 2}]

        nxt = (await client.get("/api/deck/next", params={"theme": "Wortschatz"})).json()
        assert nxt["card"]["de"] == "das Ziel, -e" and nxt["counts"]["new"] == 2

        # ripasso libero: anche carte mai viste, e non cambia lo stato SRS
        assert len((await client.get("/api/deck/practice")).json()) == 6
        await client.post(f"/api/deck/cards/{nxt['card']['id']}/answer", params={"theme": "Wortschatz"}, json={"rating": AGAIN})
        practice = (await client.get("/api/deck/practice", params={"mode": "hard"})).json()
        assert practice == []  # nessun errore in review ancora
        practice = (await client.get("/api/deck/practice", params={"theme": "Wortschatz"})).json()
        assert {c["de"] for c in practice} == {"das Ziel, -e"} and len(practice) == 2
        # fasce di frequenza: senza freq_rank nessuna carta cade in una fascia
        assert (await client.get("/api/deck/practice", params={"freq": "top"})).json() == []


@pytest.mark.asyncio
async def test_a1_deck_is_separate_and_only_in_practice(deck):
    # stessa coppia (de, it) di una nota B1: nel mazzo A1 è una nota a parte, con la sola carta DE→IT
    a1 = [Row("das Baby, -s", "il bebè", "A1 Wortliste", "Mein Kind ist noch ein Baby.", "Mio figlio è ancora un bebè.")]
    async with SessionLocal() as session:
        assert await import_rows(session, a1, deck="a1") == {"created": 1, "updated": 0}
        cards = (await session.scalars(select(DeckCard).order_by(DeckCard.id))).all()
    assert len(cards) == 7 and cards[-1].direction.value == "de_it"

    async with _client() as client:
        # Studia, riepilogo, temi, parole e ripasso libero B1 non vedono l'A1
        assert (await client.get("/api/deck/next")).json()["counts"]["new"] == 6
        summary = (await client.get("/api/deck/summary")).json()
        assert summary["total_notes"] == 3 and summary["cards"]["new"] == 6
        assert [t["theme"] for t in (await client.get("/api/deck/themes")).json()] == ["Wortschatz", "Anglicismi"]
        assert (await client.get("/api/deck/notes", params={"filter": "all"})).json()["total"] == 3
        assert len((await client.get("/api/deck/practice")).json()) == 6

        a1_cards = (await client.get("/api/deck/practice", params={"deck": "a1"})).json()
        assert [(c["de"], c["direction"], c["example_de"]) for c in a1_cards] == [
            ("das Baby, -s", "de_it", "Mein Kind ist noch ein Baby.")
        ]
        assert (await client.get("/api/deck/practice", params={"deck": "c2"})).status_code == 422
