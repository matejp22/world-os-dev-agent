from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RoadmapStatus = Literal[
    "NOT_STARTED",
    "IN_PROGRESS",
    "READY_FOR_HUMAN_REVIEW",
    "APPROVED",
    "COMPLETED",
]

VerificationStatus = Literal[
    "NOT_REQUIRED",
    "PENDING",
    "PASSED",
    "FAILED",
]


@dataclass(frozen=True)
class RoadmapNode:
    node_id: str
    title: str
    kind: Literal["GROUP", "MILESTONE"]
    parent_id: str | None = None
    status: RoadmapStatus = "NOT_STARTED"
    weight: float = 0.0
    dependencies: tuple[str, ...] = ()
    verification_status: VerificationStatus = "NOT_REQUIRED"
    patch_id: str | None = None
    completed_at: str | None = None


@dataclass(frozen=True)
class ProjectRoadmap:
    project_id: str
    title: str
    workspace_name: str
    nodes: tuple[RoadmapNode, ...]