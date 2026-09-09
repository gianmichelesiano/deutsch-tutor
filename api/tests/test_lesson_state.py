import pytest

from app.lesson_state import (
    PHASES,
    InvalidTransition,
    advance_phase,
    back_phase,
    should_repeat_scenario,
)


def test_full_forward_sequence() -> None:
    current = "warmup"
    for expected in ("prep", "roleplay", "harvest", "swiss", "completed"):
        current = advance_phase(current)
        assert current == expected


def test_swiss_goes_to_completed() -> None:
    assert advance_phase("swiss") == "completed"


def test_harvest_skip_swiss() -> None:
    assert advance_phase("harvest", skip_swiss=True) == "completed"
    assert advance_phase("harvest") == "swiss"


def test_advance_from_completed_raises() -> None:
    with pytest.raises(InvalidTransition):
        advance_phase("completed")


def test_back_only_from_roleplay() -> None:
    assert back_phase("roleplay") == "prep"


def test_back_from_other_phases_raises() -> None:
    for phase in ("warmup", "prep", "harvest", "swiss"):
        with pytest.raises(InvalidTransition):
            back_phase(phase)


def test_repeat_scenario_rule() -> None:
    assert should_repeat_scenario(7) is True
    assert should_repeat_scenario(6) is False
    assert should_repeat_scenario(0) is False


def test_phase_order() -> None:
    assert PHASES == ("warmup", "prep", "roleplay", "harvest", "swiss")
