from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.continue_milestone_runner as runner


FOCUSED_TARGET_MODULES = (
    "app.continue_milestone_runner",
)


def _ledger(*steps):
    return SimpleNamespace(
        workspace_name="world-os-research-engine",
        milestone_id="milestone-example",
        milestone_title="Example Milestone",
        steps=steps,
    )


def _step(
    step_id: str,
    status: str,
    title: str,
):
    return SimpleNamespace(
        step_id=step_id,
        status=status,
        title=title,
        target_files=(
            "app/research/example.py",
            "tests/research/test_example.py",
        ),
        note="Implement the bounded example behavior.",
    )


def test_execution_ledger_prefers_in_progress_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = _ledger(
        _step("S1", "PLANNED", "First"),
        _step("S2", "IN_PROGRESS", "Second"),
        _step("S3", "PLANNED", "Third"),
    )

    monkeypatch.setattr(
        runner,
        "load_milestone_execution_ledger",
        lambda: ledger,
    )

    objective = (
        runner._resolve_execution_ledger_objective(
            workspace_name="world-os-research-engine",
            active_milestone="Example Milestone",
            fallback_objective="fallback",
        )
    )

    assert "S2" in objective
    assert "Second" in objective
    assert "app/research/example.py" in objective


def test_execution_ledger_selects_first_planned_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = _ledger(
        _step("S1", "COMPLETED", "Done"),
        _step("S2", "PLANNED", "Next"),
        _step("S3", "PLANNED", "Later"),
    )

    monkeypatch.setattr(
        runner,
        "load_milestone_execution_ledger",
        lambda: ledger,
    )

    objective = (
        runner._resolve_execution_ledger_objective(
            workspace_name="world-os-research-engine",
            active_milestone="Example Milestone",
            fallback_objective="fallback",
        )
    )

    assert "S2" in objective
    assert "Next" in objective
    assert "S3" not in objective


def test_execution_ledger_rejects_milestone_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runner,
        "load_milestone_execution_ledger",
        lambda: _ledger(
            _step("S1", "PLANNED", "First"),
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="does not match",
    ):
        runner._resolve_execution_ledger_objective(
            workspace_name="world-os-research-engine",
            active_milestone="Different Milestone",
            fallback_objective="fallback",
        )


def test_execution_ledger_is_not_used_for_dev_agent_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called():
        raise AssertionError("RE ledger must not load for Dev Agent workspace")

    monkeypatch.setattr(
        runner,
        "load_milestone_execution_ledger",
        fail_if_called,
    )

    objective = runner._resolve_execution_ledger_objective(
        workspace_name="world-os-dev-agent",
        active_milestone="test milestone",
        fallback_objective="test objective",
    )

    assert objective == "test objective"

