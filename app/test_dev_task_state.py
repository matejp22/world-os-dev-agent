from __future__ import annotations

import json

from app.dev_task_state import (
    DevTaskState,
    derive_task_state,
    plan_task_state_transition,
    resolve_task_state,
    task_state_from_dict,
    task_state_to_dict,
)
from app.live_state import LiveState


V09_MILESTONE = (
    "Developer Console V0.9 \u2014 persistent task and handoff state."
)

V08_MILESTONE = (
    "Developer Console V0.8 \u2014 state-aware milestone progression."
)

V20_MILESTONE = (
    "Developer Console V2.0 \u2014 Functional World OS Dev Agent."
)

V15_MILESTONE = (
    "Developer Console V1.5 \u2014 Test and CI awareness."
)

V20_OBJECTIVE = (
    "Make the Developer Console the primary operating interface."
)


def active_live_state() -> LiveState:
    return LiveState(
        completed_milestones=(),
        current_milestone=V09_MILESTONE,
        next_milestone=None,
        next_milestone_objective=None,
        current_objective="Persist development task state.",
        current_objective_status="IN_PROGRESS",
        immediate_next_objective="Add resume integration.",
    )


def handoff_live_state() -> LiveState:
    return LiveState(
        completed_milestones=("V0.8",),
        current_milestone=V08_MILESTONE,
        next_milestone=V09_MILESTONE,
        next_milestone_objective=(
            "Introduce explicit persistent development-task state."
        ),
        current_objective="Complete milestone progression.",
        current_objective_status="COMPLETE",
        immediate_next_objective=None,
    )


def stopped_live_state() -> LiveState:
    return LiveState(
        completed_milestones=("V0.9",),
        current_milestone=V09_MILESTONE,
        next_milestone=None,
        next_milestone_objective=None,
        current_objective="Complete persistent task state.",
        current_objective_status="COMPLETE",
        immediate_next_objective=None,
    )


def active_v20_live_state() -> LiveState:
    return LiveState(
        completed_milestones=("V1.5",),
        current_milestone=V20_MILESTONE,
        next_milestone=None,
        next_milestone_objective=None,
        current_objective=V20_OBJECTIVE,
        current_objective_status="ACTIVE",
        immediate_next_objective=None,
    )


def complete_v20_live_state() -> LiveState:
    return LiveState(
        completed_milestones=("V1.5",),
        current_milestone=V20_MILESTONE,
        next_milestone=None,
        next_milestone_objective=None,
        current_objective=V20_OBJECTIVE,
        current_objective_status="COMPLETE",
        immediate_next_objective=None,
    )


def run_tests() -> None:
    print("V0.9 DEV TASK STATE REGRESSION TEST")
    print("=" * 70)

    active = derive_task_state(
        active_live_state()
    )

    assert active.status == "ACTIVE"
    assert active.milestone == V09_MILESTONE
    assert active.objective == "Persist development task state."

    print("TEST 1 DERIVE ACTIVE: PASS")

    handoff = derive_task_state(
        handoff_live_state()
    )

    assert handoff.status == "HANDOFF_READY"
    assert handoff.milestone == V09_MILESTONE
    assert handoff.previous_milestone == V08_MILESTONE

    print("TEST 2 DERIVE HANDOFF_READY: PASS")

    stopped = derive_task_state(
        stopped_live_state()
    )

    assert stopped.status == "NO_NEW_MILESTONE"
    assert stopped.milestone is None
    assert stopped.objective is None
    assert stopped.previous_milestone is None

    print("TEST 3 DERIVE NO_NEW_MILESTONE: PASS")

    initialize = resolve_task_state(
        active_live_state(),
        None,
    )

    assert (
        initialize.decision
        == "INITIALIZE_FROM_LIVE_STATE"
    )
    assert initialize.state == active

    print("TEST 4 INITIALIZE: PASS")

    resume = resolve_task_state(
        active_live_state(),
        active,
    )

    assert resume.decision == "RESUME_PERSISTED"
    assert resume.state == active

    print("TEST 5 RESUME: PASS")

    persisted_v08 = DevTaskState(
        milestone=V08_MILESTONE,
        objective="Complete milestone progression.",
        status="ACTIVE",
    )

    advance = resolve_task_state(
        handoff_live_state(),
        persisted_v08,
    )

    assert (
        advance.decision
        == "ADVANCE_FROM_LIVE_STATE"
    )
    assert advance.state == handoff

    print("TEST 6 ADVANCE: PASS")

    conflicting = DevTaskState(
        milestone="Developer Console V0.7",
        objective="Unrelated old work.",
        status="ACTIVE",
    )

    conflict = resolve_task_state(
        active_live_state(),
        conflicting,
    )

    assert conflict.decision == "CONFLICT"
    assert conflict.state == conflicting

    print("TEST 7 CONFLICT: PASS")

    persisted_v20_handoff = DevTaskState(
        milestone=V20_MILESTONE,
        objective=V20_OBJECTIVE,
        status="HANDOFF_READY",
        previous_milestone=V15_MILESTONE,
    )

    reconcile = resolve_task_state(
        active_v20_live_state(),
        persisted_v20_handoff,
    )

    assert (
        reconcile.decision
        == "RECONCILE_AFTER_HANDOFF"
    )
    assert reconcile.state.status == "ACTIVE"
    assert reconcile.state.milestone == V20_MILESTONE
    assert reconcile.state.objective == V20_OBJECTIVE
    assert reconcile.state.previous_milestone is None

    reconcile_plan = plan_task_state_transition(
        reconcile
    )

    assert reconcile_plan.action == "PERSIST"

    print("TEST 8 RECONCILE AFTER HANDOFF: PASS")

    wrong_v20_milestone = DevTaskState(
        milestone="Developer Console V1.9",
        objective=V20_OBJECTIVE,
        status="HANDOFF_READY",
        previous_milestone=V15_MILESTONE,
    )

    wrong_milestone_result = resolve_task_state(
        active_v20_live_state(),
        wrong_v20_milestone,
    )

    assert (
        wrong_milestone_result.decision
        == "CONFLICT"
    )

    print("TEST 9 WRONG HANDOFF MILESTONE BLOCKED: PASS")

    wrong_v20_objective = DevTaskState(
        milestone=V20_MILESTONE,
        objective="Different objective.",
        status="HANDOFF_READY",
        previous_milestone=V15_MILESTONE,
    )

    wrong_objective_result = resolve_task_state(
        active_v20_live_state(),
        wrong_v20_objective,
    )

    assert (
        wrong_objective_result.decision
        == "CONFLICT"
    )

    print("TEST 10 WRONG HANDOFF OBJECTIVE BLOCKED: PASS")

    generic_conflict_plan = plan_task_state_transition(
        conflict
    )

    assert generic_conflict_plan.action == "BLOCK"

    print("TEST 11 GENERIC CONFLICT STILL BLOCKS: PASS")

    persisted_v20_active = DevTaskState(
        milestone=V20_MILESTONE,
        objective=V20_OBJECTIVE,
        status="ACTIVE",
    )

    completion = resolve_task_state(
        complete_v20_live_state(),
        persisted_v20_active,
    )

    assert (
        completion.decision
        == "COMPLETE_TO_NO_NEW_MILESTONE"
    )

    assert completion.state.status == "NO_NEW_MILESTONE"
    assert completion.state.milestone is None
    assert completion.state.objective is None
    assert completion.state.previous_milestone is None

    completion_plan = plan_task_state_transition(
        completion
    )

    assert completion_plan.action == "PERSIST"

    print("TEST 12 COMPLETE TO NO_NEW_MILESTONE: PASS")

    wrong_completion_milestone = DevTaskState(
        milestone="Developer Console V1.9",
        objective=V20_OBJECTIVE,
        status="ACTIVE",
    )

    wrong_completion_result = resolve_task_state(
        complete_v20_live_state(),
        wrong_completion_milestone,
    )

    assert (
        wrong_completion_result.decision
        == "CONFLICT"
    )

    print("TEST 13 WRONG COMPLETION MILESTONE BLOCKED: PASS")

    wrong_completion_objective = DevTaskState(
        milestone=V20_MILESTONE,
        objective="Different objective.",
        status="ACTIVE",
    )

    wrong_completion_objective_result = resolve_task_state(
        complete_v20_live_state(),
        wrong_completion_objective,
    )

    assert (
        wrong_completion_objective_result.decision
        == "CONFLICT"
    )

    print("TEST 14 WRONG COMPLETION OBJECTIVE BLOCKED: PASS")

    payload = task_state_to_dict(
        handoff
    )

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
    )

    decoded = json.loads(
        encoded
    )

    round_trip = task_state_from_dict(
        decoded
    )

    assert round_trip == handoff

    print("TEST 15 SCHEMA ROUND TRIP: PASS")

    print()
    print("V0.9 DEV TASK STATE REGRESSION: PASS")


if __name__ == "__main__":
    run_tests()
