from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.patch_quality_gate import (
    PatchQualityEvidence,
    PatchQualityGateResult,
    evaluate_patch_quality,
)
from app.test_execution import BLOCKED_TEST_IDS
from app.test_registry import (
    inspect_repository_test_registry,
    plan_test_selection,
)


@dataclass(frozen=True)
class PatchQualityEvidenceContext:
    evidence: PatchQualityEvidence
    focused_test_ids: tuple[str, ...]
    regression_test_ids: tuple[str, ...]
    reasons: tuple[str, ...]


_HIGH_RISK_PATHS = frozenset(
    {
        "app/patch_quality_gate.py",
        "app/patch_quality_evidence.py",
        "app/full_file_approval.py",
        "app/full_file_apply_v2.py",
        "app/workspace_registry.py",
        "app/command_policy.py",
        "app/production_autonomy_gate.py",
        "app/patch_approval.py",
        "app/patch_apply.py",
    }
)

_HIGH_RISK_PARTS = frozenset(
    {
        "auth",
        "security",
        "database",
        "db",
        "supabase",
        "migration",
        "migrations",
    }
)


def _required_string(record: Mapping[str, object], name: str) -> str:
    value = record.get(name)

    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{name} must be a non-empty string.")

    return value.strip()


def _quality_booleans(
    record: Mapping[str, object],
) -> tuple[bool, bool, bool, bool, bool]:
    value = record.get("quality_evidence")

    if value is None:
        return False, False, False, False, False

    if not isinstance(value, Mapping):
        raise RuntimeError("quality_evidence must be a mapping.")

    def boolean(name: str) -> bool:
        candidate = value.get(name)
        return candidate if type(candidate) is bool else False

    return (
        True,
        boolean("focused_tests_executed"),
        boolean("focused_tests_passed"),
        boolean("regression_tests_executed"),
        boolean("regression_tests_passed"),
    )


def _normalized_target(target_file: str) -> str:
    return target_file.replace("\\", "/").strip().casefold()


def _is_behavioral_source(target_file: str) -> bool:
    normalized = _normalized_target(target_file)

    if not normalized.endswith(".py"):
        return False

    if normalized in {
        "app/test_execution.py",
        "app/test_registry.py",
    }:
        return True

    if normalized.startswith("app/"):
        return not normalized.rsplit("/", 1)[-1].startswith("test_")

    if normalized.startswith("scripts/"):
        return not normalized.rsplit("/", 1)[-1].startswith("test_")

    return False


def _is_high_risk(target_file: str) -> bool:
    normalized = _normalized_target(target_file)

    if normalized in _HIGH_RISK_PATHS:
        return True

    return bool(
        _HIGH_RISK_PARTS.intersection(
            part for part in normalized.split("/") if part
        )
    )


def build_patch_quality_evidence(
    record: Mapping[str, object],
    *,
    format_supported: bool,
    lifecycle_ready: bool,
    compile_passed: bool,
    semantic_approved: bool,
    workspace_policy_passed: bool,
    target_scope_passed: bool,
    artifact_integrity_passed: bool,
) -> PatchQualityEvidenceContext:
    if not isinstance(record, Mapping):
        raise RuntimeError("record must be a mapping.")

    workspace_name = _required_string(record, "workspace_name")
    target_file = _required_string(record, "target_file")

    behavioral = _is_behavioral_source(target_file)
    focused_ids: tuple[str, ...] = ()
    regression_ids: tuple[str, ...] = ()
    reasons: list[str] = []

    if behavioral:
        registry = inspect_repository_test_registry(workspace_name)
        selection = plan_test_selection(registry, (target_file,))
        focused_ids = selection.focused_test_ids
        regression_ids = tuple(
            test_id
            for test_id in selection.regression_test_ids
            if test_id not in BLOCKED_TEST_IDS
        )

        if not registry.tests:
            reasons.append("zero registered tests")
        if focused_ids:
            reasons.append("focused tests selected")
        else:
            reasons.append("no focused tests selected")
        if regression_ids:
            reasons.append("regression tests selected")
    else:
        reasons.append("test-only or non-behavioral change")

    (
        quality_present,
        focused_executed,
        focused_passed,
        regression_executed,
        regression_passed,
    ) = _quality_booleans(record)

    if not quality_present:
        reasons.append("quality evidence absent")

    evidence = PatchQualityEvidence(
        format_supported=format_supported,
        lifecycle_ready=lifecycle_ready,
        compile_passed=compile_passed,
        semantic_approved=semantic_approved,
        workspace_policy_passed=workspace_policy_passed,
        target_scope_passed=target_scope_passed,
        artifact_integrity_passed=artifact_integrity_passed,
        behavioral_source_change=behavioral,
        focused_tests_required=behavioral,
        focused_tests_available=bool(focused_ids),
        focused_tests_executed=focused_executed,
        focused_tests_passed=focused_passed,
        regression_tests_required=bool(regression_ids),
        regression_tests_executed=regression_executed,
        regression_tests_passed=regression_passed,
        high_risk_boundary=_is_high_risk(target_file),
    )

    return PatchQualityEvidenceContext(
        evidence=evidence,
        focused_test_ids=focused_ids,
        regression_test_ids=regression_ids,
        reasons=tuple(reasons),
    )


def evaluate_patch_record_quality(
    record: Mapping[str, object],
    *,
    format_supported: bool,
    lifecycle_ready: bool,
    compile_passed: bool,
    semantic_approved: bool,
    workspace_policy_passed: bool,
    target_scope_passed: bool,
    artifact_integrity_passed: bool,
) -> tuple[PatchQualityEvidenceContext, PatchQualityGateResult]:
    context = build_patch_quality_evidence(
        record,
        format_supported=format_supported,
        lifecycle_ready=lifecycle_ready,
        compile_passed=compile_passed,
        semantic_approved=semantic_approved,
        workspace_policy_passed=workspace_policy_passed,
        target_scope_passed=target_scope_passed,
        artifact_integrity_passed=artifact_integrity_passed,
    )

    return context, evaluate_patch_quality(context.evidence)