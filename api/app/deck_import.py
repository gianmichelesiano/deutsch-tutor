"""Import del mazzo da pacchetto Anki (``.apkg`` legacy) o da TSV.

Uso (il file arriva da stdin, così non deve stare nel container):

    docker compose exec -T api python -m app.deck_import < Wortliste_B1_blocco01_200.apkg
    docker compose exec -T api python -m app.deck_import --deck a1 < A1_wortliste_it.tsv

Entrambi i formati hanno 5 colonne nell'ordine del TSV:
``tedesco, italiano, tema, frase DE, frase IT``. Nei ``.apkg`` generati il modello
dichiara un ordine diverso (FraseDE, FraseIT, Tema) ma i dati seguono quello del
TSV: i campi si leggono quindi per posizione e il tema viene validato. Più frasi
per voce: separate da ``\\n`` (letterale) nelle due colonne delle frasi, nello stesso ordine.

``--deck a1``: mazzo separato (Wortliste A1), una sola carta DE→IT per nota.

Idempotente: chiave ``(deck, de, it)``; le note esistenti aggiornano tema e frasi, il
progresso delle carte non viene toccato.
"""
from __future__ import annotations

import argparse
import asyncio
import html
import io
import sqlite3
import sys
import zipfile
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models import DeckCard, DeckDirection, DeckNote

MAX_THEME_LEN = 80


@dataclass(frozen=True)
class Row:
    de: str
    it: str
    theme: str
    example_de: str
    example_it: str


@dataclass
class Parsed:
    rows: list[Row]
    skipped: int


def _apkg_fields(data: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())
        if "collection.anki21b" in names and not names & {"collection.anki21", "collection.anki2"}:
            raise ValueError(
                "formato Anki nuovo (anki21b) non supportato: esporta con "
                "'Supporta versioni vecchie di Anki'"
            )
        # con entrambi presenti, collection.anki2 è solo un segnaposto per Anki vecchi
        name = "collection.anki21" if "collection.anki21" in names else "collection.anki2"
        if name not in names:
            raise ValueError("pacchetto .apkg senza collection.anki2")
        blob = z.read(name)
    conn = sqlite3.connect(":memory:")
    try:
        conn.deserialize(blob)
        flds = [r[0] for r in conn.execute("SELECT flds FROM notes ORDER BY id")]
    finally:
        conn.close()
    return [[html.unescape(f) for f in note.split("\x1f")] for note in flds]


def _tsv_fields(text: str) -> list[list[str]]:
    return [
        line.split("\t")
        for line in text.splitlines()
        if line.strip() and not line.startswith("#")
    ]


def _looks_like_theme(value: str) -> bool:
    return bool(value) and len(value) <= MAX_THEME_LEN and not value.endswith((".", "?", "!"))


def parse(data: bytes) -> Parsed:
    """Bytes di un ``.apkg`` (zip, inizia con ``PK``) o di un TSV → righe valide.

    Scarta le righe senza tedesco o italiano; solleva ``ValueError`` se il tema
    non è dove deve stare (colonne disallineate): meglio fermarsi che importare
    frasi al posto dei temi.
    """
    raw = _apkg_fields(data) if data[:2] == b"PK" else _tsv_fields(data.decode("utf-8-sig"))
    rows: list[Row] = []
    skipped = 0
    for fields in raw:
        f = [x.strip() for x in fields] + [""] * (5 - len(fields))
        if not f[0] or not f[1]:
            skipped += 1
            continue
        f[3], f[4] = f[3].replace("\\n", "\n"), f[4].replace("\\n", "\n")
        rows.append(Row(*f[:5]))
    bad = [r.de for r in rows if not _looks_like_theme(r.theme)]
    if bad:
        raise ValueError(f"colonna tema non valida in {len(bad)} righe (es. {bad[:3]}): ordine colonne atteso "
                         "tedesco, italiano, tema, frase DE, frase IT")
    return Parsed(rows=rows, skipped=skipped)


async def import_rows(session: AsyncSession, rows: list[Row], deck: str = "b1") -> dict[str, int]:
    """Crea le note mancanti (+ 2 carte nuove ciascuna, 1 nel mazzo A1), aggiorna le esistenti."""
    existing = {(n.de, n.it): n for n in (await session.scalars(select(DeckNote).where(DeckNote.deck == deck))).all()}
    directions = [DeckDirection.de_it] if deck == "a1" else list(DeckDirection)
    created = updated = 0
    for r in rows:
        note = existing.get((r.de, r.it))
        if note is None:
            note = DeckNote(deck=deck, de=r.de, it=r.it, theme=r.theme, example_de=r.example_de, example_it=r.example_it)
            session.add(note)
            await session.flush()  # id in ordine di file: è l'ordine di introduzione delle nuove
            session.add_all([DeckCard(note_id=note.id, direction=d) for d in directions])
            existing[(r.de, r.it)] = note
            created += 1
        elif (note.theme, note.example_de, note.example_it) != (r.theme, r.example_de, r.example_it):
            note.theme, note.example_de, note.example_it = r.theme, r.example_de, r.example_it
            updated += 1
    await session.commit()
    return {"created": created, "updated": updated}


async def _main(data: bytes, deck: str) -> None:
    parsed = parse(data)
    async with SessionLocal() as session:
        counts = await import_rows(session, parsed.rows, deck)
    print(
        f"note create: {counts['created']} · aggiornate: {counts['updated']} · "
        f"invariate: {len(parsed.rows) - counts['created'] - counts['updated']} · "
        f"scartate: {parsed.skipped}"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Import del mazzo da stdin (.apkg o .tsv)")
    ap.add_argument("--deck", choices=["b1", "a1"], default="b1")
    try:
        asyncio.run(_main(sys.stdin.buffer.read(), ap.parse_args().deck))
    except ValueError as e:
        sys.exit(f"import annullato: {e}")
