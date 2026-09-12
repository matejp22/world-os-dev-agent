from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.lifecycle_roadmap_sync import (
    LifecycleRoadmapSyncDecision,
)
from app.roadmap_types import (
    ProjectRoadmap,
    RoadmapNode,
)


StrictMilestoneCompletionStatus = Literal[
    "ELIGIBLE_FOR_COMPLETION",
    "NOT_ELIGIBLE",
]


@dataclass(frozen=True)
class StrictMilestoneCompletionDecision:
    project_id: str
    milestone_id: str
    patch_id: str
    status: StrictMilestoneCompletionStatus
    eligible: bool
    target_status: str | None
    target_verification_status: str | None
    reason: str


def _not_eligible(
    *,
    roadmap: ProjectRoadmap,
    milestone_id: str,
    patch_id: str,
    reason: str,
) -> StrictMilestoneCompletionDecision:
    return StrictMilestoneCompletionDecision(
        project_id=roadmap.project_id,
        milestone_id=milestone_id,
        patch_id=patch_id,
        status="NOT_ELIGIBLE",
        eligible=False,
        target_status=None,
        target_verification_status=None,
        reason=reason,
    )


def evaluate_strict_milestone_completion(
    *,
    roadmap: ProjectRoadmap,
    milestone_id: str,
    sync_decision: LifecycleRoadmapSyncDecision,
) -> StrictMilestoneCompletionDecision:
    if not isinstance(roadmap, ProjectRoadmap):
        raise RuntimeError("roadmap must be a ProjectRoadmap.")

    if type(milestone_id) is not str or not milestone_id:
        raise RuntimeError(
            "milestone_id must be an exact non-empty string."
        )

    if not isinstance(
        sync_decision,
        LifecycleRoadmapSyncDecision,
    ):
        raise RuntimeError(
            "sync_decision must be a LifecycleRoadmapSyncDecision."
        )

    patch_id = (
        sync_decision.patch_id
        if type(sync_decision.patch_id) is str
        and sync_decision.patch_id
        else ""
    )

    matching_nodes = tuple(
        node
        for node in roadmap.nodes
        if node.node_id == milestone_id
    )

    if not matching_nodes:
        return _not_eligible(
            roadmap=roadmap,
            milestone_id=milestone_id,
            patch_id=patch_id,
            reason="Milestone was not found.",
        )

    if len(matching_nodes) != 1:
        return _not_eligible(
            roadmap=roadmap,
            milestone_id=milestone_id,
            patch_id=patch_id,
            reason="Milestone identifier is duplicated.",
        )

    milestone = matching_nodes[0]

    if milestone.kind != "MILESTONE":
        return _not_eligible(
            roadmap=roadmap,
            milestone_id=milestone_id,
            patch_id=patch_id,
            reason="Target node is not a milestone.",
        )

    if (
        milestone.status != "NOT_STARTED"
        or milestone.verification_status != "PENDING"
        or milestone.patch_id is not None
        or milestone.completed_at is not None
    ):
        return _not_eligible(
            roadmap=roadmap,
            milestone_id=milestone_id,
            patch_id=patch_id,
            reason="Milestone is not in the eligible initial state.",
        )

    if (
        sync_decision.status != "VERIFIED_FOR_COMPLETION"
        or sync_decision.verified is not True
    ):
        return _not_eligible(
            roadmap=roadmap,
            milestone_id=milestone_id,
            patch_id=patch_id,
            reason="Lifecycle evidence is not strictly verified.",
        )

    if not patch_id:
        return _not_eligible(
            roadmap=roadmap,
            milestone_id=milestone_id,
            patch_id=patch_id,
            reason="Verified lifecycle evidence has no patch identifier.",
        )

    for dependency_id in milestone.dependencies:
        dependencies = tuple(
            node
            for node in roadmap.nodes
            if node.node_id == dependency_id
        )

        if len(dependencies) != 1:
            return _not_eligible(
                roadmap=roadmap,
                milestone_id=milestone_id,
                patch_id=patch_id,
                reason="A dependency does not resolve uniquely.",
            )

        dependency: RoadmapNode = dependencies[0]

        if (
            dependency.kind != "MILESTONE"
            or dependency.status != "COMPLETED"
            or dependency.verification_status != "PASSED"
        ):
            return _not_eligible(
                roadmap=roadmap,
                milestone_id=milestone_id,
                patch_id=patch_id,
                reason="A dependency is not completed and verified.",
            )

    return StrictMilestoneCompletionDecision(
        project_id=roadmap.project_id,
        milestone_id=milestone_id,
        patch_id=patch_id,
        status="ELIGIBLE_FOR_COMPLETION",
        eligible=True,
        target_status="COMPLETED",
        target_verification_status="PASSED",
        reason="Milestone satisfies all strict completion requirements.",
    )