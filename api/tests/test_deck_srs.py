import random
from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.deck_srs import (
    AGAIN,
    EASY,
    GOOD,
    HARD,
    MIN_EASE,
    CardState,
    answer,
    day_start,
    format_interval,
    next_day_start,
    previews,
)

NOW = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
ZURICH = ZoneInfo("Europe/Zurich")


def review(interval: int, ease: float = 2.5) -> CardState:
    return CardState(state="review", interval_days=interval, ease=ease, due=NOW)


def test_new_good_goes_through_learning_steps_then_graduates() -> None:
    c = answer(CardState(), GOOD, NOW)
    assert (c.state, c.step, c.due) == ("learning", 1, NOW + timedelta(minutes=10))
    c = answer(c, GOOD, NOW)
    assert (c.state, c.interval_days, c.due) == ("review", 1, NOW + timedelta(days=1))


def test_new_again_and_hard_stay_on_first_step() -> None:
    assert answer(CardState(), AGAIN, NOW).due == NOW + timedelta(minutes=1)
    c = answer(CardState(state="learning", step=1), HARD, NOW)
    assert (c.step, c.due) == (1, NOW + timedelta(minutes=10))
    assert answer(CardState(state="learning", step=1), AGAIN, NOW).step == 0


def test_new_easy_graduates_to_four_days() -> None:
    c = answer(CardState(), EASY, NOW)
    assert (c.state, c.interval_days, c.due) == ("review", 4, NOW + timedelta(days=4))


def test_review_good_hard_easy() -> None:
    assert answer(review(10), GOOD, NOW).interval_days == 25
    hard = answer(review(10), HARD, NOW)
    assert (hard.interval_days, hard.ease) == (12, 2.35)
    easy = answer(review(10), EASY, NOW)
    assert (easy.interval_days, easy.ease) == (32, 2.65)


def test_review_interval_grows_by_at_least_one_day() -> None:
    assert answer(review(1, ease=1.3), HARD, NOW).interval_days == 2
    assert answer(review(1, ease=1.3), GOOD, NOW).interval_days == 2


def test_review_again_lapses_into_relearning_then_back_to_one_day() -> None:
    c = answer(review(30), AGAIN, NOW)
    assert (c.state, c.lapses, c.interval_days, c.ease) == ("relearning", 1, 1, 2.3)
    assert c.due == NOW + timedelta(minutes=10)
    c = answer(c, GOOD, NOW)
    assert (c.state, c.interval_days, c.due) == ("review", 1, NOW + timedelta(days=1))


def test_ease_never_below_minimum() -> None:
    c = review(5, ease=MIN_EASE)
    for _ in range(3):
        c = answer(c, AGAIN, NOW)
        c = answer(c, GOOD, NOW)
    assert c.ease == MIN_EASE


def test_fuzz_stays_close_and_skips_short_intervals() -> None:
    rng = random.Random(1)
    got = {answer(review(40), GOOD, NOW, rng=rng).interval_days for _ in range(200)}
    assert min(got) >= 95 and max(got) <= 105 and len(got) > 1  # 100 ± 5%
    assert {answer(CardState(), GOOD, NOW, rng=rng).step for _ in range(5)} == {1}
    # sotto i 3 giorni niente fuzz
    assert {answer(review(1, ease=1.3), GOOD, NOW, rng=rng).interval_days for _ in range(50)} == {2}


def test_day_starts_at_four_local() -> None:
    before = datetime(2026, 10, 15, 3, 59, tzinfo=ZURICH)
    after = datetime(2026, 10, 15, 4, 0, tzinfo=ZURICH)
    assert day_start(before, ZURICH) == datetime(2026, 10, 14, 4, 0, tzinfo=ZURICH)
    assert day_start(after, ZURICH) == datetime(2026, 10, 15, 4, 0, tzinfo=ZURICH)
    assert next_day_start(after, ZURICH) == datetime(2026, 10, 16, 4, 0, tzinfo=ZURICH)


def test_next_day_across_dst_change_is_25_hours() -> None:
    # 25 ottobre 2026: fine dell'ora legale, la giornata dura 25 ore
    now = datetime(2026, 10, 24, 12, 0, tzinfo=ZURICH)
    utc = UTC
    assert next_day_start(now, ZURICH).astimezone(utc) - day_start(now, ZURICH).astimezone(utc) == timedelta(hours=25)


def test_previews_match_answer_without_fuzz() -> None:
    c = review(10)
    labels = previews(c, NOW)
    assert labels == [format_interval(answer(c, r, NOW).due - NOW) for r in (AGAIN, HARD, GOOD, EASY)]
    assert labels == ["10m", "12g", "25g", "1,1 mesi"]
    assert previews(CardState(), NOW) == ["1m", "1m", "10m", "4g"]


def test_format_interval() -> None:
    assert format_interval(timedelta(minutes=1)) == "1m"
    assert format_interval(timedelta(days=3)) == "3g"
    assert format_interval(timedelta(days=45)) == "1,5 mesi"
    assert format_interval(timedelta(days=30)) == "1 mese"
    assert format_interval(timedelta(days=400)) == "1,1 anni"
