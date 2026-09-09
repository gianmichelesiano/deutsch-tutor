from app.parser import parse_requested_terms


def test_parse_simple() -> None:
    assert parse_requested_terms("Ich suche [uova].") == ["uova"]


def test_parse_multiple() -> None:
    assert parse_requested_terms("Ich brauche [mehl] und [zucker].") == ["mehl", "zucker"]


def test_parse_none() -> None:
    assert parse_requested_terms("Ich brauche Brot.") == []


def test_parse_trims_whitespace() -> None:
    assert parse_requested_terms("Ich suche [ die eier ].") == ["die eier"]
