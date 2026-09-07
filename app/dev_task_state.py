from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Literal

from app.live_state import (
    LiveState,
    has_active_milestone,
    planning_milestone,
    load_live_state,
    planning_objective,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEV_TASK_STATE_PATH = (
    PROJECT_ROOT
    / "context"
    / "DEV_TASK_STATE.json"
)

TaskStatus = Literal[
    "ACTIVE",
    "HANDOFF_READY",
    "NO_NEW_MILESTONE",
]


@dataclass(frozen=True)
class DevTaskState:
    milestone: str | None
    objective: str | None
    status: TaskStatus
    previous_milestone: str | None = None


def _require_nonempty_string(
    value: str | None,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} must be a string."
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty."
        )

    return normalized


def validate_task_state(
    state: DevTaskState,
) -> None:
    if not isinstance(state.status, str):
        raise ValueError(
            "status must be a string."
        )

    if state.status == "ACTIVE":
        _require_nonempty_string(
            state.milestone,
            "milestone",
        )

        _require_nonempty_string(
            state.objective,
            "objective",
        )

        if (
            state.previous_milestone is not None
            and not state.previous_milestone.strip()
        ):
            raise ValueError(
                "previous_milestone must not be whitespace-only."
            )

    elif state.status == "HANDOFF_READY":
        milestone = _require_nonempty_string(
            state.milestone,
            "milestone",
        )

        _require_nonempty_string(
            state.objective,
            "objective",
        )

        previous_milestone = _require_nonempty_string(
            state.previous_milestone,
            "previous_milestone",
        )

        if (
            milestone.casefold()
            == previous_milestone.casefold()
        ):
            raise ValueError(
                "HANDOFF_READY milestone must differ "
                "from previous_milestone."
            )

    elif state.status == "NO_NEW_MILESTONE":
        if (
            state.milestone is not None
            or state.objective is not None
            or state.previous_milestone is not None
        ):
            raise ValueError(
                "NO_NEW_MILESTONE cannot contain active work."
            )

    else:
        raise ValueError(
            f"Unsupported task status: {state.status}"
        )


def task_state_to_dict(
    state: DevTaskState,
) -> dict[str, str | None]:
    validate_task_state(
        state
    )

    return asdict(
        state
    )


def task_state_from_dict(
    value: dict[str, object],
) -> DevTaskState:
    required = {
        "milestone",
        "objective",
        "status",
        "previous_milestone",
    }

    if set(value) != required:
        raise ValueError(
            "DEV_TASK_STATE fields do not match schema."
        )

    status = value["status"]

    if not isinstance(status, str):
        raise ValueError(
            "status must be a string."
        )

    milestone = value["milestone"]
    objective = value["objective"]
    previous_milestone = value["previous_milestone"]

    for key, item in (
        ("milestone", milestone),
        ("objective", objective),
        ("previous_milestone", previous_milestone),
    ):
        if (
            item is not None
            and not isinstance(item, str)
        ):
            raise ValueError(
                f"{key} must be string or null."
            )

    state = DevTaskState(
        milestone=milestone,
        objective=objective,
        status=status,
        previous_milestone=previous_milestone,
    )

    validate_task_state(
        state
    )

    return state


def derive_task_state(
    live_state: LiveState,
) -> DevTaskState:
    if has_active_milestone(
        live_state
    ):
        objective = planning_objective(
            live_state
        )

        if objective is None:
            raise RuntimeError(
                "Active milestone has no planning objective."
            )

        milestone = _require_nonempty_string(
            live_state.current_milestone,
            "current_milestone",
        )

        state = DevTaskState(
            milestone=milestone,
            objective=objective,
            status="ACTIVE",
            previous_milestone=None,
        )

        validate_task_state(
            state
        )

        return state

    next_plan = planning_milestone(
        live_state
    )

    if next_plan is not None:
        milestone, objective = next_plan

        previous_milestone = _require_nonempty_string(
            live_state.current_milestone,
            "current_milestone",
        )

        state = DevTaskState(
            milestone=milestone,
            objective=objective,
            status="HANDOFF_READY",
            previous_milestone=previous_milestone,
        )

        validate_task_state(
            state
        )

        return state

    state = DevTaskState(
        milestone=None,
        objective=None,
        status="NO_NEW_MILESTONE",
        previous_milestone=None,
    )

    validate_task_state(
        state
    )

    return state


ResumeDecision = Literal[
    "INITIALIZE_FROM_LIVE_STATE",
    "RESUME_PERSISTED",
    "ADVANCE_FROM_LIVE_STATE",
    "RECONCILE_AFTER_HANDOFF",
    "COMPLETE_TO_NO_NEW_MILESTONE",
    "CONFLICT",
]


@dataclass(frozen=True)
class ResumeResolution:
    decision: ResumeDecision
    state: DevTaskState


TransitionAction = Literal[
    "PERSIST",
    "NO_WRITE",
    "BLOCK",
]


@dataclass(frozen=True)
class TaskStateTransitionPlan:
    action: TransitionAction
    decision: ResumeDecision
    state: DevTaskState
    reason: str


@dataclass(frozen=True)
class TaskStateTransitionExecutionResult:
    action: TransitionAction
    decision: ResumeDecision
    state: DevTaskState
    persisted: bool
    reason: str


def plan_task_state_transition(
    resolution: ResumeResolution,
) -> TaskStateTransitionPlan:
    validate_task_state(
        resolution.state
    )

    plans: dict[str, tuple[TransitionAction, str]] = {
        "INITIALIZE_FROM_LIVE_STATE": (
            "PERSIST",
            "Persist the resolved task state initialized from LIVE_STATE.",
        ),
        "ADVANCE_FROM_LIVE_STATE": (
            "PERSIST",
            "Persist the resolved task state advanced from LIVE_STATE.",
        ),
        "RECONCILE_AFTER_HANDOFF": (
            "PERSIST",
            "Persist canonical ACTIVE task state after a verified milestone handoff.",
        ),
        "COMPLETE_TO_NO_NEW_MILESTONE": (
            "PERSIST",
            "Persist canonical NO_NEW_MILESTONE after verified milestone completion.",
        ),
        "RESUME_PERSISTED": (
            "NO_WRITE",
            "Keep the already persisted task state unchanged.",
        ),
        "CONFLICT": (
            "BLOCK",
            "Block persistence because task state resolution is in conflict.",
        ),
    }

    try:
        action, reason = plans[resolution.decision]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported resume decision: {resolution.decision}"
        ) from exc

    return TaskStateTransitionPlan(
        action=action,
        decision=resolution.decision,
        state=resolution.state,
        reason=reason,
    )


def execute_task_state_transition(
    plan: TaskStateTransitionPlan,
) -> TaskStateTransitionExecutionResult:
    validate_task_state(
        plan.state
    )

    if plan.action == "PERSIST":
        save_task_state(
            plan.state
        )

        return TaskStateTransitionExecutionResult(
            action=plan.action,
            decision=plan.decision,
            state=plan.state,
            persisted=True,
            reason=plan.reason,
        )

    if plan.action == "NO_WRITE":
        return TaskStateTransitionExecutionResult(
            action=plan.action,
            decision=plan.decision,
            state=plan.state,
            persisted=False,
            reason=plan.reason,
        )

    if plan.action == "BLOCK":
        raise RuntimeError(
            f"Task-state transition blocked: {plan.reason}"
        )

    raise RuntimeError(
        f"Unsupported task-state transition action: {plan.action}"
    )


def resolve_task_state(
    live_state: LiveState,
    persisted_state: DevTaskState | None,
) -> ResumeResolution:
    derived = derive_task_state(
        live_state
    )

    if persisted_state is None:
        return ResumeResolution(
            decision="INITIALIZE_FROM_LIVE_STATE",
            state=derived,
        )

    validate_task_state(
        persisted_state
    )

    if persisted_state == derived:
        return ResumeResolution(
            decision="RESUME_PERSISTED",
            state=persisted_state,
        )

    if (
        derived.status == "HANDOFF_READY"
        and persisted_state.milestone is not None
        and derived.previous_milestone is not None
        and persisted_state.milestone.strip().casefold()
        == derived.previous_milestone.strip().casefold()
    ):
        return ResumeResolution(
            decision="ADVANCE_FROM_LIVE_STATE",
            state=derived,
        )

    if (
        derived.status == "ACTIVE"
        and persisted_state.status == "HANDOFF_READY"
        and derived.milestone is not None
        and persisted_state.milestone is not None
        and derived.objective is not None
        and persisted_state.objective is not None
        and persisted_state.previous_milestone is not None
        and derived.milestone.strip().casefold()
        == persisted_state.milestone.strip().casefold()
        and derived.objective.strip()
        == persisted_state.objective.strip()
    ):
        return ResumeResolution(
            decision="RECONCILE_AFTER_HANDOFF",
            state=derived,
        )

    if (
        derived.status == "NO_NEW_MILESTONE"
        and persisted_state.status == "ACTIVE"
        and live_state.current_objective_status == "COMPLETE"
        and live_state.next_milestone is None
        and live_state.next_milestone_objective is None
        and live_state.current_milestone is not None
        and live_state.current_objective is not None
        and persisted_state.milestone is not None
        and persisted_state.objective is not None
        and persisted_state.milestone.strip().casefold()
        == live_state.current_milestone.strip().casefold()
        and persisted_state.objective.strip()
        == live_state.current_objective.strip()
    ):
        return ResumeResolution(
            decision="COMPLETE_TO_NO_NEW_MILESTONE",
            state=derived,
        )

    return ResumeResolution(
        decision="CONFLICT",
        state=persisted_state,
    )


def load_task_state(
    path: Path = DEV_TASK_STATE_PATH,
) -> DevTaskState | None:
    if not path.exists():
        return None

    value = json.loads(
        path.read_text(
            encoding="utf-8-sig",
        )
    )

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            "DEV_TASK_STATE JSON must contain an object."
        )

    return task_state_from_dict(
        value
    )


def load_resolved_task_state(
) -> ResumeResolution:
    live_state = load_live_state()
    persisted_state = load_task_state()

    return resolve_task_state(
        live_state,
        persisted_state,
    )


def serialize_task_state(
    state: DevTaskState,
) -> str:
    return (
        json.dumps(
            task_state_to_dict(
                state
            ),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    )


def save_task_state(
    state: DevTaskState,
) -> None:
    validate_task_state(
        state
    )

    target = DEV_TASK_STATE_PATH.resolve()

    expected_target = (
        PROJECT_ROOT
        / "context"
        / "DEV_TASK_STATE.json"
    ).resolve()

    if target != expected_target:
        raise RuntimeError(
            "DEV_TASK_STATE write target is not allowed."
        )

    if not target.parent.exists():
        raise RuntimeError(
            "DEV_TASK_STATE parent directory does not exist."
        )

    if not target.parent.is_dir():
        raise RuntimeError(
            "DEV_TASK_STATE parent is not a directory."
        )

    serialized = serialize_task_state(
        state
    )

    temp_path = target.with_suffix(
        target.suffix + ".tmp"
    )

    if temp_path.exists():
        raise RuntimeError(
            "DEV_TASK_STATE temporary file already exists."
        )

    try:
        with temp_path.open("x", encoding="utf-8", newline="") as handle:
            handle.write(
                serialized
            )
            handle.flush()
            os.fsync(
                handle.fileno()
            )

        os.replace(
            temp_path,
            target,
        )

    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass