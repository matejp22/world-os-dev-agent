from __future__ import annotations

from dataclasses import dataclass
from os import PathLike

from app.test_execution import (
    BLOCKED_TEST_IDS,
    execute_registered_tests,
)
from app.test_registry import (
    inspect_repository_test_registry,
    plan_test_selection,
)


@dataclass(frozen=True)
class PatchQualityExecutionResult:
    workspace_name: str
    target_file: str
    behavioral_source_change: bool
    focused_test_ids: tuple[str, ...]
    regression_test_ids: tuple[str, ...]
    focused_tests_executed: bool
    focused_tests_passed: bool
    regression_tests_executed: bool
    regression_tests_passed: bool
    execution_supported: bool
    reasons: tuple[str, ...]


def _validate_inputs(
    *,
    workspace_name: str,
    target_file: str,
    timeout_seconds: int,
) -> tuple[str, str]:
    if not isinstance(workspace_name, str) or not workspace_name.strip():
        raise ValueError("workspace_name must be a non-empty string.")

    if not isinstance(target_file, str) or not target_file.strip():
        raise ValueError("target_file must be a non-empty string.")

    if not isinstance(timeout_seconds, int):
        raise ValueError("timeout_seconds must be an integer.")

    if timeout_seconds < 1 or timeout_seconds > 300:
        raise ValueError(
            "timeout_seconds must be between 1 and 300."
        )

    return workspace_name.strip(), target_file.strip()


def _is_behavioral_source(target_file: str) -> bool:
    normalized = target_file.replace("\\", "/").strip().casefold()

    if not normalized.endswith(".py"):
        return False

    if not (
        normalized.startswith("app/")
        or normalized.startswith("scripts/")
    ):
        return False

    if normalized in {
        "app/test_execution.py",
        "app/test_registry.py",
    }:
        return True

    basename = normalized.rsplit("/", 1)[-1]
    return not basename.startswith("test_")


def _exception_reason(
    stage: str,
    exc: Exception,
) -> str:
    return (
        f"{stage} raised {type(exc).__name__}: {exc}"
    )


def _batch_failure_reason(
    stage: str,
) -> str:
    return (
        f"{stage} returned executed=False; "
        "execution evidence is unusable."
    )


def _result(
    *,
    workspace_name: str,
    target_file: str,
    behavioral_source_change: bool,
    focused_test_ids: tuple[str, ...],
    regression_test_ids: tuple[str, ...],
    focused_tests_executed: bool,
    focused_tests_passed: bool,
    regression_tests_executed: bool,
    regression_tests_passed: bool,
    execution_supported: bool,
    reasons: list[str],
) -> PatchQualityExecutionResult:
    return PatchQualityExecutionResult(
        workspace_name=workspace_name,
        target_file=target_file,
        behavioral_source_change=behavioral_source_change,
        focused_test_ids=focused_test_ids,
        regression_test_ids=regression_test_ids,
        focused_tests_executed=focused_tests_executed,
        focused_tests_passed=focused_tests_passed,
        regression_tests_executed=regression_tests_executed,
        regression_tests_passed=regression_tests_passed,
        execution_supported=execution_supported,
        reasons=tuple(reasons),
    )


def run_patch_quality_evidence(
    *,
    workspace_name: str,
    target_file: str,
    timeout_seconds: int = 60,
    candidate_target_file: str | None = None,
    candidate_file: str | PathLike[str] | None = None,
) -> PatchQualityExecutionResult:
    candidate_pair_supplied = (
        candidate_target_file is not None
        and candidate_file is not None
    )

    candidate_pair_missing = (
        candidate_target_file is None
        and candidate_file is None
    )

    if not (
        candidate_pair_supplied
        or candidate_pair_missing
    ):
        raise ValueError(
            "candidate_target_file and candidate_file "
            "must be supplied together."
        )

    workspace_name, target_file = _validate_inputs(
        workspace_name=workspace_name,
        target_file=target_file,
        timeout_seconds=timeout_seconds,
    )

    behavioral = _is_behavioral_source(target_file)

    if not behavioral:
        return _result(
            workspace_name=workspace_name,
            target_file=target_file,
            behavioral_source_change=False,
            focused_test_ids=(),
            regression_test_ids=(),
            focused_tests_executed=False,
            focused_tests_passed=False,
            regression_tests_executed=False,
            regression_tests_passed=False,
            execution_supported=True,
            reasons=[
                "Tests are not required for the target."
            ],
        )

    focused_ids: tuple[str, ...] = ()
    regression_ids: tuple[str, ...] = ()
    reasons: list[str] = []

    try:
        registry = inspect_repository_test_registry(
            workspace_name
        )
    except Exception as exc:
        return _result(
            workspace_name=workspace_name,
            target_file=target_file,
            behavioral_source_change=True,
            focused_test_ids=focused_ids,
            regression_test_ids=regression_ids,
            focused_tests_executed=False,
            focused_tests_passed=False,
            regression_tests_executed=False,
            regression_tests_passed=False,
            execution_supported=False,
            reasons=[
                _exception_reason(
                    "Test registry inspection",
                    exc,
                )
            ],
        )

    try:
        selection = plan_test_selection(
            registry,
            (target_file,),
        )
        focused_ids = selection.focused_test_ids
        regression_ids = tuple(
            test_id
            for test_id in selection.regression_test_ids
            if test_id not in BLOCKED_TEST_IDS
        )
    except Exception as exc:
        return _result(
            workspace_name=workspace_name,
            target_file=target_file,
            behavioral_source_change=True,
            focused_test_ids=focused_ids,
            regression_test_ids=regression_ids,
            focused_tests_executed=False,
            focused_tests_passed=False,
            regression_tests_executed=False,
            regression_tests_passed=False,
            execution_supported=False,
            reasons=[
                _exception_reason(
                    "Test selection",
                    exc,
                )
            ],
        )

    if not focused_ids:
        return _result(
            workspace_name=workspace_name,
            target_file=target_file,
            behavioral_source_change=True,
            focused_test_ids=focused_ids,
            regression_test_ids=regression_ids,
            focused_tests_executed=False,
            focused_tests_passed=False,
            regression_tests_executed=False,
            regression_tests_passed=False,
            execution_supported=True,
            reasons=[
                "no focused tests selected"
            ],
        )

    try:
        if candidate_pair_supplied:
            focused_batch = execute_registered_tests(
                registry,
                focused_ids,
                timeout_seconds=timeout_seconds,
                candidate_target_file=candidate_target_file,
                candidate_file=candidate_file,
            )
        else:
            focused_batch = execute_registered_tests(
                registry,
                focused_ids,
                timeout_seconds=timeout_seconds,
            )
    except Exception as exc:
        return _result(
            workspace_name=workspace_name,
            target_file=target_file,
            behavioral_source_change=True,
            focused_test_ids=focused_ids,
            regression_test_ids=regression_ids,
            focused_tests_executed=False,
            focused_tests_passed=False,
            regression_tests_executed=False,
            regression_tests_passed=False,
            execution_supported=False,
            reasons=[
                _exception_reason(
                    "Focused test execution",
                    exc,
                )
            ],
        )

    if focused_batch.executed is not True:
        return _result(
            workspace_name=workspace_name,
            target_file=target_file,
            behavioral_source_change=True,
            focused_test_ids=focused_ids,
            regression_test_ids=regression_ids,
            focused_tests_executed=False,
            focused_tests_passed=False,
            regression_tests_executed=False,
            regression_tests_passed=False,
            execution_supported=False,
            reasons=[
                _batch_failure_reason(
                    "Focused test execution"
                )
            ],
        )

    focused_passed = focused_batch.passed is True

    if not focused_passed:
        return _result(
            workspace_name=workspace_name,
            target_file=target_file,
            behavioral_source_change=True,
            focused_test_ids=focused_ids,
            regression_test_ids=regression_ids,
            focused_tests_executed=True,
            focused_tests_passed=False,
            regression_tests_executed=False,
            regression_tests_passed=False,
            execution_supported=True,
            reasons=[
                "focused tests executed and failed",
                "regression skipped because focused tests failed",
            ],
        )

    if not regression_ids:
        return _result(
            workspace_name=workspace_name,
            target_file=target_file,
            behavioral_source_change=True,
            focused_test_ids=focused_ids,
            regression_test_ids=regression_ids,
            focused_tests_executed=True,
            focused_tests_passed=True,
            regression_tests_executed=False,
            regression_tests_passed=False,
            execution_supported=True,
            reasons=[
                "no regression tests selected"
            ],
        )

    try:
        if candidate_pair_supplied:
            regression_batch = execute_registered_tests(
                registry,
                regression_ids,
                timeout_seconds=timeout_seconds,
                candidate_target_file=candidate_target_file,
                candidate_file=candidate_file,
            )
        else:
            regression_batch = execute_registered_tests(
                registry,
                regression_ids,
                timeout_seconds=timeout_seconds,
            )
    except Exception as exc:
        return _result(
            workspace_name=workspace_name,
            target_file=target_file,
            behavioral_source_change=True,
            focused_test_ids=focused_ids,
            regression_test_ids=regression_ids,
            focused_tests_executed=True,
            focused_tests_passed=True,
            regression_tests_executed=False,
            regression_tests_passed=False,
            execution_supported=False,
            reasons=[
                _exception_reason(
                    "Regression test execution",
                    exc,
                )
            ],
        )

    if regression_batch.executed is not True:
        return _result(
            workspace_name=workspace_name,
            target_file=target_file,
            behavioral_source_change=True,
            focused_test_ids=focused_ids,
            regression_test_ids=regression_ids,
            focused_tests_executed=True,
            focused_tests_passed=True,
            regression_tests_executed=False,
            regression_tests_passed=False,
            execution_supported=False,
            reasons=[
                _batch_failure_reason(
                    "Regression test execution"
                )
            ],
        )

    return _result(
        workspace_name=workspace_name,
        target_file=target_file,
        behavioral_source_change=True,
        focused_test_ids=focused_ids,
        regression_test_ids=regression_ids,
        focused_tests_executed=True,
        focused_tests_passed=True,
        regression_tests_executed=True,
        regression_tests_passed=regression_batch.passed is True,
        execution_supported=True,
        reasons=[
            (
                "regression tests executed and passed"
                if regression_batch.passed is True
                else "regression tests executed and failed"
            )
        ],
    )


def quality_evidence_payload(
    result: PatchQualityExecutionResult,
) -> dict[str, bool]:
    if not isinstance(
        result,
        PatchQualityExecutionResult,
    ):
        raise TypeError(
            "result must be a PatchQualityExecutionResult instance."
        )

    return {
        "focused_tests_executed": result.focused_tests_executed,
        "focused_tests_passed": result.focused_tests_passed,
        "regression_tests_executed": result.regression_tests_executed,
        "regression_tests_passed": result.regression_tests_passed,
    }