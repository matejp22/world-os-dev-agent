from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from app.milestone_execution_ledger import (
    MilestoneExecutionLedger,
    MilestoneExecutionStep,
)
from app.roadmap_types import ProjectRoadmap, RoadmapNode
import app.post_completion_reconciler as reconciler


FOCUSED_TARGET_MODULES = (
    "app.post_completion_reconciler",
    "app.roadmap_store",
)


def _ledger() -> MilestoneExecutionLedger:
    return MilestoneExecutionLedger(
        workspace_name="world-os-research-engine",
        milestone_id="milestone-test",
        milestone_title="Test milestone",
        steps=(
            MilestoneExecutionStep(
                step_id="S1",
                title="First",
                status="IN_PROGRESS",
                patch_ids=("patch-1",),
                target_files=("app/example.py",),
            ),
            MilestoneExecutionStep(
                step_id="S2",
                title="Second",
                status="PLANNED",
                target_files=("app/next.py",),
            ),
        ),
    )


def test_record_patch_marks_first_planned_step_in_progress(
    monkeypatch,
) -> None:
    ledger = replace(
        _ledger(),
        steps=tuple(
            replace(step, status="PLANNED", patch_ids=())
            for step in _ledger().steps
        ),
    )

    saved = []

    monkeypatch.setattr(
        reconciler,
        "load_milestone_execution_ledger",
        lambda: ledger,
    )
    monkeypatch.setattr(
        reconciler,
        "save_milestone_execution_ledger",
        lambda value: saved.append(value),
    )

    assert reconciler.record_patch_for_active_step(
        "patch-new"
    ) is True

    assert saved[0].steps[0].status == "IN_PROGRESS"
    assert saved[0].steps[0].patch_ids == ("patch-new",)


def test_verified_checkpoint_advances_to_next_step(
    monkeypatch,
) -> None:
    ledger = _ledger()
    saved = []

    class GitStatus:
        tracked_modified = ()
        untracked = ()
        staged = ()
        conflicted = ()

    monkeypatch.setattr(
        reconciler,
        "load_milestone_execution_ledger",
        lambda: ledger,
    )
    monkeypatch.setattr(
        reconciler,
        "inspect_git_workspace_status",
        lambda _workspace: GitStatus(),
    )
    monkeypatch.setattr(
        reconciler,
        "_patch_is_committed_and_verified",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        reconciler,
        "save_milestone_execution_ledger",
        lambda value: saved.append(value),
    )

    result = reconciler.reconcile_completed_execution_step(
        "world-os-research-engine"
    )

    assert result.changed is True
    assert result.completed_step_id == "S1"
    assert result.next_step_id == "S2"
    assert result.milestone_completed is False
    assert saved[0].steps[0].status == "COMPLETED"
    assert saved[0].steps[1].status == "IN_PROGRESS"


def test_unverified_checkpoint_does_not_advance(
    monkeypatch,
) -> None:
    ledger = _ledger()

    class GitStatus:
        tracked_modified = ()
        untracked = ()
        staged = ()
        conflicted = ()

    monkeypatch.setattr(
        reconciler,
        "load_milestone_execution_ledger",
        lambda: ledger,
    )
    monkeypatch.setattr(
        reconciler,
        "inspect_git_workspace_status",
        lambda _workspace: GitStatus(),
    )
    monkeypatch.setattr(
        reconciler,
        "_patch_is_committed_and_verified",
        lambda **_kwargs: False,
    )

    result = reconciler.reconcile_completed_execution_step(
        "world-os-research-engine"
    )

    assert result.changed is False
    assert result.completed_step_id is None
