from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.master_roadmap_progress import (
    MasterRoadmapProgress,
    calculate_master_progress,
)
from app.master_roadmap_store import load_master_roadmap
from app.project_completion_resolver import resolve_project_completion
from app.roadmap_store import PROJECT_ROADMAP_DIR


@dataclass(frozen=True)
class MasterProjectSyncSnapshot:
    master_id: str
    project_completion: tuple[tuple[str, float], ...]
    progress: MasterRoadmapProgress


def build_master_project_sync_snapshot(
    *,
    master_roadmap_path: Path,
    project_workspaces: dict[str, str],
    roadmap_dir: Path = PROJECT_ROADMAP_DIR,
) -> MasterProjectSyncSnapshot:
    if not isinstance(master_roadmap_path, Path):
        raise RuntimeError("Master roadmap path must be a Path.")

    master_roadmap = load_master_roadmap(master_roadmap_path)

    resolved_completion = resolve_project_completion(
        master_roadmap,
        project_workspaces,
        roadmap_dir,
    )

    progress = calculate_master_progress(
        master_roadmap,
        resolved_completion,
    )

    project_ids = tuple(
        node.project_id
        for node in master_roadmap.nodes
        if node.kind == "PROJECT"
    )

    expected_ids = set(project_ids)
    resolved_ids = set(resolved_completion)

    if resolved_ids != expected_ids:
        raise RuntimeError(
            "Resolved project completion IDs must match master roadmap "
            "project IDs exactly."
        )

    project_completion = tuple(
        (project_id, resolved_completion[project_id])
        for project_id in project_ids
    )

    if progress.master_id != master_roadmap.master_id:
        raise RuntimeError(
            "Calculated progress master_id does not match master roadmap."
        )

    if len(project_completion) != progress.total_projects:
        raise RuntimeError(
            "Project completion count does not match total project count."
        )

    return MasterProjectSyncSnapshot(
        master_id=master_roadmap.master_id,
        project_completion=project_completion,
        progress=progress,
    )