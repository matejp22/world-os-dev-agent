from __future__ import annotations

from dataclasses import dataclass

from app.roadmap_types import ProjectRoadmap, RoadmapNode


@dataclass(frozen=True)
class RoadmapProgress:
    project_id: str
    completion_percent: float
    remaining_percent: float
    completed_weight: float
    total_weight: float
    completed_milestones: int
    total_milestones: int
    current_milestone_id: str | None


def _validate_milestone(milestone: RoadmapNode) -> None:
    if milestone.kind != "MILESTONE":
        raise RuntimeError(
            "Progress calculation accepts milestone nodes only."
        )

    if milestone.weight <= 0:
        raise RuntimeError(
            f"Milestone weight must be strictly positive: "
            f"{milestone.node_id}"
        )

    if (
        milestone.status == "COMPLETED"
        and milestone.verification_status != "PASSED"
    ):
        raise RuntimeError(
            f"Completed milestone must have PASSED verification: "
            f"{milestone.node_id}"
        )


def _calculate_progress(
    project_id: str,
    milestones: tuple[RoadmapNode, ...],
) -> RoadmapProgress:
    if not milestones:
        raise RuntimeError(
            "Roadmap must contain at least one milestone."
        )

    for milestone in milestones:
        _validate_milestone(milestone)

    total_weight = sum(
        milestone.weight
        for milestone in milestones
    )

    completed_milestones = tuple(
        milestone
        for milestone in milestones
        if (
            milestone.status == "COMPLETED"
            and milestone.verification_status == "PASSED"
        )
    )

    completed_weight = sum(
        milestone.weight
        for milestone in completed_milestones
    )

    completion_percent = (
        completed_weight / total_weight
    ) * 100

    return RoadmapProgress(
        project_id=project_id,
        completion_percent=completion_percent,
        remaining_percent=100 - completion_percent,
        completed_weight=completed_weight,
        total_weight=total_weight,
        completed_milestones=len(completed_milestones),
        total_milestones=len(milestones),
        current_milestone_id=next(
            (
                milestone.node_id
                for milestone in milestones
                if milestone.status == "IN_PROGRESS"
            ),
            None,
        ),
    )


def calculate_project_progress(
    roadmap: ProjectRoadmap,
) -> RoadmapProgress:
    milestones = tuple(
        node
        for node in roadmap.nodes
        if node.kind == "MILESTONE"
    )

    return _calculate_progress(
        project_id=roadmap.project_id,
        milestones=milestones,
    )


def calculate_group_progress(
    roadmap: ProjectRoadmap,
    group_id: str,
) -> RoadmapProgress:
    groups = tuple(
        node
        for node in roadmap.nodes
        if node.kind == "GROUP"
        and node.node_id == group_id
    )

    if not groups:
        raise RuntimeError(
            f"Group not found: {group_id}"
        )

    milestones = tuple(
        node
        for node in roadmap.nodes
        if node.kind == "MILESTONE"
        and node.parent_id == group_id
    )

    if not milestones:
        raise RuntimeError(
            f"Group has no direct milestone children: {group_id}"
        )

    return _calculate_progress(
        project_id=group_id,
        milestones=milestones,
    )