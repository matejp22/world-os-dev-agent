from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real

from app.master_roadmap_types import MasterRoadmap, MasterRoadmapNode


@dataclass(frozen=True)
class MasterRoadmapProgress:
    master_id: str
    completion_percent: float
    remaining_percent: float
    completed_weight: float
    total_weight: float
    completed_projects: int
    total_projects: int
    current_project_ids: tuple[str, ...]


def _validate_project(
    node: MasterRoadmapNode,
    project_ids: set[str],
) -> None:
    if node.project_id is None:
        raise RuntimeError(
            f"PROJECT node must have a project_id: {node.node_id}"
        )

    if node.project_id in project_ids:
        raise RuntimeError(
            f"Duplicate project_id: {node.project_id}"
        )

    project_ids.add(node.project_id)

    if (
        isinstance(node.weight, bool)
        or not isinstance(node.weight, Real)
        or not math.isfinite(node.weight)
        or node.weight <= 0
    ):
        raise RuntimeError(
            f"Project weight must be a finite positive number: "
            f"{node.project_id}"
        )


def _validate_completion(
    project_id: str,
    completion: object,
) -> float:
    if (
        isinstance(completion, bool)
        or not isinstance(completion, Real)
        or not math.isfinite(completion)
        or not 0.0 <= completion <= 100.0
    ):
        raise RuntimeError(
            f"Project completion must be finite and within 0.0 through "
            f"100.0: {project_id}"
        )

    return float(completion)


def calculate_master_progress(
    roadmap: MasterRoadmap,
    project_completion: dict[str, float],
) -> MasterRoadmapProgress:
    if not isinstance(project_completion, dict):
        raise RuntimeError("project_completion must be a dictionary.")

    projects: list[MasterRoadmapNode] = []
    project_ids: set[str] = set()

    for node in roadmap.nodes:
        if node.kind == "PROJECT":
            _validate_project(node, project_ids)
            projects.append(node)

    if not projects:
        raise RuntimeError(
            "Master roadmap must contain at least one PROJECT node."
        )

    expected_ids = set(project_ids)
    supplied_ids = set(project_completion)

    missing_ids = expected_ids - supplied_ids
    unexpected_ids = supplied_ids - expected_ids

    if missing_ids or unexpected_ids:
        raise RuntimeError(
            "project_completion IDs must match project IDs exactly. "
            f"Missing: {sorted(missing_ids)}; "
            f"unexpected: {sorted(unexpected_ids)}."
        )

    validated_completion = {
        project_id: _validate_completion(
            project_id,
            project_completion[project_id],
        )
        for project_id in expected_ids
    }

    total_weight = sum(
        float(project.weight)
        for project in projects
    )

    completed_weight = sum(
        float(project.weight)
        * validated_completion[project.project_id]
        / 100.0
        for project in projects
    )

    completion_percent = (
        completed_weight / total_weight
    ) * 100.0

    return MasterRoadmapProgress(
        master_id=roadmap.master_id,
        completion_percent=completion_percent,
        remaining_percent=100.0 - completion_percent,
        completed_weight=completed_weight,
        total_weight=total_weight,
        completed_projects=sum(
            validated_completion[project.project_id] == 100.0
            for project in projects
        ),
        total_projects=len(projects),
        current_project_ids=tuple(
            project.project_id
            for project in projects
            if (
                0.0
                < validated_completion[project.project_id]
                < 100.0
            )
        ),
    )