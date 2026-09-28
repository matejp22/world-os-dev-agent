from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Iterator

import pytest

from app.lifecycle_roadmap_sync import LifecycleRoadmapSyncDecision
from app.roadmap_types import ProjectRoadmap, RoadmapNode
from app.test_registry import (
    inspect_repository_test_registry,
    plan_test_selection,
)


FOCUSED_TARGET_MODULES = (
    "app.strict_milestone_completion",
)


@pytest.fixture
def implementation_module() -> Iterator[ModuleType]:
    target_name = "app.strict_milestone_completion"
    previous_module = sys.modules.get(target_name)
    sys.modules.pop(target_name, None)

    try:
        try:
            module = importlib.import_module(target_name)
        except ModuleNotFoundError as exc:
            if exc.name != target_name:
                raise
            pytest.skip(
                "app.strict_milestone_completion is not canonically installed yet."
            )
        yield module
    finally:
        sys.modules.pop(target_name, None)
        if previous_module is not None:
            sys.modules[target_name] = previous_module


def test_focused_target_modules_are_exact() -> None:
    assert FOCUSED_TARGET_MODULES == (
        "app.strict_milestone_completion",
    )


def test_repository_test_registry_selects_focused_test() -> None:
    registry = inspect_repository_test_registry(
        "world-os-dev-agent",
    )

    plan = plan_test_selection(
        registry,
        ("app/strict_milestone_completion.py",),
    )

    assert "test_strict_milestone_completion" in (
        plan.focused_test_ids
    )


def _roadmap() -> ProjectRoadmap:
    dependency = RoadmapNode(
        node_id="dependency-milestone",
        title="Completed dependency",
        kind="MILESTONE",
        status="COMPLETED",
        verification_status="PASSED",
    )
    target = RoadmapNode(
        node_id="target-milestone",
        title="Target milestone",
        kind="MILESTONE",
        status="IN_PROGRESS",
        dependencies=("dependency-milestone",),
        verification_status="PENDING",
        patch_id=None,
        completed_at=None,
    )
    return ProjectRoadmap(
        project_id="project-test",
        title="Strict completion test roadmap",
        workspace_name="world-os-dev-agent",
        nodes=(dependency, target),
    )


def _verified_sync_decision() -> LifecycleRoadmapSyncDecision:
    return LifecycleRoadmapSyncDecision(
        patch_id="patch-test-123",
        format_version="FULL_FILE_V2",
        target_file="app/example.py",
        status="VERIFIED_FOR_COMPLETION",
        verified=True,
        candidate_sha256="a" * 64,
        observed_target_sha256="a" * 64,
        reason="Verified lifecycle evidence.",
    )


def test_in_progress_milestone_with_verified_lifecycle_is_eligible(
    implementation_module: ModuleType,
) -> None:
    roadmap = _roadmap()
    target = roadmap.nodes[1]

    assert target.kind == "MILESTONE"
    assert target.status == "IN_PROGRESS"
    assert target.verification_status == "PENDING"
    assert target.patch_id is None
    assert target.completed_at is None
    assert target.dependencies == ("dependency-milestone",)

    dependency = roadmap.nodes[0]
    assert dependency.status == "COMPLETED"
    assert dependency.verification_status == "PASSED"

    lifecycle = _verified_sync_decision()
    assert lifecycle.status == "VERIFIED_FOR_COMPLETION"
    assert lifecycle.verified is True
    assert lifecycle.patch_id

    decision = (
        implementation_module.evaluate_strict_milestone_completion(
            roadmap=roadmap,
            milestone_id="target-milestone",
            sync_decision=lifecycle,
        )
    )

    assert decision.status == "ELIGIBLE_FOR_COMPLETION"
    assert decision.eligible is True
    assert decision.target_status == "COMPLETED"
    assert decision.target_verification_status == "PASSED"


def test_unverified_lifecycle_evidence_is_not_eligible(
    implementation_module: ModuleType,
) -> None:
    lifecycle = LifecycleRoadmapSyncDecision(
        patch_id="patch-test-123",
        format_version="FULL_FILE_V2",
        target_file="app/example.py",
        status="NOT_VERIFIED",
        verified=False,
        candidate_sha256="a" * 64,
        observed_target_sha256="a" * 64,
        reason="Lifecycle evidence was not verified.",
    )

    decision = (
        implementation_module.evaluate_strict_milestone_completion(
            roadmap=_roadmap(),
            milestone_id="target-milestone",
            sync_decision=lifecycle,
        )
    )

    assert decision.status == "NOT_ELIGIBLE"
    assert decision.eligible is False