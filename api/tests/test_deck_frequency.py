from app.deck_frequency import load_counts, ranks, score

COUNTS = load_counts(
    "ich 1000\nziehen 300\nzieht 200\nzog 50\ngezogen 80\nzeugnis 40\nmit 900\nmitgeteilt 7\n"
    "mitteilen 9\nteilt 60\nbabysitter 5\nguten 400\nmorgen 350\nhalb 30\ne-mail 20\nverhalten 25\n"
    "sandwich 15\nglace 2\nglacé 3\nsein 800\nzu 900\nwar 500\nein 2000\ndas 3000\nder 2500\n"
    "anhaben 4\nan 950\nhatte 600\nangehabt 1\nist 990\ngewesen 70\ndiese 100\ndieser 50\nhier 700\n"
)


def test_noun_uses_singular_and_ignores_plural_markers() -> None:
    assert score("das Zeugnis, -se", COUNTS) == 40
    assert score("der Babysitter, -/die Babysitterin, -nen", COUNTS) == 5


def test_verb_sums_single_word_forms_only() -> None:
    assert score("ziehen, zieht, zog, hat/ist gezogen", COUNTS) == 300 + 200 + 50 + 80
    # "teilt mit" è di due parole: "teilt"/"mit" non vanno contati per "mitteilen"
    assert score("mitteilen, teilt mit, teilte mit, hat mitgeteilt", COUNTS) == 9 + 7


def test_reflexive_parentheses_arrow_and_hyphen() -> None:
    assert score("sich verhalten, verhält sich, verhielt sich, hat sich verhalten", COUNTS) == 25 + 25
    assert score("das Zeugnis, -se (CH) → D, A: Mitteilung", COUNTS) == 40
    assert score("die E-Mail, -s", COUNTS) == 20


def test_phrase_uses_rarest_word_and_unknown_is_zero() -> None:
    assert score("Guten Morgen!", COUNTS) == 350
    assert score("½ = ein halb; halb …", COUNTS) == 30
    assert score("der Pöstler, - (CH)", COUNTS) == 0


def test_ranks_by_score_then_file_order() -> None:
    notes = [(1, "der Pöstler, -"), (2, "das Zeugnis, -se"), (3, "ziehen, zieht, zog, hat gezogen"), (4, "die Bude, -n")]
    assert ranks(notes, COUNTS) == {3: 1, 2: 2, 1: 3, 4: 4}


def test_article_alternatives_prefixes_and_function_word_forms() -> None:
    assert score("das/der Sandwich, -(e)s/-e", COUNTS) == 15
    assert score("die/das Glace/Glacé, -n (CH) → D, A: Eis", COUNTS) == 3
    assert score("ein-", COUNTS) == 0
    assert score("Speise-/-speise, -n", COUNTS) == 0
    # "zu sein" è un'espressione: niente somma delle forme ("ist zu" ≠ "zu")
    assert score("zu sein, ist zu, war zu, ist zu gewesen", COUNTS) == 800


def test_separable_present_forms_do_not_count_the_particle() -> None:
    assert score("anhaben, hat an, hatte an, hat angehabt", COUNTS) == 4 + 1
    assert score("sein, ist, war, ist gewesen", COUNTS) == 800 + 990 + 500 + 70


def test_declinable_stems_sum_their_endings() -> None:
    assert score("dies-", COUNTS) == 150
    assert score("hier/hier-", COUNTS) == 700
    assert score("Sonder-", COUNTS) == 0
    assert score("was für ein-", COUNTS) == 0
