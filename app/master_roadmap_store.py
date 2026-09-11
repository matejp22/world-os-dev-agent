from __future__ import annotations

import json
import math
from numbers import Real
from pathlib import Path
from typing import Any

from app.master_roadmap_types import MasterRoadmap, MasterRoadmapNode


MASTER_FIELDS = frozenset(
    {
        "master_id",
        "title",
        "target",
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
        "project_id",
    }
)

NODE_KINDS = frozenset({"PROGRAM", "PROJECT"})

ROADMAP_STATUSES = frozenset(
    {
        "NOT_STARTED",
        "IN_PROGRESS",
        "READY_FOR_HUMAN_REVIEW",
        "APPROVED",
        "COMPLETED",
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


def _parse_node(value: object, index: int) -> MasterRoadmapNode:
    raw = _require_exact_fields(
        value,
        NODE_FIELDS,
        f"Master roadmap node {index}",
    )

    node_id = _require_string(
        raw["node_id"],
        f"Master roadmap node {index} node_id",
    )
    title = _require_string(
        raw["title"],
        f"Master roadmap node {index} title",
    )

    kind = raw["kind"]
    if kind not in NODE_KINDS:
        raise RuntimeError(f"Invalid node kind for {node_id}: {kind!r}")

    parent_id = _require_string(
        raw["parent_id"],
        f"Master roadmap node {index} parent_id",
        allow_none=True,
    )

    status = raw["status"]
    if status not in ROADMAP_STATUSES:
        raise RuntimeError(
            f"Invalid roadmap status for {node_id}: {status!r}"
        )

    raw_dependencies = raw["dependencies"]
    if not isinstance(raw_dependencies, list):
        raise RuntimeError(f"Dependencies must be a list for {node_id}.")

    dependencies: list[str] = []
    dependency_ids: set[str] = set()

    for dependency in raw_dependencies:
        parsed_dependency = _require_string(
            dependency,
            f"Dependency for {node_id}",
        )
        assert parsed_dependency is not None

        if parsed_dependency in dependency_ids:
            raise RuntimeError(
                f"Duplicate dependency for {node_id}: "
                f"{parsed_dependency}"
            )

        dependency_ids.add(parsed_dependency)
        dependencies.append(parsed_dependency)

    project_id = _require_string(
        raw["project_id"],
        f"Master roadmap node {index} project_id",
        allow_none=True,
    )

    weight = raw["weight"]

    if kind == "PROGRAM":
        if project_id is not None:
            raise RuntimeError(
                f"PROGRAM node must not have a project_id: {node_id}"
            )

        if (
            isinstance(weight, bool)
            or not isinstance(weight, Real)
            or float(weight) != 0.0
        ):
            raise RuntimeError(
                f"PROGRAM weight must equal 0.0: {node_id}"
            )

        parsed_weight = 0.0
    else:
        if project_id is None:
            raise RuntimeError(
                f"PROJECT node must have a project_id: {node_id}"
            )

        if (
            isinstance(weight, bool)
            or not isinstance(weight, Real)
            or not math.isfinite(float(weight))
            or float(weight) <= 0.0
        ):
            raise RuntimeError(
                f"PROJECT weight must be finite and greater than zero: "
                f"{node_id}"
            )

        parsed_weight = float(weight)

    return MasterRoadmapNode(
        node_id=node_id,
        title=title,
        kind=kind,
        parent_id=parent_id,
        status=status,
        weight=parsed_weight,
        dependencies=tuple(dependencies),
        project_id=project_id,
    )


def _validate_parent_tree(
    nodes: tuple[MasterRoadmapNode, ...],
) -> None:
    node_by_id = {node.node_id: node for node in nodes}

    for node in nodes:
        if node.parent_id is None:
            continue

        if node.parent_id == node.node_id:
            raise RuntimeError(
                f"Node cannot parent itself: {node.node_id}"
            )

        parent = node_by_id.get(node.parent_id)
        if parent is None:
            raise RuntimeError(
                f"Unknown parent ID for {node.node_id}: "
                f"{node.parent_id}"
            )

        if parent.kind == "PROJECT":
            raise RuntimeError(
                f"PROJECT node cannot have children: {parent.node_id}"
            )

    for node in nodes:
        visited: set[str] = set()
        current_id: str | None = node.node_id

        while current_id is not None:
            if current_id in visited:
                raise RuntimeError(
                    f"Parent hierarchy cycle detected at: {current_id}"
                )

            visited.add(current_id)
            current = node_by_id[current_id]
            current_id = current.parent_id


def _validate_dependencies(
    nodes: tuple[MasterRoadmapNode, ...],
) -> None:
    node_by_id = {node.node_id: node for node in nodes}

    for node in nodes:
        for dependency in node.dependencies:
            if dependency == node.node_id:
                raise RuntimeError(
                    f"Node cannot depend on itself: {node.node_id}"
                )

            if dependency not in node_by_id:
                raise RuntimeError(
                    f"Unknown dependency for {node.node_id}: "
                    f"{dependency}"
                )

    state: dict[str, int] = {}

    def visit(node_id: str) -> None:
        current_state = state.get(node_id, 0)

        if current_state == 1:
            raise RuntimeError(
                f"Dependency cycle detected at: {node_id}"
            )

        if current_state == 2:
            return

        state[node_id] = 1

        for dependency in node_by_id[node_id].dependencies:
            visit(dependency)

        state[node_id] = 2

    for node in nodes:
        visit(node.node_id)


def _validate_nodes(
    nodes: tuple[MasterRoadmapNode, ...],
) -> None:
    node_ids = [node.node_id for node in nodes]

    if len(set(node_ids)) != len(node_ids):
        raise RuntimeError("Master roadmap contains duplicate node IDs.")

    project_ids: set[str] = set()

    for node in nodes:
        if node.kind != "PROJECT":
            continue

        if node.project_id is None:
            raise RuntimeError(
                f"PROJECT node must have a project_id: {node.node_id}"
            )

        if node.project_id in project_ids:
            raise RuntimeError(
                f"Duplicate project_id: {node.project_id}"
            )

        project_ids.add(node.project_id)

    _validate_parent_tree(nodes)
    _validate_dependencies(nodes)


def master_roadmap_from_dict(
    value: dict[str, object],
) -> MasterRoadmap:
    raw_master = _require_exact_fields(
        value,
        MASTER_FIELDS,
        "Master roadmap",
    )

    master_id = _require_string(
        raw_master["master_id"],
        "Master roadmap master_id",
    )
    title = _require_string(
        raw_master["title"],
        "Master roadmap title",
    )
    target = _require_string(
        raw_master["target"],
        "Master roadmap target",
    )

    raw_nodes = raw_master["nodes"]
    if not isinstance(raw_nodes, list):
        raise RuntimeError("Master roadmap nodes must be a list.")

    nodes = tuple(
        _parse_node(node, index)
        for index, node in enumerate(raw_nodes)
    )

    _validate_nodes(nodes)

    assert master_id is not None
    assert title is not None
    assert target is not None

    return MasterRoadmap(
        master_id=master_id,
        title=title,
        target=target,
        nodes=nodes,
    )


def load_master_roadmap(path: Path) -> MasterRoadmap:
    if not isinstance(path, Path):
        raise RuntimeError("Master roadmap path must be a Path.")

    if not path.exists():
        raise RuntimeError(
            f"Master roadmap file does not exist: {path}"
        )

    if not path.is_file():
        raise RuntimeError(
            f"Master roadmap path is not a regular file: {path}"
        )

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Unable to read master roadmap: {path}"
        ) from exc

    try:
        raw_master = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Master roadmap contains malformed JSON: {path}"
        ) from exc

    if not isinstance(raw_master, dict):
        raise RuntimeError("Master roadmap must be an object.")

    return master_roadmap_from_dict(raw_master)