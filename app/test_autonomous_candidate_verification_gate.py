from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import app.build_patch_orchestrator as orchestrator
import app.test_registry as test_registry
from app.patch_quality_evidence_runner import PatchQualityExecutionResult


FOCUSED_TARGET_MODULES = (
    "app.build_patch_orchestrator",
    "app.test_registry",
)


def _quality_result(
    *,
    focused_executed: bool,
    focused_passed: bool,
    regression_executed: bool,
    regression_passed: bool,
    focused_ids: tuple[str, ...] = ("test_focused",),
    regression_ids: tuple[str, ...] = ("test_regression",),
    execution_supported: bool = True,
    reasons: tuple[str, ...] = (),
) -> PatchQualityExecutionResult:
    return PatchQualityExecutionResult(
        workspace_name="world-os-dev-agent",
        target_file="app/example.py",
        behavioral_source_change=True,
        focused_test_ids=focused_ids,
        regression_test_ids=regression_ids,
        focused_tests_executed=focused_executed,
        focused_tests_passed=focused_passed,
        regression_tests_executed=regression_executed,
        regression_tests_passed=regression_passed,
        execution_supported=execution_supported,
        reasons=reasons,
    )


def test_registry_discovers_tests_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    app_dir = workspace / "app"
    tests_dir = workspace / "tests" / "research"

    app_dir.mkdir(parents=True)
    tests_dir.mkdir(parents=True)

    (app_dir / "example.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    (tests_dir / "test_example.py").write_text(
        "import app.example as example\n\n"
        "def test_example():\n"
        "    assert example.VALUE == 1\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        test_registry,
        "get_workspace_profile",
        lambda _: SimpleNamespace(
            name="world-os-dev-agent",
            path=workspace,
        ),
    )

    monkeypatch.setattr(
        test_registry,
        "is_test_execution_validated",
        lambda *_args, **_kwargs: False,
    )

    registry = test_registry.inspect_repository_test_registry(
        "world-os-dev-agent"
    )

    matching = [
        entry
        for entry in registry.tests
        if entry.path == "tests/research/test_example.py"
    ]

    assert len(matching) == 1

    entry = matching[0]

    assert entry.test_id == "tests__research__test_example"
    assert entry.module == "tests.research.test_example"
    assert "app.example" in entry.imported_app_modules

    selection = test_registry.plan_test_selection(
        registry,
        ("app/example.py",),
    )

    assert entry.test_id in selection.focused_test_ids


def _prepare_attempt_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    target = tmp_path / "example.py"
    target.write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    temp_dir = tmp_path / "temp"
    queue_dir = tmp_path / "queue"

    temp_dir.mkdir()
    queue_dir.mkdir()

    monkeypatch.setattr(
        orchestrator,
        "TEMP_DIR",
        temp_dir,
    )
    monkeypatch.setattr(
        orchestrator,
        "QUEUE_DIR",
        queue_dir,
    )

    monkeypatch.setattr(
        orchestrator,
        "compile_candidate",
        lambda _path: (True, ""),
    )

    monkeypatch.setattr(
        orchestrator,
        "review_full_file_candidate",
        lambda **_kwargs: (
            "APPROVE_FOR_HUMAN_REVIEW\n"
            "Candidate is semantically acceptable."
        ),
    )

    return target


def test_quality_preflight_blocks_ready_status_when_not_green(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _prepare_attempt_environment(
        tmp_path,
        monkeypatch,
    )

    monkeypatch.setattr(
        orchestrator,
        "run_patch_quality_evidence",
        lambda **_kwargs: _quality_result(
            focused_executed=False,
            focused_passed=False,
            regression_executed=False,
            regression_passed=False,
            focused_ids=(),
            reasons=("no focused tests selected",),
        ),
    )

    attempt = orchestrator._build_candidate_attempt(
        clean_goal="bounded test",
        canonical_workspace_name="world-os-dev-agent",
        target_file="app/example.py",
        target_path=target,
        target_exists=True,
        format_version="FULL_FILE_V2",
        new_content="VALUE = 2\n",
        revision_round=0,
        lineage=[],
        previous_patch_id=None,
    )

    assert attempt.result.semantic_decision == "REVISE"
    assert attempt.result.status == "DRAFT"
    assert "AUTONOMOUS QUALITY PREFLIGHT DID NOT PASS" in (
        attempt.result.semantic_review
    )


def test_quality_preflight_allows_ready_status_when_green(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _prepare_attempt_environment(
        tmp_path,
        monkeypatch,
    )

    monkeypatch.setattr(
        orchestrator,
        "run_patch_quality_evidence",
        lambda **_kwargs: _quality_result(
            focused_executed=True,
            focused_passed=True,
            regression_executed=True,
            regression_passed=True,
        ),
    )

    attempt = orchestrator._build_candidate_attempt(
        clean_goal="bounded test",
        canonical_workspace_name="world-os-dev-agent",
        target_file="app/example.py",
        target_path=target,
        target_exists=True,
        format_version="FULL_FILE_V2",
        new_content="VALUE = 2\n",
        revision_round=0,
        lineage=[],
        previous_patch_id=None,
    )

    assert (
        attempt.result.semantic_decision
        == "APPROVE_FOR_HUMAN_REVIEW"
    )
    assert attempt.result.status == "READY_FOR_HUMAN_REVIEW"
