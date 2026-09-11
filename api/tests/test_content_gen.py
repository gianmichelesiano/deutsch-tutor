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


def test_dialect_hits_covers_intro_fields():
    intro = {
        "situation": [{"de": "Ich bin im Coop.", "it": "Sono alla Coop."}, {"de": "Ich bi im Coop.", "it": "x"}],
        "dialog": [{"speaker": "Ich", "de": "Grüezi, wie gaht's?", "it": "x"}],
        "notes_it": ["Si usa il Sie."],
    }
    hits = dialect_hits(intro)
    assert "Ich bi im Coop." in hits
    assert "Grüezi, wie gaht's?" in hits
    assert "Ich bin im Coop." not in hits
    # anche quando l'intro è annidato in un contenuto completo
    assert dialect_hits({"role_label": "Kellnerin", "key_phrases": [], "imprevisti": [], "goals": [], "intro": intro}) == hits
