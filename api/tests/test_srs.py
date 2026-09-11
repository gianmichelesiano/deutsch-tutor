import random
from datetime import datetime, timedelta

from app.srs import (
    Candidate,
    Progress,
    apply_review,
    is_due,
    next_interval,
    pick_due,
    rank,
    rescue_consolidated,
    should_consolidate,
)

NOW = datetime(2026, 9, 9, 12, 0, 0)


def test_next_interval_sequence() -> None:
    assert next_interval(0) == 1
    assert next_interval(1) == 3
    assert next_interval(3) == 7
    assert next_interval(7) == 21
    assert next_interval(21) == 21  # capped


def test_four_intervals_advance_on_correct() -> None:
    p = Progress()
    for expected in (1, 3, 7, 21):
        p = apply_review(p, result="correct", now=NOW, distinct_correct_lessons=1, counts_for_consolidation=True)
        assert p.interval_days == expected
    # oltre 21 resta 21
    p = apply_review(p, result="correct", now=NOW, distinct_correct_lessons=1, counts_for_consolidation=True)
    assert p.interval_days == 21


def test_wrong_resets_interval_and_increments_lapses() -> None:
    p = Progress(interval_days=7, lapses=1)
    p2 = apply_review(p, result="wrong", now=NOW)
    assert p2.interval_days == 1
    assert p2.lapses == 2
    assert p2.next_review_at == NOW + timedelta(days=1)


def test_consolidation_after_three_distinct_lessons() -> None:
    p = Progress(state="used", correct_uses=2)
    p2 = apply_review(p, result="correct", now=NOW, distinct_correct_lessons=3, counts_for_consolidation=True)
    assert p2.state == "consolidated"
    assert p2.correct_uses == 3


def test_two_lessons_do_not_consolidate() -> None:
    p = Progress(state="used", correct_uses=1)
    p2 = apply_review(p, result="correct", now=NOW, distinct_correct_lessons=2, counts_for_consolidation=True)
    assert p2.state == "used"
    assert p2.correct_uses == 2


def test_flashcard_correct_does_not_count_for_consolidation() -> None:
    p = Progress(state="new", correct_uses=0)
    p2 = apply_review(p, result="correct", now=NOW, distinct_correct_lessons=3, counts_for_consolidation=False)
    assert p2.correct_uses == 0  # non avanza
    assert p2.state == "seen"  # non diventa "used"
    assert p2.interval_days == 1  # avanza comunque l'intervallo


def test_is_due() -> None:
    assert is_due(None, NOW) is True
    assert is_due(NOW - timedelta(days=1), NOW) is True
    assert is_due(NOW, NOW) is True
    assert is_due(NOW + timedelta(days=1), NOW) is False


def test_should_consolidate_threshold() -> None:
    assert should_consolidate(3) is True
    assert should_consolidate(2) is False


def test_ranking_priority() -> None:
    old = NOW - timedelta(days=10)
    c_curated_low_lapse = Candidate(1, "seen", 0, NOW - timedelta(days=1), "curated", old)
    c_error_high_lapse = Candidate(2, "seen", 3, NOW - timedelta(days=1), "error", old)
    c_not_due = Candidate(3, "seen", 99, NOW + timedelta(days=5), "error", NOW)
    ranked = rank([c_curated_low_lapse, c_not_due, c_error_high_lapse], NOW)
    # dovuti prima; tra i dovuti, lapses alto prima
    assert ranked[0].id == 2
    assert ranked[1].id == 1
    assert ranked[2].id == 3


def test_pick_due_filters_not_due() -> None:
    due = Candidate(1, "seen", 0, NOW - timedelta(days=1), "curated", NOW)
    not_due = Candidate(2, "seen", 0, NOW + timedelta(days=1), "curated", NOW)
    picked = pick_due([due, not_due], NOW, limit=10)
    assert [c.id for c in picked] == [1]


def _consolidated(id_: int, reviewed: datetime = NOW) -> Candidate:
    return Candidate(id_, "consolidated", 0, reviewed, "curated", NOW)


def test_rescue_consolidated_returns_ten_percent() -> None:
    consolidated = [_consolidated(i) for i in range(10)]
    rng = random.Random(42)
    rescued = rescue_consolidated(consolidated, rng, ratio=0.1)
    assert len(rescued) == 1  # 10% di 10 = 1
    assert rescued[0].state == "consolidated"


def test_rescue_consolidated_minimum_one() -> None:
    consolidated = [_consolidated(1), _consolidated(2), _consolidated(3)]
    rng = random.Random(7)
    rescued = rescue_consolidated(consolidated, rng, ratio=0.1)
    assert len(rescued) == 1  # round(0.3)=0 → minimo 1


def test_rescue_consolidated_empty_when_no_consolidated() -> None:
    due = Candidate(1, "seen", 0, NOW - timedelta(days=1), "curated", NOW)
    assert rescue_consolidated([due], random.Random(1)) == []


def test_pick_due_includes_rescued_consolidated() -> None:
    due = Candidate(1, "seen", 0, NOW - timedelta(days=1), "curated", NOW)
    consolidated = [_consolidated(i) for i in range(10)]
    rng = random.Random(123)
    picked = pick_due([due] + consolidated, NOW, limit=10, rng=rng)
    ids = [c.id for c in picked]
    assert 1 in ids  # il dovuto c'è sempre
    # una consolidata ripescata è inclusa
    assert any(c.state == "consolidated" for c in picked)


def test_pick_due_rescue_is_deterministic_with_seed() -> None:
    due = Candidate(1, "seen", 0, NOW - timedelta(days=1), "curated", NOW)
    consolidated = [_consolidated(i) for i in range(20)]
    a = pick_due([due] + consolidated, NOW, limit=10, rng=random.Random(99))
    b = pick_due([due] + consolidated, NOW, limit=10, rng=random.Random(99))
    assert [c.id for c in a] == [c.id for c in b]


def test_pick_due_no_consolidated_without_rescue_pool() -> None:
    due = Candidate(1, "seen", 0, NOW - timedelta(days=1), "curated", NOW)
    picked = pick_due([due], NOW, limit=10, rng=random.Random(0))
    assert [c.id for c in picked] == [1]
