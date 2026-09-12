from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.autonomous_task_planning import (
    AutonomousTaskPlan,
    plan_autonomous_task,
)
from app.dev_task_state import DevTaskState
from app.git_workspace_status import (
    GitWorkspaceStatus,
    inspect_git_workspace_status,
)
from app.multi_repo_coordination import (
    MultiRepoCoordinationPlan,
    coordinate_multi_repo_task,
)
from app.roadmap_store import load_project_roadmap
from app.workspace_registry import get_workspace_profile


ProductionAutonomyDecision = Literal[
    "PROCEED",
    "NO_TASK",
    "BLOCKED",
]


@dataclass(frozen=True)
class ProductionAutonomyGateResult:
    control_workspace_name: str
    target_workspace_name: str
    decision: ProductionAutonomyDecision
    task_plan: AutonomousTaskPlan | None
    coordination_plan: MultiRepoCoordinationPlan | None
    reason: str


def _result(
    *,
    control_workspace_name: str,
    target_workspace_name: str,
    decision: ProductionAutonomyDecision,
    task_plan: AutonomousTaskPlan | None,
    coordination_plan: MultiRepoCoordinationPlan | None,
    reason: str,
) -> ProductionAutonomyGateResult:
    return ProductionAutonomyGateResult(
        control_workspace_name=control_workspace_name,
        target_workspace_name=target_workspace_name,
        decision=decision,
        task_plan=task_plan,
        coordination_plan=coordination_plan,
        reason=reason,
    )


def evaluate_production_autonomy(
    *,
    control_workspace_name: str,
    target_workspace_name: str,
    task_state: DevTaskState,
) -> ProductionAutonomyGateResult:
    if (
        not isinstance(control_workspace_name, str)
        or not control_workspace_name.strip()
    ):
        raise ValueError(
            "control_workspace_name must be a non-empty string."
        )

    if (
        not isinstance(target_workspace_name, str)
        or not target_workspace_name.strip()
    ):
        raise ValueError(
            "target_workspace_name must be a non-empty string."
        )

    if not isinstance(task_state, DevTaskState):
        raise ValueError("task_state must be a DevTaskState.")

    try:
        control_workspace = get_workspace_profile(
            control_workspace_name
        )
    except RuntimeError:
        return _result(
            control_workspace_name=control_workspace_name,
            target_workspace_name=target_workspace_name,
            decision="BLOCKED",
            task_plan=None,
            coordination_plan=None,
            reason="Canonical control workspace lookup failed.",
        )

    canonical_control_name = control_workspace.name

    if (
        control_workspace.access_mode != "HUMAN_APPROVED_PATCH_ONLY"
        or control_workspace.write_workflow_verified is not True
    ):
        return _result(
            control_workspace_name=canonical_control_name,
            target_workspace_name=target_workspace_name,
            decision="BLOCKED",
            task_plan=None,
            coordination_plan=None,
            reason="Canonical control workspace is not verified for human-approved patches.",
        )

    try:
        target_workspace = get_workspace_profile(
            target_workspace_name
        )
    except RuntimeError:
        return _result(
            control_workspace_name=canonical_control_name,
            target_workspace_name=target_workspace_name,
            decision="BLOCKED",
            task_plan=None,
            coordination_plan=None,
            reason="Canonical target workspace lookup failed.",
        )

    canonical_target_name = target_workspace.name

    try:
        roadmap = load_project_roadmap(canonical_target_name)
    except RuntimeError:
        return _result(
            control_workspace_name=canonical_control_name,
            target_workspace_name=canonical_target_name,
            decision="BLOCKED",
            task_plan=None,
            coordination_plan=None,
            reason="Canonical project roadmap loading failed.",
        )

    task_plan = plan_autonomous_task(
        workspace_name=canonical_target_name,
        roadmap=roadmap,
        task_state=task_state,
    )

    if task_plan.decision == "BLOCKED":
        return _result(
            control_workspace_name=canonical_control_name,
            target_workspace_name=canonical_target_name,
            decision="BLOCKED",
            task_plan=task_plan,
            coordination_plan=None,
            reason="Canonical autonomous task planning blocked progression.",
        )

    if task_plan.decision == "NO_TASK":
        return _result(
            control_workspace_name=canonical_control_name,
            target_workspace_name=canonical_target_name,
            decision="NO_TASK",
            task_plan=task_plan,
            coordination_plan=None,
            reason="Canonical autonomous task planning reports no task.",
        )

    if task_plan.decision != "PLAN":
        return _result(
            control_workspace_name=canonical_control_name,
            target_workspace_name=canonical_target_name,
            decision="BLOCKED",
            task_plan=task_plan,
            coordination_plan=None,
            reason="Canonical autonomous task planning returned an unsupported decision.",
        )

    try:
        git_status: GitWorkspaceStatus = inspect_git_workspace_status(
            canonical_target_name
        )
    except RuntimeError:
        return _result(
            control_workspace_name=canonical_control_name,
            target_workspace_name=canonical_target_name,
            decision="BLOCKED",
            task_plan=task_plan,
            coordination_plan=None,
            reason="Read-only target Git inspection failed.",
        )

    coordination_plan = coordinate_multi_repo_task(
        control_workspace_name=canonical_control_name,
        target_workspace_name=canonical_target_name,
        task_plan=task_plan,
        target_git_status=git_status,
    )

    if coordination_plan.decision == "BLOCKED":
        return _result(
            control_workspace_name=canonical_control_name,
            target_workspace_name=canonical_target_name,
            decision="BLOCKED",
            task_plan=task_plan,
            coordination_plan=coordination_plan,
            reason="Canonical multi-repository coordination blocked progression.",
        )

    if coordination_plan.decision == "NO_TARGET":
        return _result(
            control_workspace_name=canonical_control_name,
            target_workspace_name=canonical_target_name,
            decision="NO_TASK",
            task_plan=task_plan,
            coordination_plan=coordination_plan,
            reason="Canonical multi-repository coordination reports no target.",
        )

    if coordination_plan.decision == "COORDINATE":
        return _result(
            control_workspace_name=canonical_control_name,
            target_workspace_name=canonical_target_name,
            decision="PROCEED",
            task_plan=task_plan,
            coordination_plan=coordination_plan,
            reason=(
                "Canonical task planning, target Git inspection, and "
                "multi-repository coordination permit the bounded build cycle."
            ),
        )

    return _result(
        control_workspace_name=canonical_control_name,
        target_workspace_name=canonical_target_name,
        decision="BLOCKED",
        task_plan=task_plan,
        coordination_plan=coordination_plan,
        reason="Canonical multi-repository coordination returned an unsupported decision.",
    )