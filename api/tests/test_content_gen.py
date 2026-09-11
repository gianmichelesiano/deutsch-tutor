"""Validatore anti-dialetto del generatore contenuti (task 3.4)."""
from app.content_gen import dialect_hits


def test_dialect_hits_detects_schweizerdeutsch():
    content = {
        "role_label": "Nachbarin",
        "key_phrases": [{"de": "Chömed Sie doch ine."}, {"de": "Kommen Sie doch rein."}],
        "imprevisti": ["D'Waschmaschine isch besetzt.", "Die Waschmaschine ist besetzt."],
        "goals": ["Hesch scho öppis vor?"],
    }
    hits = dialect_hits(content)
    assert "Chömed Sie doch ine." in hits
    assert "D'Waschmaschine isch besetzt." in hits
    assert "Hesch scho öppis vor?" in hits
    assert "Kommen Sie doch rein." not in hits
    assert "Die Waschmaschine ist besetzt." not in hits


def test_dialect_hits_accepts_hochdeutsch_with_helvetisms():
    content = {
        "role_label": "Kellnerin",
        "key_phrases": [
            {"de": "Grüezi, haben Sie reserviert?"},
            {"de": "Ich fahre mit dem Velo zur Arbeit."},
            {"de": "Das macht zwölf Franken, bitte."},
            {"de": "Wir treffen uns im Treppenhaus."},
        ],
        "imprevisti": ["Das Gericht ist ausverkauft.", "Der Zug hat Verspätung."],
        "goals": ["Einen Tisch reservieren."],
    }
    assert dialect_hits(content) == []
