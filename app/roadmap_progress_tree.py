from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from app.global_progress_snapshot import GlobalProgressSnapshot
from app.master_roadmap_store import load_master_roadmap
from app.master_roadmap_types import MasterRoadmap


@dataclass(frozen=True)
class RoadmapTreeProject:
    project_id: str
    node_id: str
    title: str
    completion_percent: float
    weight: float
    is_current: bool
    achievement_status: str


@dataclass(frozen=True)
class RoadmapTreeProgram:
    node_id: str
    title: str
    projects: tuple[RoadmapTreeProject, ...]


@dataclass(frozen=True)
class RoadmapProgressTree:
    master_id: str
    title: str
    completion_percent: float
    programs: tuple[RoadmapTreeProgram, ...]


def _validate_non_empty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{label} must be a non-empty string.")
    return value


def _validate_weight(value: object, project_id: str) -> float:
    if isinstance(value, bool):
        raise RuntimeError(
            f"Project weight must be numeric for project_id: {project_id}"
        )

    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError(
            f"Project weight must be numeric for project_id: {project_id}"
        ) from exc

    if not math.isfinite(parsed) or parsed < 0.0:
        raise RuntimeError(
            "Project weight must be finite and greater than or equal to "
            f"0.0 for project_id: {project_id}"
        )

    return parsed


def _validate_completion(value: object, project_id: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError(
            "Project completion_percent must be numeric for project_id: "
            f"{project_id}"
        ) from exc

    if not math.isfinite(parsed) or not 0.0 <= parsed <= 100.0:
        raise RuntimeError(
            "Project completion_percent must be finite and between 0.0 "
            f"and 100.0 for project_id: {project_id}"
        )

    return parsed


def _achievement_status(completion_percent: float) -> str:
    if completion_percent == 0.0:
        return "NOT_STARTED"
    if completion_percent == 100.0:
        return "ACHIEVED"
    return "IN_PROGRESS"


def build_roadmap_progress_tree(
    *,
    master_roadmap: MasterRoadmap,
    snapshot: GlobalProgressSnapshot,
) -> RoadmapProgressTree:
    if master_roadmap.master_id != snapshot.master_id:
        raise RuntimeError(
            "Master roadmap master_id does not match snapshot master_id."
        )

    program_nodes = []
    program_ids: set[str] = set()

    for node in master_roadmap.nodes:
        if node.kind != "PROGRAM":
            continue

        if node.node_id in program_ids:
            raise RuntimeError(f"Duplicate PROGRAM node_id: {node.node_id}")

        program_ids.add(node.node_id)
        program_nodes.append(node)

    validated_projects = []
    project_ids: set[str] = set()

    for node in master_roadmap.nodes:
        if node.kind != "PROJECT":
            continue

        project_id = _validate_non_empty_string(
            node.project_id,
            f"PROJECT node {node.node_id} project_id",
        )

        if project_id in project_ids:
            raise RuntimeError(f"Duplicate project_id: {project_id}")

        if node.parent_id not in program_ids:
            raise RuntimeError(
                f"PROJECT node {node.node_id} must reference an existing "
                f"PROGRAM parent: {node.parent_id!r}"
            )

        weight = _validate_weight(node.weight, project_id)
        project_ids.add(project_id)
        validated_projects.append((node, project_id, weight))

    snapshot_projects = {}

    for project in snapshot.projects:
        project_id = _validate_non_empty_string(
            project.project_id,
            "Snapshot project_id",
        )

        if project_id in snapshot_projects:
            raise RuntimeError(f"Duplicate snapshot project_id: {project_id}")

        snapshot_projects[project_id] = project

    snapshot_project_ids = set(snapshot_projects)

    if project_ids != snapshot_project_ids:
        raise RuntimeError(
            "Master PROJECT and snapshot project_id sets must match exactly. "
            f"Missing from snapshot: "
            f"{sorted(project_ids - snapshot_project_ids)}; "
            f"Unexpected in snapshot: "
            f"{sorted(snapshot_project_ids - project_ids)}."
        )

    validated_snapshot_projects = {}

    for project_id, project in snapshot_projects.items():
        completion_percent = _validate_completion(
            project.completion_percent,
            project_id,
        )
        validated_snapshot_projects[project_id] = (
            project,
            completion_percent,
        )

    projects_by_program: dict[str, list[RoadmapTreeProject]] = {
        program.node_id: []
        for program in program_nodes
    }

    for node, project_id, weight in validated_projects:
        snapshot_project, completion_percent = (
            validated_snapshot_projects[project_id]
        )

        projects_by_program[node.parent_id].append(
            RoadmapTreeProject(
                project_id=project_id,
                node_id=node.node_id,
                title=node.title,
                completion_percent=completion_percent,
                weight=weight,
                is_current=snapshot_project.is_current,
                achievement_status=_achievement_status(completion_percent),
            )
        )

    programs = tuple(
        RoadmapTreeProgram(
            node_id=program.node_id,
            title=program.title,
            projects=tuple(projects_by_program[program.node_id]),
        )
        for program in program_nodes
    )

    return RoadmapProgressTree(
        master_id=master_roadmap.master_id,
        title=master_roadmap.title,
        completion_percent=_validate_completion(
            snapshot.completion_percent,
            "snapshot",
        ),
        programs=programs,
    )


def render_roadmap_progress_tree(
    tree: RoadmapProgressTree,
) -> None:
    st.title("World OS Roadmap Progress")
    st.subheader(tree.title)
    st.metric("Global completion", f"{tree.completion_percent:.1f}%")
    st.progress(tree.completion_percent / 100.0)

    for program in tree.programs:
        st.header(program.title)

        for project in program.projects:
            current_marker = " — CURRENT" if project.is_current else ""
            st.write(
                f"**{project.title}**{current_marker}  \n"
                f"{project.completion_percent:.1f}% — "
                f"{project.achievement_status}"
            )
            st.progress(project.completion_percent / 100.0)


def load_and_build_roadmap_progress_tree(
    *,
    master_roadmap_path: Path,
    snapshot: GlobalProgressSnapshot,
) -> RoadmapProgressTree:
    if not isinstance(master_roadmap_path, Path):
        raise RuntimeError("Master roadmap path must be a Path.")

    master_roadmap = load_master_roadmap(master_roadmap_path)

    return build_roadmap_progress_tree(
        master_roadmap=master_roadmap,
        snapshot=snapshot,
    )