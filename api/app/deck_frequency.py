"""Ordina le carte nuove del mazzo per frequenza d'uso.

La Wortliste B1 non ha dati di frequenza: si incrocia con una lista ``parola
conteggio`` (es. FrequencyWords ``de_50k.txt``, sottotitoli OpenSubtitles) e si
scrive ``deck_notes.freq_rank`` (1 = più usata). Il progresso delle carte non
viene toccato; si può rilanciare dopo ogni import.

    make deck-rank   # usa api/app/seed_content/de_50k.txt (FrequencyWords, CC BY-SA 4.0)
"""
from __future__ import annotations

import asyncio
import re
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models import DeckNote

STOP = {"der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "sich", "hat", "ist", "jdn", "jdm", "etw"}
_WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")
_PARENS = re.compile(r"\([^)]*\)")
_ENDINGS = ("e", "er", "es", "en", "em")
_PLURAL = re.compile(r"(?<![^\W\d_])¨?-[^\W\d_]*")  # -se, ¨-er, -nen: trattino non attaccato a una lettera


def load_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in text.splitlines():
        word, _, n = line.strip().rpartition(" ")
        if word and n.isdigit():
            counts[word.lower()] = int(n)
    return counts


def _words(text: str, keep_stop: bool = False) -> list[str]:
    words = [w.lower() for w in _WORD.findall(text) if w.replace("-", "").isalpha()]  # esclude ½
    return words if keep_stop else [w for w in words if w not in STOP]


def _form_word(form: str, last: bool) -> str | None:
    """Parola da contare in una forma coniugata, o None.

    Forme intermedie: solo se di una parola ("zieht", "war"; non "teilt mit",
    "hat an"). Ultima forma (Perfekt): il participio dopo hat/ist/sich.
    """
    words = _words(form, keep_stop=True)
    if len(words) == 1:
        return words[0]
    if last and words and set(words[:-1]) <= {"hat", "ist", "sich"}:
        return words[-1]
    return None


def _alt_score(alt: str, counts: dict[str, int]) -> int | None:
    """Conteggio di un'alternativa ("das/der Sandwich" → "der Sandwich"); None se vuota."""
    alt = alt.strip()
    if alt.endswith("-"):
        # tema declinabile (dies-, all-, ander-): somma le forme con desinenza;
        # prefisso (Sonder-, un-, ein-, "was für ein-"): non è una parola da contare
        stem = alt[:-1]
        if not stem.isalpha() or not stem.islower() or stem in STOP:
            return 0
        return sum(counts.get(stem + e, 0) for e in _ENDINGS)
    words = _words(alt)
    return min(counts.get(w, 0) for w in words) if words else None  # espressioni: la più rara


def score(de: str, counts: dict[str, int]) -> int:
    """Conteggio d'uso di una voce; 0 se la parola base non è nella lista."""
    left = _PLURAL.sub(" ", _PARENS.sub(" ", de.split("→")[0]))
    head, *forms = left.split(",")
    alts = [s for s in (_alt_score(a, counts) for a in head.split("/")) if s is not None]
    if not alts:
        return 0
    base = max(alts)  # "Glace/Glacé": vince l'alternativa più usata
    if not base or len(alts) > 1 or len(_words(head)) != 1 or head.strip().endswith("-"):
        return base
    # parola singola (verbo, nome con plurale intero): somma le forme (vedi _form_word)
    words = [_form_word(f, last=i == len(forms) - 1) for i, f in enumerate(forms)]
    return base + sum(counts.get(w, 0) for w in words if w)


def ranks(notes: list[tuple[int, str]], counts: dict[str, int]) -> dict[int, int]:
    """``{note_id: rank}``: più usata prima; a parità (e per le sconosciute) ordine di file."""
    ordered = sorted(notes, key=lambda n: (-score(n[1], counts), n[0]))
    return {note_id: i for i, (note_id, _) in enumerate(ordered, start=1)}


async def _main(text: str) -> None:
    counts = load_counts(text)
    async with SessionLocal() as session:
        notes = (await session.scalars(select(DeckNote))).all()
        new_ranks = ranks([(n.id, n.de) for n in notes], counts)
        for n in notes:
            n.freq_rank = new_ranks[n.id]
        await session.commit()
    unknown = sum(1 for n in notes if score(n.de, counts) == 0)
    print(f"note ordinate: {len(notes)} · non trovate nella lista (in coda): {unknown}")


if __name__ == "__main__":
    asyncio.run(_main(sys.stdin.read()))
