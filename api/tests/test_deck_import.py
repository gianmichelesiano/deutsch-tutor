import io
import sqlite3
import zipfile

import pytest

from app.deck_import import Row, parse


def make_apkg(notes: list[list[str]], name: str = "collection.anki2") -> bytes:
    """``.apkg`` minimo: zip con una collection SQLite che ha solo ``notes(id, flds)``."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, flds TEXT)")
    # id volutamente non in ordine di inserimento: l'import segue l'id
    for i, fields in reversed(list(enumerate(notes, start=100))):
        conn.execute("INSERT INTO notes VALUES (?, ?)", (i, "\x1f".join(fields)))
    conn.commit()
    blob = conn.serialize()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, blob)
        z.writestr("media", "{}")
    return buf.getvalue()


def test_apkg_fields_read_by_position_like_the_real_wortliste() -> None:
    data = make_apkg(
        [
            ["das Baby, -s", "il bebè", "Anglicismi", "", ""],
            ["die Anzeige, -n", "l&#x27;annuncio", "Linguaggio delle istruzioni", "Lesen Sie die Anzeigen.", "Legga gli annunci."],
        ]
    )
    parsed = parse(data)
    assert parsed.skipped == 0
    assert parsed.rows == [
        Row("das Baby, -s", "il bebè", "Anglicismi", "", ""),
        Row("die Anzeige, -n", "l'annuncio", "Linguaggio delle istruzioni", "Lesen Sie die Anzeigen.", "Legga gli annunci."),
    ]


def test_apkg_new_format_is_rejected() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("collection.anki21b", b"zstd")
    with pytest.raises(ValueError, match="anki21b"):
        parse(buf.getvalue())


def test_tsv_skips_header_blank_and_incomplete_rows() -> None:
    tsv = (
        "# voce tedesca\ttraduzione italiana\ttema\tfrase\ttraduzione\n"
        "das Steak, -s\tla bistecca\tAnglicismi\n"
        "\n"
        "nur Deutsch\t\tWortschatz\t\t\n"
        "das Ziel, -e\tl'obiettivo\tWortschatz (lista alfabetica)\tDas ist mein Ziel.\tÈ il mio obiettivo.\n"
    ).encode()
    parsed = parse(tsv)
    assert parsed.skipped == 1
    assert [r.de for r in parsed.rows] == ["das Steak, -s", "das Ziel, -e"]
    assert parsed.rows[1].example_it == "È il mio obiettivo."


def test_misaligned_columns_abort_the_import() -> None:
    # ordine dichiarato dal modello Anki (FraseDE al posto del tema): non va importato
    data = make_apkg([["das Ziel, -e", "l'obiettivo", "Das ist mein Ziel.", "È il mio obiettivo.", "Wortschatz"]])
    with pytest.raises(ValueError, match="tema"):
        parse(data)
    with pytest.raises(ValueError, match="tema"):
        parse(make_apkg([["das Baby, -s", "il bebè", "", "", "Anglicismi"]]))
