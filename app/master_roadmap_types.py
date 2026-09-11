from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


MasterNodeKind = Literal["PROGRAM", "PROJECT"]

MasterRoadmapStatus = Literal[
    "NOT_STARTED",
    "IN_PROGRESS",
    "READY_FOR_HUMAN_REVIEW",
    "APPROVED",
    "COMPLETED",
]


@dataclass(frozen=True)
class MasterRoadmapNode:
    node_id: str
    title: str
    kind: MasterNodeKind
    parent_id: str | None = None
    status: MasterRoadmapStatus = "NOT_STARTED"
    weight: float = 0.0
    dependencies: tuple[str, ...] = ()
    project_id: str | None = None


@dataclass(frozen=True)
class MasterRoadmap:
    master_id: str
    title: str
    target: str
    nodes: tuple[MasterRoadmapNode, ...]