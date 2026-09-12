from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.dev_task_state import DevTaskState
from app.roadmap_types import ProjectRoadmap, RoadmapNode
from app.workspace_registry import get_workspace_profile


AutonomousTaskPlanningDecision = Literal[
    "PLAN",
    "NO_TASK",
    "BLOCKED",
]


@dataclass(frozen=True)
class AutonomousTaskPlan:
    workspace_name: str
    decision: AutonomousTaskPlanningDecision
    roadmap_milestone_id: str | None
    roadmap_milestone_title: str | None
    task_milestone: str | None
    persistent_objective: str | None
    reason: str


def _blocked(
    workspace_name: str,
    reason: str,
    task_state: DevTaskState,
) -> AutonomousTaskPlan:
    return AutonomousTaskPlan(
        workspace_name=workspace_name,
        decision="BLOCKED",
        roadmap_milestone_id=None,
        roadmap_milestone_title=None,
        task_milestone=task_state.milestone,
        persistent_objective=task_state.objective,
        reason=reason,
    )


def _strictly_complete(node: RoadmapNode) -> bool:
    return (
        node.status == "COMPLETED"
        and node.verification_status == "PASSED"
    )


def plan_autonomous_task(
    *,
    workspace_name: str,
    roadmap: ProjectRoadmap,
    task_state: DevTaskState,
) -> AutonomousTaskPlan:
    if not isinstance(workspace_name, str) or not workspace_name.strip():
        raise ValueError("workspace_name must be a non-empty string.")

    normalized_workspace_name = workspace_name.strip()

    if not isinstance(roadmap, ProjectRoadmap):
        raise ValueError("roadmap must be a ProjectRoadmap.")

    if not isinstance(task_state, DevTaskState):
        raise ValueError("task_state must be a DevTaskState.")

    try:
        workspace = get_workspace_profile(normalized_workspace_name)
    except RuntimeError:
        return _blocked(
            normalized_workspace_name,
            "Canonical workspace lookup failed.",
            task_state,
        )

    if roadmap.workspace_name != workspace.name:
        return _blocked(
            normalized_workspace_name,
            "Roadmap workspace does not match canonical workspace.",
            task_state,
        )

    if roadmap.project_id != workspace.name:
        return _blocked(
            normalized_workspace_name,
            "Roadmap project does not match canonical workspace.",
            task_state,
        )

    if workspace.access_mode == "READ_ONLY":
        return _blocked(
            normalized_workspace_name,
            "Workspace is read-only.",
            task_state,
        )

    if (
        workspace.access_mode != "HUMAN_APPROVED_PATCH_ONLY"
        or workspace.write_workflow_verified is not True
    ):
        return _blocked(
            normalized_workspace_name,
            "Workspace policy does not permit autonomous planning.",
            task_state,
        )

    milestones = tuple(
        node
        for node in roadmap.nodes
        if node.kind == "MILESTONE"
    )

    lookup: dict[str, RoadmapNode] = {}

    for milestone in milestones:
        if milestone.node_id in lookup:
            return _blocked(
                normalized_workspace_name,
                "Roadmap contains a duplicate milestone identifier.",
                task_state,
            )
        lookup[milestone.node_id] = milestone

    for milestone in milestones:
        for dependency_id in milestone.dependencies:
            dependency = lookup.get(dependency_id)
            if dependency is None:
                return _blocked(
                    normalized_workspace_name,
                    "Roadmap contains a missing milestone dependency.",
                    task_state,
                )

    if task_state.status == "NO_NEW_MILESTONE":
        if (
            task_state.milestone is not None
            or task_state.objective is not None
        ):
            return _blocked(
                normalized_workspace_name,
                "NO_NEW_MILESTONE contains active task state.",
                task_state,
            )

        if all(_strictly_complete(node) for node in milestones):
            return AutonomousTaskPlan(
                workspace_name=normalized_workspace_name,
                decision="NO_TASK",
                roadmap_milestone_id=None,
                roadmap_milestone_title=None,
                task_milestone=None,
                persistent_objective=None,
                reason="All roadmap milestones are strictly complete.",
            )

        return _blocked(
            normalized_workspace_name,
            "Task state and roadmap disagree.",
            task_state,
        )

    if task_state.status not in {"ACTIVE", "HANDOFF_READY"}:
        return _blocked(
            normalized_workspace_name,
            "Unsupported task status.",
            task_state,
        )

    if (
        not isinstance(task_state.milestone, str)
        or not task_state.milestone.strip()
    ):
        return _blocked(
            normalized_workspace_name,
            "Active task state has no valid milestone.",
            task_state,
        )

    if (
        not isinstance(task_state.objective, str)
        or not task_state.objective.strip()
    ):
        return _blocked(
            normalized_workspace_name,
            "Active task state has no valid objective.",
            task_state,
        )

    matched = lookup.get(task_state.milestone)

    if matched is None:
        normalized_title = task_state.milestone.strip().casefold()
        title_matches = tuple(
            node
            for node in milestones
            if node.title.strip().casefold() == normalized_title
        )

        if len(title_matches) > 1:
            return _blocked(
                normalized_workspace_name,
                "Task milestone title matches multiple roadmap milestones.",
                task_state,
            )

        if not title_matches:
            return _blocked(
                normalized_workspace_name,
                "Task milestone does not match the roadmap.",
                task_state,
            )

        matched = title_matches[0]

    if _strictly_complete(matched):
        return _blocked(
            normalized_workspace_name,
            "Task milestone is already strictly complete.",
            task_state,
        )

    if (
        matched.status == "COMPLETED"
        and matched.verification_status != "PASSED"
    ):
        return _blocked(
            normalized_workspace_name,
            "Task milestone is completed but not verified.",
            task_state,
        )

    for dependency_id in matched.dependencies:
        dependency = lookup[dependency_id]
        if not _strictly_complete(dependency):
            return _blocked(
                normalized_workspace_name,
                "A task milestone dependency is not strictly complete.",
                task_state,
            )

    return AutonomousTaskPlan(
        workspace_name=normalized_workspace_name,
        decision="PLAN",
        roadmap_milestone_id=matched.node_id,
        roadmap_milestone_title=matched.title,
        task_milestone=task_state.milestone,
        persistent_objective=task_state.objective,
        reason=(
            "Canonical workspace policy, roadmap milestone, strict "
            "dependencies, and resolved task-state boundaries are satisfied."
        ),
    )