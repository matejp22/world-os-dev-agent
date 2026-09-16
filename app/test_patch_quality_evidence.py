from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

import pytest

from app.patch_quality_gate import QualityVerdict

if TYPE_CHECKING:
    import app.patch_quality_evidence


_CANDIDATE_ENV = "WORLD_OS_PATCH_QUALITY_EVIDENCE_CANDIDATE"
_CANONICAL_MODULE = "app.patch_quality_evidence"
_CANDIDATE_MODULE_NAME = "_world_os_patch_quality_evidence_candidate"


def _load_patch_quality_evidence_module() -> ModuleType:
    candidate_value = os.environ.get(_CANDIDATE_ENV, "").strip()

    if not candidate_value:
        return importlib.import_module(_CANONICAL_MODULE)

    candidate = Path(candidate_value).resolve()

    if not candidate.exists():
        raise RuntimeError(f"Candidate does not exist: {candidate}")

    if not candidate.is_file():
        raise RuntimeError(f"Candidate is not a file: {candidate}")

    if candidate.suffix.lower() != ".py":
        raise RuntimeError("Candidate must be a Python file.")

    spec = importlib.util.spec_from_file_location(
        _CANDIDATE_MODULE_NAME,
        candidate,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to create candidate module specification.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module

    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise

    return module


@pytest.fixture
def evidence_module() -> ModuleType:
    return _load_patch_quality_evidence_module()


@dataclass(frozen=True)
class RegistryStub:
    tests: tuple[object, ...] = ()
    inspected: bool = True


@dataclass(frozen=True)
class SelectionStub:
    focused_test_ids: tuple[str, ...]
    regression_test_ids: tuple[str, ...]


def _install_selection_mocks(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    regression_test_ids: tuple[str, ...],
) -> None:
    registry = RegistryStub()
    selection = SelectionStub(
        focused_test_ids=("test_focus",),
        regression_test_ids=regression_test_ids,
    )

    def fake_inspect(workspace_name: str) -> RegistryStub:
        assert workspace_name == "world-os-dev-agent"
        return registry

    def fake_select(
        registry_arg: RegistryStub,
        changed_files: tuple[str, ...],
    ) -> SelectionStub:
        assert registry_arg is registry
        assert changed_files == ("app/example.py",)
        return selection

    monkeypatch.setattr(
        module,
        "inspect_repository_test_registry",
        fake_inspect,
    )
    monkeypatch.setattr(
        module,
        "plan_test_selection",
        fake_select,
    )


def _record(
    *,
    quality_evidence: dict[str, bool] | None = None,
) -> dict[str, object]:
    return {
        "workspace_name": "world-os-dev-agent",
        "target_file": "app/example.py",
        "quality_evidence": quality_evidence or {},
    }


def _structural_kwargs() -> dict[str, bool]:
    return {
        "format_supported": True,
        "lifecycle_ready": True,
        "compile_passed": True,
        "semantic_approved": True,
        "workspace_policy_passed": True,
        "target_scope_passed": True,
        "artifact_integrity_passed": True,
    }


def test_blocked_regressions_are_excluded_from_required_regression_ids(
    evidence_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_selection_mocks(
        monkeypatch,
        evidence_module,
        (
            "test_alpha",
            "test_full_file_diff_pipeline",
            "test_beta",
            "test_repaired_patch_pipeline",
        ),
    )

    context = evidence_module.build_patch_quality_evidence(
        _record(),
        **_structural_kwargs(),
    )

    assert context.focused_test_ids == ("test_focus",)
    assert context.regression_test_ids == (
        "test_alpha",
        "test_beta",
    )
    assert context.evidence.regression_tests_required is True


def test_only_blocked_regressions_mean_no_required_automated_regression(
    evidence_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_selection_mocks(
        monkeypatch,
        evidence_module,
        (
            "test_full_file_diff_pipeline",
            "test_repaired_patch_pipeline",
        ),
    )

    context = evidence_module.build_patch_quality_evidence(
        _record(),
        **_structural_kwargs(),
    )

    assert context.regression_test_ids == ()
    assert context.evidence.regression_tests_required is False


def test_execution_eligible_regression_evidence_can_pass(
    evidence_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_selection_mocks(
        monkeypatch,
        evidence_module,
        (
            "test_alpha",
            "test_full_file_diff_pipeline",
            "test_repaired_patch_pipeline",
        ),
    )

    record = _record(
        quality_evidence={
            "focused_tests_executed": True,
            "focused_tests_passed": True,
            "regression_tests_executed": True,
            "regression_tests_passed": True,
        },
    )

    context, result = evidence_module.evaluate_patch_record_quality(
        record,
        **_structural_kwargs(),
    )

    assert context.regression_test_ids == ("test_alpha",)
    assert result.verdict == QualityVerdict.PASS
    assert result.safe_for_human_approval is True


def test_execution_eligible_regression_failure_still_fails_closed(
    evidence_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_selection_mocks(
        monkeypatch,
        evidence_module,
        (
            "test_alpha",
            "test_full_file_diff_pipeline",
            "test_repaired_patch_pipeline",
        ),
    )

    record = _record(
        quality_evidence={
            "focused_tests_executed": True,
            "focused_tests_passed": True,
            "regression_tests_executed": True,
            "regression_tests_passed": False,
        },
    )

    context, result = evidence_module.evaluate_patch_record_quality(
        record,
        **_structural_kwargs(),
    )

    assert context.regression_test_ids == ("test_alpha",)
    assert result.verdict != QualityVerdict.PASS
    assert result.safe_for_human_approval is False


def test_policy_uses_canonical_blocked_test_ids(
    evidence_module: ModuleType,
) -> None:
    from app.test_execution import (
        BLOCKED_TEST_IDS as CANONICAL_BLOCKED_TEST_IDS,
    )

    assert evidence_module.BLOCKED_TEST_IDS == CANONICAL_BLOCKED_TEST_IDS