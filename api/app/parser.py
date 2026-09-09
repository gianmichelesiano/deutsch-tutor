"""Parser deterministico per i termini richiesti con ``[parola italiana]``."""
import re

_BRACKET_RE = re.compile(r"\[([^\]]+)\]")


def parse_requested_terms(text: str) -> list[str]:
    """Estrae i termini italiani racchiusi tra parentesi quadre.

    Es. ``"Ich suche [uova] und [mehl]"`` -> ``["uova", "mehl"]``.
    """
    return [m.strip() for m in _BRACKET_RE.findall(text)]
