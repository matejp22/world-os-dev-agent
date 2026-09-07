from app.live_state import (
    NO_NEW_MILESTONE,
    current_milestone_version,
    has_active_milestone,
    parse_live_state,
)


ACTIVE_STATE = """
V0.6 STATUS:
COMPLETE

V0.7 STATUS:
COMPLETE

Current milestone:
Developer Console V0.8 — state-aware milestone progression.

Immediate next objective:
Prevent the build planner from repeating completed milestones.
""".strip()


COMPLETED_CURRENT_STATE = """
V0.8 STATUS:
COMPLETE

Current milestone:
Developer Console V0.8 — state-aware milestone progression.

Immediate next objective:
Do something else.
""".strip()


NO_CURRENT_STATE = """
V0.7 STATUS:
COMPLETE
""".strip()


NO_OBJECTIVE_STATE = """
V0.7 STATUS:
COMPLETE

Current milestone:
Developer Console V0.8 — state-aware milestone progression.
""".strip()


def test_parse_live_state_active() -> None:
    state = parse_live_state(ACTIVE_STATE)

    assert state.completed_milestones == (
        "V0.6",
        "V0.7",
    )

    assert state.current_milestone == (
        "Developer Console V0.8 — "
        "state-aware milestone progression."
    )

    assert state.immediate_next_objective == (
        "Prevent the build planner from repeating "
        "completed milestones."
    )

    assert current_milestone_version(state) == "V0.8"
    assert has_active_milestone(state) is True


def test_completed_current_milestone_is_not_active() -> None:
    state = parse_live_state(
        COMPLETED_CURRENT_STATE
    )

    assert current_milestone_version(state) == "V0.8"
    assert has_active_milestone(state) is False


def test_missing_current_milestone_is_not_active() -> None:
    state = parse_live_state(
        NO_CURRENT_STATE
    )

    assert current_milestone_version(state) is None
    assert has_active_milestone(state) is False


def test_missing_objective_is_not_active() -> None:
    state = parse_live_state(
        NO_OBJECTIVE_STATE
    )

    assert current_milestone_version(state) == "V0.8"
    assert has_active_milestone(state) is False


def test_sentinel_constant() -> None:
    assert NO_NEW_MILESTONE == "NO_NEW_MILESTONE"
