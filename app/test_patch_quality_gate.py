from __future__ import annotations

from app.patch_quality_gate import (
    PatchQualityEvidence,
    QualityVerdict,
    RiskLevel,
    evaluate_patch_quality,
)


def _evidence(**overrides: object) -> PatchQualityEvidence:
    values = {
        "format_supported": True,
        "lifecycle_ready": True,
        "compile_passed": True,
        "semantic_approved": True,
        "workspace_policy_passed": True,
        "target_scope_passed": True,
        "artifact_integrity_passed": True,
        "behavioral_source_change": False,
        "focused_tests_required": False,
        "focused_tests_available": False,
        "focused_tests_executed": False,
        "focused_tests_passed": False,
        "regression_tests_required": False,
        "regression_tests_executed": False,
        "regression_tests_passed": False,
        "high_risk_boundary": False,
    }
    values.update(overrides)
    return PatchQualityEvidence(**values)


def test_behavioral_change_without_focused_tests_requires_revision() -> None:
    result = evaluate_patch_quality(
        _evidence(
            behavioral_source_change=True,
            focused_tests_required=True,
        )
    )

    assert result.verdict is QualityVerdict.REVISE
    assert result.risk is RiskLevel.MEDIUM
    assert result.safe_for_human_approval is False
    assert any(
        "Focused tests are required" in action
        for action in result.required_actions
    )


def test_completed_structural_and_test_checks_pass() -> None:
    result = evaluate_patch_quality(
        _evidence(
            behavioral_source_change=True,
            focused_tests_required=True,
            focused_tests_available=True,
            focused_tests_executed=True,
            focused_tests_passed=True,
            regression_tests_required=True,
            regression_tests_executed=True,
            regression_tests_passed=True,
        )
    )

    assert result.verdict is QualityVerdict.PASS
    assert result.risk is RiskLevel.MEDIUM
    assert result.safe_for_human_approval is True


def test_compile_failure_blocks_approval() -> None:
    result = evaluate_patch_quality(
        _evidence(compile_passed=False)
    )

    assert result.verdict is QualityVerdict.BLOCK
    assert result.safe_for_human_approval is False


def test_failed_focused_tests_block_approval() -> None:
    result = evaluate_patch_quality(
        _evidence(
            focused_tests_required=True,
            focused_tests_available=True,
            focused_tests_executed=True,
            focused_tests_passed=False,
        )
    )

    assert result.verdict is QualityVerdict.BLOCK
    assert result.safe_for_human_approval is False


def test_missing_required_regression_tests_requires_revision() -> None:
    result = evaluate_patch_quality(
        _evidence(regression_tests_required=True)
    )

    assert result.verdict is QualityVerdict.REVISE
    assert result.safe_for_human_approval is False


def test_high_risk_boundary_sets_high_risk() -> None:
    result = evaluate_patch_quality(
        _evidence(high_risk_boundary=True)
    )

    assert result.risk is RiskLevel.HIGH


def test_non_behavioral_change_without_required_tests_passes_low_risk() -> None:
    result = evaluate_patch_quality(_evidence())

    assert result.verdict is QualityVerdict.PASS
    assert result.risk is RiskLevel.LOW
    assert result.safe_for_human_approval is True