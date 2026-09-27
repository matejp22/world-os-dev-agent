from importlib import util
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


FOCUSED_TARGET_MODULES = (
    "app.continue_milestone_runner",
)


@pytest.fixture
def implementation_module():
    candidate_value = os.environ.get(
        "WORLD_OS_CONTINUE_MILESTONE_RUNNER_CANDIDATE"
    )

    if not candidate_value:
        import app.continue_milestone_runner as module

        yield module
        return

    candidate_path = Path(candidate_value).expanduser().resolve()

    if not candidate_path.exists():
        pytest.fail(
            f"Candidate path does not exist: {candidate_path}"
        )

    if not candidate_path.is_file():
        pytest.fail(
            f"Candidate path is not a regular file: {candidate_path}"
        )

    if candidate_path.suffix.casefold() != ".py":
        pytest.fail(
            f"Candidate path is not a Python file: {candidate_path}"
        )

    module_name = "app.continue_milestone_runner"
    previous = sys.modules.get(module_name)

    spec = util.spec_from_file_location(
        module_name,
        candidate_path,
    )

    if spec is None or spec.loader is None:
        pytest.fail(
            f"Unable to create candidate module spec: {candidate_path}"
        )

    module = util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous


def _install_proceed_path(monkeypatch, module, events):
    workspace = SimpleNamespace(
        name="world-os-dev-agent",
        path=module.PROJECT_ROOT,
    )
    selection = SimpleNamespace(
        workspace=workspace,
    )

    state = SimpleNamespace(
        status="ACTIVE",
        milestone="test milestone",
        objective="test objective",
        previous_milestone=None,
    )
    resolution = SimpleNamespace(
        decision="TEST",
        state=state,
    )
    transition_plan = SimpleNamespace(
        action="NO_WRITE",
        decision="TEST",
        reason="test",
    )
    transition_execution = SimpleNamespace(
        persisted=False,
    )
    autonomy = SimpleNamespace(
        decision="PROCEED",
        reason="test",
        task_plan=None,
        coordination_plan=None,
    )

    monkeypatch.setattr(
        module,
        "active_workspace_from_path",
        lambda path: selection,
    )
    monkeypatch.setattr(
        module,
        "_print_workspace_context",
        lambda selection: None,
    )
    monkeypatch.setattr(
        module,
        "load_resolved_task_state",
        lambda workspace_name: resolution,
    )
    monkeypatch.setattr(
        module,
        "plan_task_state_transition",
        lambda resolution: transition_plan,
    )
    monkeypatch.setattr(
        module,
        "execute_task_state_transition",
        lambda plan, workspace_name=None: transition_execution,
    )

    def evaluate_production_autonomy(**kwargs):
        events.append("gate")
        return autonomy

    monkeypatch.setattr(
        module,
        "evaluate_production_autonomy",
        evaluate_production_autonomy,
    )


def test_focused_target_modules():
    assert FOCUSED_TARGET_MODULES == (
        "app.continue_milestone_runner",
    )


def test_candidate_first_isolation(implementation_module):
    candidate_value = os.environ.get(
        "WORLD_OS_CONTINUE_MILESTONE_RUNNER_CANDIDATE"
    )

    if candidate_value:
        candidate_path = Path(candidate_value).expanduser().resolve()

        assert (
            Path(implementation_module.__file__).resolve()
            == candidate_path
        )
        assert (
            sys.modules["app.continue_milestone_runner"]
            is implementation_module
        )
    else:
        assert implementation_module.__name__ == (
            "app.continue_milestone_runner"
        )


def test_recovery_helper(implementation_module, monkeypatch):
    helper = getattr(
        implementation_module,
        "_run_data_file_recovery_preflight",
        None,
    )

    if helper is None:
        pytest.skip(
            "recovery integration is not canonically installed yet"
        )

    calls = []
    sentinel = ("recovered",)

    def recovery_cycle(**kwargs):
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(
        implementation_module,
        "run_data_file_recovery_cycle",
        recovery_cycle,
    )

    result = helper()

    assert len(calls) == 1
    assert calls[0] == {
        "queue_dir": (
            implementation_module.PROJECT_ROOT
            / "pending_patches"
        ),
    }
    assert result is sentinel


def test_proceed_ordering(implementation_module, monkeypatch):
    if not hasattr(
        implementation_module,
        "_run_data_file_recovery_preflight",
    ):
        pytest.skip(
            "recovery integration is not canonically installed yet"
        )

    events = []
    _install_proceed_path(
        monkeypatch,
        implementation_module,
        events,
    )

    def recovery():
        events.append("recovery")
        return ()

    def build_cycle(**kwargs):
        events.append("build")
        return (
            "test objective",
            SimpleNamespace(
                status="READY_FOR_HUMAN_REVIEW",
            ),
        )

    monkeypatch.setattr(
        implementation_module,
        "_run_data_file_recovery_preflight",
        recovery,
    )
    monkeypatch.setattr(
        implementation_module,
        "_run_bounded_build_cycle",
        build_cycle,
    )

    result = implementation_module.run_continue_milestone(
        "test instruction",
        target_repository=implementation_module.PROJECT_ROOT,
    )

    assert result == 0
    assert events == [
        "gate",
        "recovery",
        "build",
    ]


def test_recovery_failure_fails_closed(
    implementation_module,
    monkeypatch,
):
    if not hasattr(
        implementation_module,
        "_run_data_file_recovery_preflight",
    ):
        pytest.skip(
            "recovery integration is not canonically installed yet"
        )

    events = []
    _install_proceed_path(
        monkeypatch,
        implementation_module,
        events,
    )

    def recovery():
        events.append("recovery")
        raise RuntimeError("RECOVERY_FAILURE")

    def build_cycle(**kwargs):
        events.append("build")
        return (
            "test objective",
            SimpleNamespace(
                status="READY_FOR_HUMAN_REVIEW",
            ),
        )

    monkeypatch.setattr(
        implementation_module,
        "_run_data_file_recovery_preflight",
        recovery,
    )
    monkeypatch.setattr(
        implementation_module,
        "_run_bounded_build_cycle",
        build_cycle,
    )

    result = implementation_module.run_continue_milestone(
        "Continue the current milestone through the bounded "
        "human-controlled development workflow.",
        target_repository=implementation_module.PROJECT_ROOT,
    )

    assert result != 0
    assert events == [
        "gate",
        "recovery",
    ]