from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.master_project_sync import build_master_project_sync_snapshot
from app.roadmap_store import PROJECT_ROADMAP_DIR


@dataclass(frozen=True)
class GlobalProjectProgress:
    project_id: str
    completion_percent: float
    is_current: bool


@dataclass(frozen=True)
class GlobalProgressSnapshot:
    master_id: str
    completion_percent: float
    remaining_percent: float
    completed_weight: float
    total_weight: float
    completed_projects: int
    total_projects: int
    current_project_ids: tuple[str, ...]
    projects: tuple[GlobalProjectProgress, ...]


def build_global_progress_snapshot(
    *,
    master_roadmap_path: Path,
    project_workspaces: dict[str, str],
    roadmap_dir: Path = PROJECT_ROADMAP_DIR,
) -> GlobalProgressSnapshot:
    if not isinstance(master_roadmap_path, Path):
        raise RuntimeError("Master roadmap path must be a Path.")

    sync_snapshot = build_master_project_sync_snapshot(
        master_roadmap_path=master_roadmap_path,
        project_workspaces=project_workspaces,
        roadmap_dir=roadmap_dir,
    )

    progress = sync_snapshot.progress

    if sync_snapshot.master_id != progress.master_id:
        raise RuntimeError(
            "Sync snapshot master_id does not match progress master_id."
        )

    projects = tuple(
        GlobalProjectProgress(
            project_id=project_id,
            completion_percent=completion_percent,
            is_current=project_id in progress.current_project_ids,
        )
        for project_id, completion_percent in sync_snapshot.project_completion
    )

    if len(projects) != progress.total_projects:
        raise RuntimeError(
            "Global project count does not match total project count."
        )

    current_project_ids = tuple(
        project.project_id
        for project in projects
        if project.is_current
    )

    if current_project_ids != progress.current_project_ids:
        raise RuntimeError(
            "Global current project IDs do not match progress current "
            "project IDs."
        )

    return GlobalProgressSnapshot(
        master_id=sync_snapshot.master_id,
        completion_percent=progress.completion_percent,
        remaining_percent=progress.remaining_percent,
        completed_weight=progress.completed_weight,
        total_weight=progress.total_weight,
        completed_projects=progress.completed_projects,
        total_projects=progress.total_projects,
        current_project_ids=progress.current_project_ids,
        projects=projects,
    )