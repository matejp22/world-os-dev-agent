from __future__ import annotations

from dataclasses import replace

import app.continue_milestone_runner as runner
from app.milestone_execution_ledger import (
    MilestoneExecutionLedger,
    MilestoneExecutionStep,
)


def _completed_stale_ledger() -> MilestoneExecutionLedger:
    return MilestoneExecutionLedger(
        workspace_name="world-os-research-engine",
        milestone_id="milestone-old",
        milestone_title="Old Production-Ready",
        steps=(
            MilestoneExecutionStep(
                step_id="S1-old-work",
                title="Old work",
                status="COMPLETED",
                patch_ids=(),
                target_files=("app/research/old.py",),
                note=None,
            ),
            MilestoneExecutionStep(
                step_id="S2-old-closure",
                title="Old closure",
                status="COMPLETED",
                patch_ids=(),
                target_files=("app/research/old.py",),
                note=None,
            ),
        ),
    )


def test_allows_rollover_only_from_fully_completed_stale_ledger() -> None:
    ledger = _completed_stale_ledger()

    assert runner._prepare_execution_ledger_rollover(
        workspace_name="world-os-research-engine",
        active_milestone="Roads Production-Ready",
        ledger=ledger,
    ) is True


def test_blocks_rollover_if_stale_ledger_has_unfinished_step() -> None:
    ledger = _completed_stale_ledger()

    unsafe = replace(
        ledger,
        steps=(
            ledger.steps[0],
            replace(
                ledger.steps[1],
                status="PLANNED",
            ),
        ),
    )

    assert runner._prepare_execution_ledger_rollover(
        workspace_name="world-os-research-engine",
        active_milestone="Roads Production-Ready",
        ledger=unsafe,
    ) is False


def test_completed_ledger_rollover_entrypoint_exists() -> None:
    assert callable(
        getattr(runner, "_prepare_execution_ledger_rollover", None)
    ), "Completed ledger rollover must have a controlled entrypoint."

def test_next_ledger_planner_uses_canonical_milestone(monkeypatch):
    from types import SimpleNamespace
    calls = {}
    node = SimpleNamespace(node_id="milestone-new", title="New Milestone")
    monkeypatch.setattr(runner, "_resolve_active_roadmap_milestone", lambda **kwargs: node)
    def fake_planner(**kwargs):
        calls.update(kwargs)
        return "SIMULATED_LEDGER"
    monkeypatch.setattr(runner, "plan_milestone_seams", fake_planner)
    result = runner._plan_next_execution_ledger(workspace_name="world-os-research-engine", active_milestone="New Milestone", milestone_objective="Test objective", relevant_context="Test context")
    assert result == "SIMULATED_LEDGER"
    assert calls["milestone_id"] == "milestone-new"
    assert calls["milestone_title"] == "New Milestone"
    assert calls["milestone_objective"] == "Test objective"
    assert calls["relevant_context"] == "Test context"

def test_execute_rollover_blocks_unfinished_ledger_before_planning(monkeypatch):
    import pytest
    ledger = _completed_stale_ledger()
    unfinished = replace(ledger, steps=(replace(ledger.steps[0], status="PLANNED"), ledger.steps[1]))
    monkeypatch.setattr(runner, "load_milestone_execution_ledger", lambda: unfinished)
    def forbidden_planner(**kwargs):
        raise AssertionError("Planner must not be called.")
    monkeypatch.setattr(runner, "_plan_next_execution_ledger", forbidden_planner)
    with pytest.raises(RuntimeError, match="not permitted"):
        runner._execute_execution_ledger_rollover(
            workspace_name="world-os-research-engine",
            active_milestone="New Milestone",
            milestone_objective="Test objective",
            relevant_context="Test context",
        )

def test_execute_rollover_plans_when_old_ledger_completed(monkeypatch):
    ledger = _completed_stale_ledger()
    expected = replace(ledger, milestone_id="milestone-new", milestone_title="New Milestone")
    from types import SimpleNamespace
    monkeypatch.setattr(
        runner,
        "_resolve_active_roadmap_milestone",
        lambda **kwargs: SimpleNamespace(node_id="milestone-new", title="New Milestone"),
    )
    monkeypatch.setattr(runner, "load_milestone_execution_ledger", lambda: ledger)
    calls = []
    def fake_planner(**kwargs):
        calls.append(kwargs)
        return expected
    monkeypatch.setattr(runner, "_plan_next_execution_ledger", fake_planner)
    result = runner._execute_execution_ledger_rollover(
        workspace_name="world-os-research-engine",
        active_milestone="New Milestone",
        milestone_objective="Test objective",
        relevant_context="Test context",
    )
    assert result is expected
    assert len(calls) == 1
    assert calls[0]["active_milestone"] == "New Milestone"
    assert calls[0]["milestone_objective"] == "Test objective"

def test_execute_rollover_planning_failure_propagates(monkeypatch):
    import pytest
    ledger = _completed_stale_ledger()
    monkeypatch.setattr(runner, "load_milestone_execution_ledger", lambda: ledger)
    def failing_planner(**kwargs):
        raise RuntimeError("Simulated planning failure")
    monkeypatch.setattr(runner, "_plan_next_execution_ledger", failing_planner)
    with pytest.raises(RuntimeError, match="Simulated planning failure"):
        runner._execute_execution_ledger_rollover(
            workspace_name="world-os-research-engine",
            active_milestone="New Milestone",
            milestone_objective="Test objective",
            relevant_context="Test context",
        )

def test_execute_rollover_rejects_wrong_milestone_id(monkeypatch):
    import pytest
    from types import SimpleNamespace
    ledger = _completed_stale_ledger()
    wrong = replace(ledger, milestone_id="milestone-wrong", milestone_title="New Milestone")
    monkeypatch.setattr(runner, "load_milestone_execution_ledger", lambda: ledger)
    monkeypatch.setattr(runner, "_plan_next_execution_ledger", lambda **kwargs: wrong)
    monkeypatch.setattr(
        runner, "_resolve_active_roadmap_milestone",
        lambda **kwargs: SimpleNamespace(node_id="milestone-new", title="New Milestone"),
    )
    with pytest.raises(RuntimeError, match="does not match canonical active milestone"):
        runner._execute_execution_ledger_rollover(
            workspace_name="world-os-research-engine",
            active_milestone="New Milestone",
            milestone_objective="Test objective",
            relevant_context="Test context",
        )

import pytest

@pytest.fixture(autouse=True)
def isolate_rollover_writes(monkeypatch, tmp_path):
    context = tmp_path / "context"
    context.mkdir()
    (context / "RESEARCH_ENGINE_MILESTONE_EXECUTION_LEDGER.json").write_text("test-ledger", encoding="utf-8")
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(runner, "archive_execution_ledger", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "save_milestone_execution_ledger", lambda *args, **kwargs: None)

def test_rollover_archive_failure_prevents_save(monkeypatch):
    from types import SimpleNamespace
    import pytest

    ledger = _completed_stale_ledger()
    next_ledger = replace(
        ledger,
        milestone_id="milestone-new",
        milestone_title="New Milestone",
    )
    monkeypatch.setattr(runner, "load_milestone_execution_ledger", lambda: ledger)
    monkeypatch.setattr(runner, "_plan_next_execution_ledger", lambda **kwargs: next_ledger)
    monkeypatch.setattr(
        runner, "_resolve_active_roadmap_milestone",
        lambda **kwargs: SimpleNamespace(node_id="milestone-new", title="New Milestone"),
    )

    calls = []

    def fail_archive(*args, **kwargs):
        calls.append("archive")
        raise RuntimeError("Simulated archive failure")

    def fake_save(*args, **kwargs):
        calls.append("save")

    monkeypatch.setattr(runner, "archive_execution_ledger", fail_archive)
    monkeypatch.setattr(runner, "save_milestone_execution_ledger", fake_save)

    with pytest.raises(RuntimeError, match="Simulated archive failure"):
        runner._execute_execution_ledger_rollover(
            workspace_name="world-os-research-engine",
            active_milestone="New Milestone",
            milestone_objective="Test objective",
            relevant_context="Test context",
        )

    assert calls == ["archive"]

def test_rollover_archives_then_saves_once(monkeypatch):
    from types import SimpleNamespace

    ledger = _completed_stale_ledger()
    next_ledger = replace(
        ledger,
        milestone_id="milestone-new",
        milestone_title="New Milestone",
    )

    monkeypatch.setattr(runner, "load_milestone_execution_ledger", lambda: ledger)
    monkeypatch.setattr(runner, "_plan_next_execution_ledger", lambda **kwargs: next_ledger)
    monkeypatch.setattr(
        runner,
        "_resolve_active_roadmap_milestone",
        lambda **kwargs: SimpleNamespace(
            node_id="milestone-new",
            title="New Milestone",
        ),
    )

    calls = []

    def fake_archive(*args, **kwargs):
        calls.append("archive")

    def fake_save(saved_ledger):
        assert saved_ledger is next_ledger
        calls.append("save")

    monkeypatch.setattr(runner, "archive_execution_ledger", fake_archive)
    monkeypatch.setattr(runner, "save_milestone_execution_ledger", fake_save)

    result = runner._execute_execution_ledger_rollover(
        workspace_name="world-os-research-engine",
        active_milestone="New Milestone",
        milestone_objective="Test objective",
        relevant_context="Test context",
    )

    assert result is next_ledger
    assert calls == ["archive", "save"]