from __future__ import annotations

from pathlib import Path

from app.master_roadmap_types import MasterRoadmap
from app.roadmap_progress import calculate_project_progress
from app.roadmap_store import (
    PROJECT_ROADMAP_DIR,
    load_project_roadmap,
)


def _require_non_empty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{label} must be a non-empty string.")
    return value


def resolve_project_completion(
    master_roadmap: MasterRoadmap,
    project_workspaces: dict[str, str],
    roadmap_dir: Path = PROJECT_ROADMAP_DIR,
) -> dict[str, float]:
    if not isinstance(project_workspaces, dict):
        raise RuntimeError("project_workspaces must be a dictionary.")

    project_ids: list[str] = []
    seen_project_ids: set[str] = set()

    for node in master_roadmap.nodes:
        if node.kind != "PROJECT":
            continue

        project_id = _require_non_empty_string(
            node.project_id,
            f"PROJECT node {node.node_id} project_id",
        )

        if project_id in seen_project_ids:
            raise RuntimeError(f"Duplicate project_id: {project_id}")

        seen_project_ids.add(project_id)
        project_ids.append(project_id)

    if not project_ids:
        raise RuntimeError(
            "Master roadmap must contain at least one PROJECT node."
        )

    for project_id, workspace_name in project_workspaces.items():
        validated_project_id = _require_non_empty_string(
            project_id,
            "project_workspaces project_id",
        )
        _require_non_empty_string(
            workspace_name,
            f"Workspace for project {validated_project_id}",
        )

        if validated_project_id not in seen_project_ids:
            raise RuntimeError(
                "project_workspaces contains an unknown project_id: "
                f"{validated_project_id}"
            )

    resolved: dict[str, float] = {}

    for project_id in project_ids:
        if project_id not in project_workspaces:
            resolved[project_id] = 0.0
            continue

        workspace_name = project_workspaces[project_id]
        roadmap = load_project_roadmap(workspace_name, roadmap_dir)

        if roadmap.project_id != project_id:
            raise RuntimeError(
                "Loaded project roadmap project_id does not match mapped "
                f"Master project_id: {project_id}"
            )

        progress = calculate_project_progress(roadmap)
        resolved[project_id] = float(progress.completion_percent)

    return resolved