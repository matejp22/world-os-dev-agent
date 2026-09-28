from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterator

import pytest

from app.test_registry import (
    inspect_repository_test_registry,
    plan_test_selection,
)


FOCUSED_TARGET_MODULES = (
    "app.milestone_execution_ledger",
)


@pytest.fixture
def implementation_module() -> Iterator[ModuleType]:
    target_name = "app.milestone_execution_ledger"
    previous_module = sys.modules.get(target_name)
    sys.modules.pop(target_name, None)

    try:
        try:
            module = importlib.import_module(target_name)
        except ModuleNotFoundError as exc:
            if exc.name != target_name:
                raise
            pytest.skip(
                "app.milestone_execution_ledger is not canonically installed yet."
            )
        yield module
    finally:
        sys.modules.pop(target_name, None)
        if previous_module is not None:
            sys.modules[target_name] = previous_module


def test_focused_target_modules_are_exact() -> None:
    assert FOCUSED_TARGET_MODULES == (
        "app.milestone_execution_ledger",
    )


def test_repository_test_registry_selects_focused_test() -> None:
    registry = inspect_repository_test_registry(
        "world-os-dev-agent",
    )

    plan = plan_test_selection(
        registry,
        ("app/milestone_execution_ledger.py",),
    )

    assert "test_milestone_execution_ledger" in (
        plan.focused_test_ids
    )


def _step_types(module: ModuleType) -> tuple[type, type]:
    return (
        module.MilestoneExecutionStep,
        module.MilestoneExecutionLedger,
    )


def test_valid_round_trip(
    implementation_module: ModuleType,
) -> None:
    step_type, ledger_type = _step_types(implementation_module)

    planned = step_type(
        step_id="step-plan",
        title="Plan milestone work",
        status="PLANNED",
        patch_ids=("patch-plan",),
        target_files=("app/example.py",),
        note="Ready for execution.",
    )
    completed = step_type(
        step_id="step-complete",
        title="Complete milestone work",
        status="COMPLETED",
        patch_ids=("patch-complete",),
        target_files=("app/example.py",),
    )
    ledger = ledger_type(
        workspace_name="world-os-research-engine",
        milestone_id="milestone-test",
        milestone_title="Test Milestone",
        steps=(planned, completed),
    )

    implementation_module.validate_milestone_execution_ledger(
        ledger
    )

    encoded = (
        implementation_module.milestone_execution_ledger_to_dict(
            ledger
        )
    )
    decoded = (
        implementation_module.milestone_execution_ledger_from_dict(
            encoded
        )
    )

    assert decoded == ledger


def test_empty_steps_are_valid(
    implementation_module: ModuleType,
) -> None:
    ledger_type = implementation_module.MilestoneExecutionLedger
    ledger = ledger_type(
        workspace_name="world-os-research-engine",
        milestone_id="milestone-test",
        milestone_title="Test Milestone",
        steps=(),
    )

    implementation_module.validate_milestone_execution_ledger(
        ledger
    )


def test_invalid_workspace_fails_closed(
    implementation_module: ModuleType,
) -> None:
    ledger_type = implementation_module.MilestoneExecutionLedger
    ledger = ledger_type(
        workspace_name="",
        milestone_id="milestone-test",
        milestone_title="Test Milestone",
        steps=(),
    )

    with pytest.raises((ValueError, TypeError, RuntimeError)):
        implementation_module.validate_milestone_execution_ledger(
            ledger
        )


def test_duplicate_step_ids_fail_closed(
    implementation_module: ModuleType,
) -> None:
    step_type = implementation_module.MilestoneExecutionStep
    ledger_type = implementation_module.MilestoneExecutionLedger

    first = step_type(
        step_id="duplicate",
        title="First step",
        status="PLANNED",
    )
    second = step_type(
        step_id="duplicate",
        title="Second step",
        status="COMPLETED",
    )
    ledger = ledger_type(
        workspace_name="world-os-research-engine",
        milestone_id="milestone-test",
        milestone_title="Test Milestone",
        steps=(first, second),
    )

    with pytest.raises((ValueError, TypeError, RuntimeError)):
        implementation_module.validate_milestone_execution_ledger(
            ledger
        )


def test_unsupported_status_fails_closed(
    implementation_module: ModuleType,
) -> None:
    step_type = implementation_module.MilestoneExecutionStep
    step = step_type(
        step_id="step-invalid",
        title="Invalid step",
        status="UNSUPPORTED",
    )

    with pytest.raises((ValueError, TypeError, RuntimeError)):
        implementation_module.validate_milestone_execution_step(
            step
        )


def test_invalid_schema_fails_closed(
    implementation_module: ModuleType,
) -> None:
    with pytest.raises((ValueError, TypeError, RuntimeError)):
        implementation_module.milestone_execution_ledger_from_dict(
            []
        )

    with pytest.raises((ValueError, TypeError, RuntimeError)):
        implementation_module.milestone_execution_ledger_from_dict(
            {
                "workspace_name": "world-os-research-engine",
                "milestone_id": "milestone-test",
                "steps": [],
            }
        )

    with pytest.raises((ValueError, TypeError, RuntimeError)):
        implementation_module.milestone_execution_ledger_from_dict(
            {
                "workspace_name": "world-os-research-engine",
                "milestone_id": "milestone-test",
                "milestone_title": "Test Milestone",
                "steps": [
                    {
                        "step_id": "step-invalid",
                        "title": "Invalid step",
                        "status": "PLANNED",
                        "unexpected": True,
                    }
                ],
            }
        )


def test_safe_save_load_round_trip(
    implementation_module: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context_dir = tmp_path / "context"
    context_dir.mkdir()

    ledger_path = (
        context_dir
        / "RESEARCH_ENGINE_MILESTONE_EXECUTION_LEDGER.json"
    )

    monkeypatch.setattr(
        implementation_module,
        "PROJECT_ROOT",
        tmp_path,
    )
    monkeypatch.setattr(
        implementation_module,
        "MILESTONE_EXECUTION_LEDGER_PATH",
        ledger_path,
    )

    step_type = implementation_module.MilestoneExecutionStep
    ledger_type = implementation_module.MilestoneExecutionLedger
    ledger = ledger_type(
        workspace_name="world-os-research-engine",
        milestone_id="milestone-test",
        milestone_title="Test Milestone",
        steps=(
            step_type(
                step_id="step-plan",
                title="Plan milestone work",
                status="PLANNED",
            ),
        ),
    )

    implementation_module.save_milestone_execution_ledger(
        ledger
    )

    assert ledger_path.exists()
    raw = ledger_path.read_bytes()
    assert raw.endswith(b"\n")

    parsed = json.loads(raw.decode("utf-8"))
    assert isinstance(parsed, dict)

    loaded = implementation_module.load_milestone_execution_ledger()

    assert loaded == ledger


def test_missing_ledger_returns_none(
    implementation_module: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context_dir = tmp_path / "context"
    context_dir.mkdir()

    ledger_path = (
        context_dir
        / "RESEARCH_ENGINE_MILESTONE_EXECUTION_LEDGER.json"
    )

    monkeypatch.setattr(
        implementation_module,
        "PROJECT_ROOT",
        tmp_path,
    )
    monkeypatch.setattr(
        implementation_module,
        "MILESTONE_EXECUTION_LEDGER_PATH",
        ledger_path,
    )

    assert (
        implementation_module.load_milestone_execution_ledger()
        is None
    )


def test_schema_operations_do_not_touch_canonical_ledger(
    implementation_module: ModuleType,
) -> None:
    canonical_path = Path(
        implementation_module.MILESTONE_EXECUTION_LEDGER_PATH
    )
    existed_before = canonical_path.exists()

    step_type = implementation_module.MilestoneExecutionStep
    ledger_type = implementation_module.MilestoneExecutionLedger
    ledger = ledger_type(
        workspace_name="world-os-research-engine",
        milestone_id="milestone-test",
        milestone_title="Test Milestone",
        steps=(
            step_type(
                step_id="step-schema",
                title="Validate schema",
                status="PLANNED",
            ),
        ),
    )

    encoded = (
        implementation_module.milestone_execution_ledger_to_dict(
            ledger
        )
    )
    decoded = (
        implementation_module.milestone_execution_ledger_from_dict(
            encoded
        )
    )
    implementation_module.validate_milestone_execution_step(
        decoded.steps[0]
    )
    implementation_module.validate_milestone_execution_ledger(
        decoded
    )

    assert canonical_path.exists() is existed_before