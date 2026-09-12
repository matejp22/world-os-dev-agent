from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.global_progress_snapshot import (
    GlobalProgressSnapshot,
    build_global_progress_snapshot,
)
from app.roadmap_progress_tree import (
    RoadmapProgressTree,
    load_and_build_roadmap_progress_tree,
)
from app.roadmap_store import PROJECT_ROADMAP_DIR


DEFAULT_MASTER_ROADMAP_PATH = Path(
    "context/master_roadmaps/world-os-2050.json"
)

DEFAULT_PROJECT_WORKSPACES = {
    "world-os-dev-agent": "world-os-dev-agent",
    "world-os-research-engine": "world-os-research-engine",
    "world-os-web": "world-os-web",
}


def render_global_progress_snapshot(
    snapshot: GlobalProgressSnapshot,
) -> None:
    if snapshot.total_projects != len(snapshot.projects):
        raise RuntimeError(
            "Snapshot total_projects does not match the project count."
        )

    if not snapshot.master_id:
        raise RuntimeError("Snapshot master_id must not be empty.")

    st.title("Global Progress Snapshot")

    metric_columns = st.columns(4)

    with metric_columns[0]:
        st.metric(
            "Global completion",
            f"{snapshot.completion_percent:.2f}%",
        )

    with metric_columns[1]:
        st.metric(
            "Remaining",
            f"{snapshot.remaining_percent:.2f}%",
        )

    with metric_columns[2]:
        st.metric(
            "Completed weight",
            f"{snapshot.completed_weight:.2f} / "
            f"{snapshot.total_weight:.2f}",
        )

    with metric_columns[3]:
        st.metric(
            "Completed projects",
            f"{snapshot.completed_projects} / "
            f"{snapshot.total_projects}",
        )

    st.caption(f"Master roadmap: {snapshot.master_id}")

    current_project_ids = snapshot.current_project_ids

    if current_project_ids:
        st.write(
            "Current project IDs: "
            + ", ".join(current_project_ids)
        )
    else:
        st.write("Current project IDs: <none>")

    project_rows = [
        {
            "project_id": project.project_id,
            "completion_percent": project.completion_percent,
            "is_current": project.is_current,
        }
        for project in snapshot.projects
    ]

    st.dataframe(
        project_rows,
        use_container_width=True,
        hide_index=True,
    )


def render_roadmap_console(
    *,
    master_roadmap_path: Path,
    project_workspaces: dict[str, str],
    roadmap_dir: Path = PROJECT_ROADMAP_DIR,
) -> GlobalProgressSnapshot:
    if not isinstance(master_roadmap_path, Path):
        raise RuntimeError("Master roadmap path must be a Path.")

    snapshot = build_global_progress_snapshot(
        master_roadmap_path=master_roadmap_path,
        project_workspaces=project_workspaces,
        roadmap_dir=roadmap_dir,
    )

    render_global_progress_snapshot(snapshot)

    return snapshot


def _terminal_progress_bar(
    completion_percent: float,
    *,
    width: int = 30,
) -> str:
    if not 0.0 <= completion_percent <= 100.0:
        raise RuntimeError(
            "completion_percent must be between 0.0 and 100.0."
        )

    filled = round(
        width * completion_percent / 100.0
    )

    return (
        "["
        + "#" * filled
        + "-" * (width - filled)
        + "]"
    )


def _terminal_project_marker(
    *,
    achievement_status: str,
    is_current: bool,
) -> str:
    if is_current:
        return ">>"

    if achievement_status == "ACHIEVED":
        return "OK"

    if achievement_status == "IN_PROGRESS":
        return ".."

    return "--"


def render_terminal_roadmap(
    tree: RoadmapProgressTree,
) -> str:
    lines: list[str] = []

    lines.append("=" * 78)
    lines.append("WORLD OS 2050 - MASTER ROADMAP")
    lines.append("=" * 78)
    lines.append("")
    lines.append(tree.title)
    lines.append(f"Master ID: {tree.master_id}")
    lines.append("")
    lines.append("GLOBAL PROGRESS")
    lines.append(
        f"{_terminal_progress_bar(tree.completion_percent, width=40)} "
        f"{tree.completion_percent:6.2f}%"
    )
    lines.append("")

    for program_index, program in enumerate(tree.programs):
        lines.append("-" * 78)
        lines.append(program.title)
        lines.append("-" * 78)

        if not program.projects:
            lines.append("  <no projects>")
            lines.append("")
            continue

        for project_index, project in enumerate(program.projects):
            is_last = (
                project_index
                == len(program.projects) - 1
            )

            branch = "`--" if is_last else "|--"

            marker = _terminal_project_marker(
                achievement_status=project.achievement_status,
                is_current=project.is_current,
            )

            current_text = (
                "  <== CURRENT"
                if project.is_current
                else ""
            )

            lines.append(
                f"{branch} [{marker}] {project.title}{current_text}"
            )

            lines.append(
                "    "
                f"{_terminal_progress_bar(project.completion_percent)} "
                f"{project.completion_percent:6.2f}%  "
                f"{project.achievement_status}"
            )

            lines.append(
                f"    project_id={project.project_id}  "
                f"weight={project.weight:g}"
            )

        if program_index != len(tree.programs) - 1:
            lines.append("")

    current_projects = [
        project
        for program in tree.programs
        for project in program.projects
        if project.is_current
    ]

    lines.append("")
    lines.append("=" * 78)
    lines.append("CURRENT FOCUS")
    lines.append("=" * 78)

    if current_projects:
        for project in current_projects:
            lines.append(
                f">> {project.title} "
                f"({project.completion_percent:.2f}%)"
            )
    else:
        lines.append("<none>")

    lines.append("")
    lines.append("Legend: OK=achieved  ..=in progress  --=not started  >>=current")
    lines.append("=" * 78)

    return "\n".join(lines)


def build_terminal_roadmap(
    *,
    master_roadmap_path: Path = DEFAULT_MASTER_ROADMAP_PATH,
    project_workspaces: dict[str, str] | None = None,
    roadmap_dir: Path = PROJECT_ROADMAP_DIR,
) -> str:
    if project_workspaces is None:
        project_workspaces = dict(
            DEFAULT_PROJECT_WORKSPACES
        )

    snapshot = build_global_progress_snapshot(
        master_roadmap_path=master_roadmap_path,
        project_workspaces=project_workspaces,
        roadmap_dir=roadmap_dir,
    )

    tree = load_and_build_roadmap_progress_tree(
        master_roadmap_path=master_roadmap_path,
        snapshot=snapshot,
    )

    return render_terminal_roadmap(tree)


def main() -> None:
    print(
        build_terminal_roadmap()
    )


if __name__ == "__main__":
    main()