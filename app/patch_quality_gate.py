from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class QualityVerdict(str, Enum):
    PASS = "PASS"
    REVISE = "REVISE"
    BLOCK = "BLOCK"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    MISSING = "MISSING"
    NOT_REQUIRED = "NOT_REQUIRED"


@dataclass(frozen=True)
class PatchQualityCheck:
    name: str
    status: CheckStatus
    reason: str


@dataclass(frozen=True)
class PatchQualityEvidence:
    format_supported: bool
    lifecycle_ready: bool
    compile_passed: bool
    semantic_approved: bool
    workspace_policy_passed: bool
    target_scope_passed: bool
    artifact_integrity_passed: bool
    behavioral_source_change: bool
    focused_tests_required: bool
    focused_tests_available: bool
    focused_tests_executed: bool
    focused_tests_passed: bool
    regression_tests_required: bool
    regression_tests_executed: bool
    regression_tests_passed: bool
    high_risk_boundary: bool


@dataclass(frozen=True)
class PatchQualityGateResult:
    verdict: QualityVerdict
    risk: RiskLevel
    safe_for_human_approval: bool
    checks: tuple[PatchQualityCheck, ...]
    reasons: tuple[str, ...]
    required_actions: tuple[str, ...]


_STRUCTURAL_CHECKS = (
    ("format_supported", "Patch format is supported."),
    ("lifecycle_ready", "Patch lifecycle is ready."),
    ("compile_passed", "Compilation passed."),
    ("semantic_approved", "Semantic review approved the patch."),
    ("workspace_policy_passed", "Workspace policy passed."),
    ("target_scope_passed", "Patch target scope passed."),
    ("artifact_integrity_passed", "Patch artifact integrity passed."),
)


def _boolean_check(
    name: str,
    value: bool,
    passed_reason: str,
) -> PatchQualityCheck:
    return PatchQualityCheck(
        name=name,
        status=CheckStatus.PASS if value else CheckStatus.FAIL,
        reason=passed_reason if value else f"{passed_reason[:-1]} failed.",
    )


def _focused_tests_check(evidence: PatchQualityEvidence) -> PatchQualityCheck:
    name = "Focused tests"

    if not evidence.focused_tests_required:
        return PatchQualityCheck(
            name=name,
            status=CheckStatus.NOT_REQUIRED,
            reason="Focused tests are not required.",
        )

    if not evidence.focused_tests_available:
        return PatchQualityCheck(
            name=name,
            status=CheckStatus.MISSING,
            reason="Focused tests are required but unavailable.",
        )

    if not evidence.focused_tests_executed:
        return PatchQualityCheck(
            name=name,
            status=CheckStatus.MISSING,
            reason="Focused tests are required but have not been executed.",
        )

    if not evidence.focused_tests_passed:
        return PatchQualityCheck(
            name=name,
            status=CheckStatus.FAIL,
            reason="Focused tests executed and failed.",
        )

    return PatchQualityCheck(
        name=name,
        status=CheckStatus.PASS,
        reason="Focused tests executed and passed.",
    )


def _regression_tests_check(
    evidence: PatchQualityEvidence,
) -> PatchQualityCheck:
    name = "Regression tests"

    if not evidence.regression_tests_required:
        return PatchQualityCheck(
            name=name,
            status=CheckStatus.NOT_REQUIRED,
            reason="Regression tests are not required.",
        )

    if not evidence.regression_tests_executed:
        return PatchQualityCheck(
            name=name,
            status=CheckStatus.MISSING,
            reason="Regression tests are required but have not been executed.",
        )

    if not evidence.regression_tests_passed:
        return PatchQualityCheck(
            name=name,
            status=CheckStatus.FAIL,
            reason="Regression tests executed and failed.",
        )

    return PatchQualityCheck(
        name=name,
        status=CheckStatus.PASS,
        reason="Regression tests executed and passed.",
    )


def evaluate_patch_quality(
    evidence: PatchQualityEvidence,
) -> PatchQualityGateResult:
    if not isinstance(evidence, PatchQualityEvidence):
        raise TypeError("evidence must be a PatchQualityEvidence instance.")

    structural_checks = tuple(
        _boolean_check(
            name=name,
            value=getattr(evidence, name),
            passed_reason=reason,
        )
        for name, reason in _STRUCTURAL_CHECKS
    )
    test_checks = (
        _focused_tests_check(evidence),
        _regression_tests_check(evidence),
    )
    checks = structural_checks + test_checks

    risk = (
        RiskLevel.HIGH
        if evidence.high_risk_boundary
        else (
            RiskLevel.MEDIUM
            if evidence.behavioral_source_change
            else RiskLevel.LOW
        )
    )

    structural_failures = tuple(
        check for check in structural_checks
        if check.status == CheckStatus.FAIL
    )
    failed_tests = tuple(
        check for check in test_checks
        if check.status == CheckStatus.FAIL
    )
    missing_tests = tuple(
        check for check in test_checks
        if check.status == CheckStatus.MISSING
    )

    if structural_failures:
        return PatchQualityGateResult(
            verdict=QualityVerdict.BLOCK,
            risk=risk,
            safe_for_human_approval=False,
            checks=checks,
            reasons=tuple(
                f"{check.name}: {check.reason}"
                for check in structural_failures
            ),
            required_actions=(
                "Resolve every failed structural or safety prerequisite.",
            ),
        )

    if failed_tests:
        return PatchQualityGateResult(
            verdict=QualityVerdict.BLOCK,
            risk=risk,
            safe_for_human_approval=False,
            checks=checks,
            reasons=tuple(check.reason for check in failed_tests),
            required_actions=(
                "Fix the failing tests and rerun the required test coverage.",
            ),
        )

    if missing_tests:
        actions = []
        if any(
            check.name == "Focused tests"
            for check in missing_tests
        ):
            actions.append(
                "Focused tests are required; make them available, "
                "execute them, and verify they pass."
            )
        if any(
            check.name == "Regression tests"
            for check in missing_tests
        ):
            actions.append(
                "Execute the required regression tests and verify they pass."
            )

        return PatchQualityGateResult(
            verdict=QualityVerdict.REVISE,
            risk=risk,
            safe_for_human_approval=False,
            checks=checks,
            reasons=tuple(check.reason for check in missing_tests),
            required_actions=tuple(actions),
        )

    return PatchQualityGateResult(
        verdict=QualityVerdict.PASS,
        risk=risk,
        safe_for_human_approval=True,
        checks=checks,
        reasons=("All required structural, safety, and test checks passed.",),
        required_actions=(),
    )