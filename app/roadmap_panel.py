from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.global_progress_snapshot import (
    GlobalProgressSnapshot,
    build_global_progress_snapshot,
)
from app.roadmap_progress import calculate_project_progress
from app.roadmap_progress_tree import load_and_build_roadmap_progress_tree
from app.roadmap_store import PROJECT_ROADMAP_DIR, load_project_roadmap
from app.roadmap_types import RoadmapNode


def _render_milestone(milestone: RoadmapNode, current_milestone_id: str | None) -> None:
    is_current = milestone.node_id == current_milestone_id
    label = "CURRENT — " if is_current else ""

    details = (
        f"**{label}{milestone.title}**  \n"
        f"ID: `{milestone.node_id}`  \n"
        f"Status: `{milestone.status}`  \n"
        f"Verification: `{milestone.verification_status}`  \n"
        f"Weight: {milestone.weight:g}  \n"
        f"Dependencies: "
        f"{', '.join(milestone.dependencies) if milestone.dependencies else 'None'}"
    )

    if milestone.patch_id is not None:
        details += f"  \nPatch ID: `{milestone.patch_id}`"

    if milestone.completed_at is not None:
        details += f"  \nCompleted at: `{milestone.completed_at}`"

    if is_current:
        st.warning(details)
    elif (
        milestone.status == "COMPLETED"
        and milestone.verification_status == "PASSED"
    ):
        st.success(details)
    elif milestone.status == "IN_PROGRESS":
        st.warning(details)
    elif milestone.status == "NOT_STARTED":
        st.info(details)
    else:
        st.error(details)


def _render_project_detail(
    project_id: str,
    project_title: str,
    workspace_name: str | None,
    *,
    roadmap_dir: Path,
) -> None:
    st.markdown(f"### {project_title}")
    st.caption(f"Project ID: `{project_id}`")

    if workspace_name is None:
        st.info("No canonical project roadmap is connected.")
        return

    roadmap = load_project_roadmap(workspace_name, roadmap_dir)
    progress = calculate_project_progress(roadmap)

    completed_weight = progress.completed_weight
    total_weight = progress.total_weight
    remaining_percent = progress.remaining_percent

    columns = st.columns(4)
    columns[0].metric("Completion", f"{progress.completion_percent:.1f}%")
    columns[1].metric(
        "Milestones",
        f"{progress.completed_milestones}/{progress.total_milestones}",
    )
    columns[2].metric(
        "Weight",
        f"{completed_weight:g}/{total_weight:g}",
    )
    columns[3].metric("Remaining", f"{remaining_percent:.1f}%")

    st.progress(progress.completion_percent / 100.0)

    groups = tuple(
        node
        for node in roadmap.nodes
        if node.kind == "GROUP"
    )
    milestones_by_parent: dict[str | None, list[RoadmapNode]] = {}

    for node in roadmap.nodes:
        if node.kind == "MILESTONE":
            milestones_by_parent.setdefault(node.parent_id, []).append(node)

    for group in groups:
        with st.expander(group.title, expanded=True):
            st.caption(f"Group ID: `{group.node_id}`")
            group_milestones = milestones_by_parent.get(group.node_id, [])

            for milestone in group_milestones:
                _render_milestone(
                    milestone,
                    progress.current_milestone_id,
                )


def render_world_os_roadmap_panel(
    *,
    master_roadmap_path: Path,
    project_workspaces: dict[str, str],
    roadmap_dir: Path = PROJECT_ROADMAP_DIR,
) -> GlobalProgressSnapshot:
    snapshot = build_global_progress_snapshot(
        master_roadmap_path=master_roadmap_path,
        project_workspaces=project_workspaces,
        roadmap_dir=roadmap_dir,
    )
    tree = load_and_build_roadmap_progress_tree(
        master_roadmap_path=master_roadmap_path,
        snapshot=snapshot,
    )

    st.subheader(tree.title)

    columns = st.columns(4)
    columns[0].metric("Global completion", f"{snapshot.completion_percent:.1f}%")
    columns[1].metric(
        "Projects",
        f"{snapshot.completed_projects}/{snapshot.total_projects}",
    )
    columns[2].metric(
        "Weight",
        f"{snapshot.completed_weight:g}/{snapshot.total_weight:g}",
    )
    columns[3].metric("Remaining", f"{snapshot.remaining_percent:.1f}%")

    st.progress(snapshot.completion_percent / 100.0)

    project_workspace_by_id = {
        project.project_id: project_workspaces.get(project.project_id)
        for project in snapshot.projects
    }

    for program in tree.programs:
        st.markdown(f"## {program.title}")

        for project in program.projects:
            current_marker = " — CURRENT" if project.is_current else ""
            with st.expander(
                f"{project.title}{current_marker}",
                expanded=project.is_current,
            ):
                st.caption(f"Project ID: `{project.project_id}`")
                st.metric(
                    "Project completion",
                    f"{project.completion_percent:.1f}%",
                )
                st.progress(project.completion_percent / 100.0)
                _render_project_detail(
                    project.project_id,
                    project.title,
                    project_workspace_by_id[project.project_id],
                    roadmap_dir=roadmap_dir,
                )

        st.divider()

    return snapshot