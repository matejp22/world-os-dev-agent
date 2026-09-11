from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.roadmap_types import ProjectRoadmap, RoadmapNode
from app.workspace_registry import get_workspace_profile


PROJECT_ROADMAP_DIR = (
    Path(__file__).resolve().parent.parent
    / "context"
    / "project_roadmaps"
)

PROJECT_FIELDS = frozenset(
    {
        "project_id",
        "title",
        "workspace_name",
        "nodes",
    }
)

NODE_FIELDS = frozenset(
    {
        "node_id",
        "title",
        "kind",
        "parent_id",
        "status",
        "weight",
        "dependencies",
        "verification_status",
        "patch_id",
        "completed_at",
    }
)

NODE_KINDS = frozenset({"GROUP", "MILESTONE"})

ROADMAP_STATUSES = frozenset(
    {
        "NOT_STARTED",
        "IN_PROGRESS",
        "READY_FOR_HUMAN_REVIEW",
        "APPROVED",
        "COMPLETED",
    }
)

VERIFICATION_STATUSES = frozenset(
    {
        "NOT_REQUIRED",
        "PENDING",
        "PASSED",
        "FAILED",
    }
)


def _require_exact_fields(
    value: object,
    expected: frozenset[str],
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must be an object.")

    actual = frozenset(value)

    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise RuntimeError(
            f"{label} fields do not match exactly. "
            f"Missing: {missing}; unknown: {unknown}."
        )

    return value


def _require_string(
    value: object,
    label: str,
    *,
    allow_none: bool = False,
) -> str | None:
    if allow_none and value is None:
        return None

    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{label} must be a non-empty string.")

    return value


def _parse_node(value: object, index: int) -> RoadmapNode:
    raw = _require_exact_fields(
        value,
        NODE_FIELDS,
        f"Roadmap node {index}",
    )

    node_id = _require_string(
        raw["node_id"],
        f"Roadmap node {index} node_id",
    )
    title = _require_string(
        raw["title"],
        f"Roadmap node {index} title",
    )
    kind = raw["kind"]

    if kind not in NODE_KINDS:
        raise RuntimeError(f"Invalid node kind for {node_id}: {kind!r}")

    parent_id = _require_string(
        raw["parent_id"],
        f"Roadmap node {index} parent_id",
        allow_none=True,
    )

    status = raw["status"]

    if status not in ROADMAP_STATUSES:
        raise RuntimeError(
            f"Invalid roadmap status for {node_id}: {status!r}"
        )

    weight = raw["weight"]

    if (
        isinstance(weight, bool)
        or not isinstance(weight, (int, float))
        or weight < 0
    ):
        raise RuntimeError(
            f"Invalid roadmap weight for {node_id}: {weight!r}"
        )

    dependencies = raw["dependencies"]

    if not isinstance(dependencies, list):
        raise RuntimeError(f"Dependencies must be a list for {node_id}.")

    parsed_dependencies: list[str] = []

    for dependency in dependencies:
        parsed_dependency = _require_string(
            dependency,
            f"Dependency for {node_id}",
        )
        parsed_dependencies.append(parsed_dependency)

    verification_status = raw["verification_status"]

    if verification_status not in VERIFICATION_STATUSES:
        raise RuntimeError(
            "Invalid verification status for "
            f"{node_id}: {verification_status!r}"
        )

    patch_id = _require_string(
        raw["patch_id"],
        f"Roadmap node {index} patch_id",
        allow_none=True,
    )
    completed_at = _require_string(
        raw["completed_at"],
        f"Roadmap node {index} completed_at",
        allow_none=True,
    )

    return RoadmapNode(
        node_id=node_id,
        title=title,
        kind=kind,
        parent_id=parent_id,
        status=status,
        weight=float(weight),
        dependencies=tuple(parsed_dependencies),
        verification_status=verification_status,
        patch_id=patch_id,
        completed_at=completed_at,
    )


def _validate_relationships(nodes: tuple[RoadmapNode, ...]) -> None:
    node_ids = {node.node_id for node in nodes}

    if len(node_ids) != len(nodes):
        raise RuntimeError("Roadmap contains duplicate node IDs.")

    for node in nodes:
        if node.parent_id is not None:
            if node.parent_id == node.node_id:
                raise RuntimeError(
                    f"Node cannot parent itself: {node.node_id}"
                )

            if node.parent_id not in node_ids:
                raise RuntimeError(
                    f"Unknown parent ID for {node.node_id}: "
                    f"{node.parent_id}"
                )

        for dependency in node.dependencies:
            if dependency == node.node_id:
                raise RuntimeError(
                    f"Node cannot depend on itself: {node.node_id}"
                )

            if dependency not in node_ids:
                raise RuntimeError(
                    f"Unknown dependency for {node.node_id}: "
                    f"{dependency}"
                )


def roadmap_path_for_workspace(
    workspace_name: str,
    roadmap_dir: Path = PROJECT_ROADMAP_DIR,
) -> Path:
    requested_workspace_name = _require_string(
        workspace_name,
        "Requested workspace_name",
    )

    workspace = get_workspace_profile(requested_workspace_name)
    canonical_workspace_name = workspace.name

    if not isinstance(roadmap_dir, Path):
        raise RuntimeError("roadmap_dir must be a Path.")

    resolved_directory = roadmap_dir.resolve()
    roadmap_path = (
        resolved_directory
        / f"{canonical_workspace_name}.json"
    ).resolve()

    try:
        if roadmap_path.parent != resolved_directory:
            raise RuntimeError(
                "Roadmap path escapes the supplied roadmap directory."
            )
    except OSError as exc:
        raise RuntimeError(
            "Unable to resolve roadmap directory."
        ) from exc

    return roadmap_path


def project_roadmap_from_dict(
    value: dict[str, object],
) -> ProjectRoadmap:
    project = _require_exact_fields(
        value,
        PROJECT_FIELDS,
        "Project roadmap",
    )

    project_id = _require_string(
        project["project_id"],
        "Project roadmap project_id",
    )
    title = _require_string(
        project["title"],
        "Project roadmap title",
    )
    declared_workspace_name = _require_string(
        project["workspace_name"],
        "Project roadmap workspace_name",
    )

    workspace = get_workspace_profile(declared_workspace_name)

    if project_id != workspace.name:
        raise RuntimeError(
            "Project roadmap project_id must equal the canonical "
            f"workspace name: {workspace.name!r}"
        )

    if declared_workspace_name != workspace.name:
        raise RuntimeError(
            "Project roadmap workspace_name must equal the canonical "
            f"workspace name: {workspace.name!r}"
        )

    raw_nodes = project["nodes"]

    if not isinstance(raw_nodes, list):
        raise RuntimeError("Project roadmap nodes must be a list.")

    nodes = tuple(
        _parse_node(node, index)
        for index, node in enumerate(raw_nodes)
    )

    _validate_relationships(nodes)

    return ProjectRoadmap(
        project_id=project_id,
        title=title,
        workspace_name=workspace.name,
        nodes=nodes,
    )


def load_project_roadmap(
    workspace_name: str,
    roadmap_dir: Path = PROJECT_ROADMAP_DIR,
) -> ProjectRoadmap:
    roadmap_path = roadmap_path_for_workspace(
        workspace_name,
        roadmap_dir,
    )

    workspace = get_workspace_profile(workspace_name)

    try:
        raw_text = roadmap_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Unable to read project roadmap: {roadmap_path}"
        ) from exc

    try:
        raw_project = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Project roadmap contains malformed JSON: "
            f"{roadmap_path}"
        ) from exc

    if not isinstance(raw_project, dict):
        raise RuntimeError("Project roadmap must be an object.")

    project = project_roadmap_from_dict(raw_project)

    if project.workspace_name != workspace.name:
        raise RuntimeError(
            "Loaded roadmap workspace does not match requested workspace: "
            f"{project.workspace_name!r}"
        )

    return project