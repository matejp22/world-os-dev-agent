from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.patch_quality_evidence_runner as evidence
from app.test_registry import (
    inspect_repository_test_registry,
    plan_test_selection,
)
from app.workspace_registry import get_workspace_profile


FOCUSED_TARGET_MODULES = ("app.patch_quality_evidence_runner",)

WORKSPACE = "world-os-web"
TARGET = "src/app/api/internal-preview/osm-geometry/route.ts"
TEST_ID = "web_osm_preview_contract"


def test_web_osm_exact_focused_selection() -> None:
    registry = inspect_repository_test_registry(WORKSPACE)

    for target in (TARGET, TARGET.replace("/", "\\")):
        plan = plan_test_selection(registry, (target,))
        assert plan.focused_test_ids == (TEST_ID,)
        assert plan.regression_test_ids == ()
        assert plan.executable is False


@pytest.mark.parametrize(
    "target",
    (
        "src/app/page.tsx",
        "src/components/GlobalMap.tsx",
        "package.json",
        "../" + TARGET,
    ),
)
def test_unrelated_web_paths_not_focused(target: str) -> None:
    registry = inspect_repository_test_registry(WORKSPACE)
    plan = plan_test_selection(registry, (target,))

    assert plan.focused_test_ids == ()
    assert plan.regression_test_ids == (TEST_ID,)
    assert plan.executable is False


def test_web_osm_evidence_executes_restricted_contract() -> None:
    profile = get_workspace_profile(WORKSPACE)
    assert profile.access_mode == "READ_ONLY"

    result = evidence.run_patch_quality_evidence(
        workspace_name=WORKSPACE,
        target_file=TARGET,
        timeout_seconds=60,
    )

    assert result.behavioral_source_change is True
    assert result.focused_test_ids == (TEST_ID,)
    assert result.regression_test_ids == ()
    assert result.focused_tests_executed is True
    assert result.focused_tests_passed is True
    assert result.regression_tests_executed is False
    assert result.execution_supported is True
    assert "no regression tests selected" in result.reasons


@pytest.mark.parametrize(
    "target",
    ("src/app/page.tsx", "src/components/GlobalMap.tsx", "package.json"),
)
def test_unrelated_web_evidence_not_executed(target: str) -> None:
    result = evidence.run_patch_quality_evidence(
        workspace_name=WORKSPACE,
        target_file=target,
    )

    assert result.behavioral_source_change is False
    assert result.focused_tests_executed is False
    assert result.focused_test_ids == ()


def test_web_candidate_overlay_is_blocked() -> None:
    result = evidence.run_patch_quality_evidence(
        workspace_name=WORKSPACE,
        target_file=TARGET,
        candidate_target_file=TARGET,
        candidate_file="unapproved_candidate.ts",
    )

    assert result.execution_supported is False
    assert result.focused_tests_executed is False
    assert any(
        "candidate-file execution is not permitted" in reason
        for reason in result.reasons
    )


def test_failed_focused_test_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = []

    def failing_executor(registry, test_ids, **kwargs):
        called.append((registry.workspace_name, test_ids))
        return SimpleNamespace(executed=True, passed=False)

    monkeypatch.setattr(
        evidence,
        "execute_registered_tests",
        failing_executor,
    )

    result = evidence.run_patch_quality_evidence(
        workspace_name=WORKSPACE,
        target_file=TARGET,
    )

    assert called == [(WORKSPACE, (TEST_ID,))]
    assert result.focused_tests_executed is True
    assert result.focused_tests_passed is False
    assert result.regression_tests_executed is False
    assert "focused tests executed and failed" in result.reasons
