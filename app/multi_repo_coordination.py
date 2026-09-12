from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.autonomous_task_planning import AutonomousTaskPlan
from app.git_workspace_status import GitWorkspaceStatus
from app.workspace_registry import get_workspace_profile


MultiRepoCoordinationDecision = Literal[
    "COORDINATE",
    "NO_TARGET",
    "BLOCKED",
]


@dataclass(frozen=True)
class MultiRepoCoordinationPlan:
    control_workspace_name: str
    target_workspace_name: str | None
    decision: MultiRepoCoordinationDecision
    roadmap_milestone_id: str | None
    task_milestone: str | None
    persistent_objective: str | None
    target_branch: str | None
    target_dirty: bool
    reason: str


def _blocked(
    *,
    control_workspace_name: str,
    target_workspace_name: str | None,
    roadmap_milestone_id: str | None,
    task_milestone: str | None,
    persistent_objective: str | None,
    target_branch: str | None,
    target_dirty: bool,
    reason: str,
) -> MultiRepoCoordinationPlan:
    return MultiRepoCoordinationPlan(
        control_workspace_name=control_workspace_name,
        target_workspace_name=target_workspace_name,
        decision="BLOCKED",
        roadmap_milestone_id=roadmap_milestone_id,
        task_milestone=task_milestone,
        persistent_objective=persistent_objective,
        target_branch=target_branch,
        target_dirty=target_dirty,
        reason=reason,
    )


def coordinate_multi_repo_task(
    *,
    control_workspace_name: str,
    target_workspace_name: str | None,
    task_plan: AutonomousTaskPlan,
    target_git_status: GitWorkspaceStatus | None,
) -> MultiRepoCoordinationPlan:
    if (
        not isinstance(control_workspace_name, str)
        or not control_workspace_name.strip()
    ):
        raise ValueError(
            "control_workspace_name must be a non-empty string."
        )

    if (
        target_workspace_name is not None
        and (
            not isinstance(target_workspace_name, str)
            or not target_workspace_name.strip()
        )
    ):
        raise ValueError(
            "target_workspace_name must be None or a non-empty string."
        )

    if not isinstance(task_plan, AutonomousTaskPlan):
        raise ValueError(
            "task_plan must be an AutonomousTaskPlan."
        )

    if (
        target_git_status is not None
        and not isinstance(target_git_status, GitWorkspaceStatus)
    ):
        raise ValueError(
            "target_git_status must be None or a GitWorkspaceStatus."
        )

    original_control_name = control_workspace_name
    original_target_name = target_workspace_name

    try:
        control_workspace = get_workspace_profile(
            original_control_name
        )
    except RuntimeError:
        return _blocked(
            control_workspace_name=original_control_name,
            target_workspace_name=original_target_name,
            roadmap_milestone_id=task_plan.roadmap_milestone_id,
            task_milestone=task_plan.task_milestone,
            persistent_objective=task_plan.persistent_objective,
            target_branch=None,
            target_dirty=False,
            reason="Canonical control workspace lookup failed.",
        )

    canonical_control_name = control_workspace.name

    if (
        control_workspace.access_mode != "HUMAN_APPROVED_PATCH_ONLY"
        or control_workspace.write_workflow_verified is not True
    ):
        return _blocked(
            control_workspace_name=canonical_control_name,
            target_workspace_name=original_target_name,
            roadmap_milestone_id=task_plan.roadmap_milestone_id,
            task_milestone=task_plan.task_milestone,
            persistent_objective=task_plan.persistent_objective,
            target_branch=None,
            target_dirty=False,
            reason="Canonical control workspace is not verified for human-approved patches.",
        )

    if task_plan.decision == "BLOCKED":
        return _blocked(
            control_workspace_name=canonical_control_name,
            target_workspace_name=original_target_name,
            roadmap_milestone_id=task_plan.roadmap_milestone_id,
            task_milestone=task_plan.task_milestone,
            persistent_objective=task_plan.persistent_objective,
            target_branch=None,
            target_dirty=False,
            reason="Canonical autonomous task plan is blocked.",
        )

    if task_plan.decision == "NO_TASK":
        if (
            original_target_name is not None
            or target_git_status is not None
        ):
            return _blocked(
                control_workspace_name=canonical_control_name,
                target_workspace_name=original_target_name,
                roadmap_milestone_id=task_plan.roadmap_milestone_id,
                task_milestone=task_plan.task_milestone,
                persistent_objective=task_plan.persistent_objective,
                target_branch=None,
                target_dirty=False,
                reason="A no-task plan must not include a target workspace or Git status.",
            )

        return MultiRepoCoordinationPlan(
            control_workspace_name=canonical_control_name,
            target_workspace_name=None,
            decision="NO_TARGET",
            roadmap_milestone_id=None,
            task_milestone=None,
            persistent_objective=None,
            target_branch=None,
            target_dirty=False,
            reason=(
                "Canonical autonomous task plan contains no task to coordinate."
            ),
        )

    if task_plan.decision != "PLAN":
        return _blocked(
            control_workspace_name=canonical_control_name,
            target_workspace_name=original_target_name,
            roadmap_milestone_id=task_plan.roadmap_milestone_id,
            task_milestone=task_plan.task_milestone,
            persistent_objective=task_plan.persistent_objective,
            target_branch=None,
            target_dirty=False,
            reason="Canonical autonomous task plan has an unsupported decision.",
        )

    if (
        not isinstance(task_plan.roadmap_milestone_id, str)
        or not task_plan.roadmap_milestone_id.strip()
        or not isinstance(task_plan.task_milestone, str)
        or not task_plan.task_milestone.strip()
        or not isinstance(task_plan.persistent_objective, str)
        or not task_plan.persistent_objective.strip()
    ):
        return _blocked(
            control_workspace_name=canonical_control_name,
            target_workspace_name=original_target_name,
            roadmap_milestone_id=task_plan.roadmap_milestone_id,
            task_milestone=task_plan.task_milestone,
            persistent_objective=task_plan.persistent_objective,
            target_branch=None,
            target_dirty=False,
            reason="Canonical autonomous task plan is missing required PLAN fields.",
        )

    if original_target_name is None:
        return _blocked(
            control_workspace_name=canonical_control_name,
            target_workspace_name=None,
            roadmap_milestone_id=task_plan.roadmap_milestone_id,
            task_milestone=task_plan.task_milestone,
            persistent_objective=task_plan.persistent_objective,
            target_branch=None,
            target_dirty=False,
            reason="A PLAN decision requires a target workspace.",
        )

    try:
        target_workspace = get_workspace_profile(
            original_target_name
        )
    except RuntimeError:
        return _blocked(
            control_workspace_name=canonical_control_name,
            target_workspace_name=original_target_name,
            roadmap_milestone_id=task_plan.roadmap_milestone_id,
            task_milestone=task_plan.task_milestone,
            persistent_objective=task_plan.persistent_objective,
            target_branch=None,
            target_dirty=False,
            reason="Canonical target workspace lookup failed.",
        )

    canonical_target_name = target_workspace.name

    if task_plan.workspace_name != canonical_target_name:
        return _blocked(
            control_workspace_name=canonical_control_name,
            target_workspace_name=canonical_target_name,
            roadmap_milestone_id=task_plan.roadmap_milestone_id,
            task_milestone=task_plan.task_milestone,
            persistent_objective=task_plan.persistent_objective,
            target_branch=None,
            target_dirty=False,
            reason="Autonomous task plan workspace does not match canonical target workspace.",
        )

    if target_workspace.access_mode == "READ_ONLY":
        return _blocked(
            control_workspace_name=canonical_control_name,
            target_workspace_name=canonical_target_name,
            roadmap_milestone_id=task_plan.roadmap_milestone_id,
            task_milestone=task_plan.task_milestone,
            persistent_objective=task_plan.persistent_objective,
            target_branch=None,
            target_dirty=False,
            reason="Target workspace is read-only.",
        )

    if (
        target_workspace.access_mode != "HUMAN_APPROVED_PATCH_ONLY"
        or target_workspace.write_workflow_verified is not True
    ):
        return _blocked(
            control_workspace_name=canonical_control_name,
            target_workspace_name=canonical_target_name,
            roadmap_milestone_id=task_plan.roadmap_milestone_id,
            task_milestone=task_plan.task_milestone,
            persistent_objective=task_plan.persistent_objective,
            target_branch=None,
            target_dirty=False,
            reason="Target workspace is not verified for human-approved patches.",
        )

    if target_git_status is None:
        return _blocked(
            control_workspace_name=canonical_control_name,
            target_workspace_name=canonical_target_name,
            roadmap_milestone_id=task_plan.roadmap_milestone_id,
            task_milestone=task_plan.task_milestone,
            persistent_objective=task_plan.persistent_objective,
            target_branch=None,
            target_dirty=False,
            reason="Canonical target Git status is required.",
        )

    git_validated = (
        target_git_status.inspected is True
        and target_git_status.workspace_name == canonical_target_name
        and target_git_status.workspace_path
        == str(target_workspace.path)
        and isinstance(target_git_status.branch, str)
        and bool(target_git_status.branch.strip())
    )

    if not git_validated:
        return _blocked(
            control_workspace_name=canonical_control_name,
            target_workspace_name=canonical_target_name,
            roadmap_milestone_id=task_plan.roadmap_milestone_id,
            task_milestone=task_plan.task_milestone,
            persistent_objective=task_plan.persistent_objective,
            target_branch=None,
            target_dirty=False,
            reason="Target Git status did not pass canonical validation.",
        )

    target_branch = target_git_status.branch
    target_dirty = not target_git_status.clean

    if target_git_status.conflicted:
        return _blocked(
            control_workspace_name=canonical_control_name,
            target_workspace_name=canonical_target_name,
            roadmap_milestone_id=task_plan.roadmap_milestone_id,
            task_milestone=task_plan.task_milestone,
            persistent_objective=task_plan.persistent_objective,
            target_branch=target_branch,
            target_dirty=target_dirty,
            reason="Target Git status contains conflicted files.",
        )

    return MultiRepoCoordinationPlan(
        control_workspace_name=canonical_control_name,
        target_workspace_name=canonical_target_name,
        decision="COORDINATE",
        roadmap_milestone_id=task_plan.roadmap_milestone_id,
        task_milestone=task_plan.task_milestone,
        persistent_objective=task_plan.persistent_objective,
        target_branch=target_branch,
        target_dirty=target_dirty,
        reason=(
            "Canonical control workspace, target workspace, autonomous task plan, "
            "and inspected Git boundaries are satisfied."
        ),
    )