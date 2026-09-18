from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable, TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import app.patch_quality_evidence_runner


_BOOTSTRAP_ENV = "WORLD_OS_PATCH_QUALITY_EVIDENCE_RUNNER_CANDIDATE"
_CANONICAL_MODULE = "app.patch_quality_evidence_runner"


def _load_runner_module() -> ModuleType:
    try:
        return importlib.import_module(_CANONICAL_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name != _CANONICAL_MODULE:
            raise

    candidate_value = os.environ.get(
        _BOOTSTRAP_ENV,
        "",
    ).strip()

    if not candidate_value:
        raise RuntimeError(
            "Canonical patch quality evidence runner is absent and "
            f"{_BOOTSTRAP_ENV} was not supplied."
        )

    candidate = Path(candidate_value).resolve()

    if not candidate.exists():
        raise RuntimeError(
            f"Bootstrap candidate does not exist: {candidate}"
        )

    if not candidate.is_file():
        raise RuntimeError(
            f"Bootstrap candidate is not a file: {candidate}"
        )

    if candidate.suffix.lower() != ".py":
        raise RuntimeError(
            "Bootstrap candidate must be a Python file."
        )

    spec = importlib.util.spec_from_file_location(
        "_world_os_patch_quality_evidence_runner_candidate",
        candidate,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Unable to create bootstrap module specification."
        )

    module = importlib.util.module_from_spec(spec)

    sys.modules[spec.name] = module

    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise

    return module


@pytest.fixture
def runner_module() -> ModuleType:
    return _load_runner_module()


@dataclass(frozen=True)
class RegistryStub:
    name: str = "registry"


@dataclass(frozen=True)
class BatchStub:
    workspace_name: str
    requested_test_ids: tuple[str, ...]
    results: tuple[object, ...]
    passed: bool
    executed: bool
    reason: str


@dataclass(frozen=True)
class SelectionStub:
    focused_test_ids: tuple[str, ...]
    regression_test_ids: tuple[str, ...]


def _install_mocks(
    monkeypatch: pytest.MonkeyPatch,
    runner_module: ModuleType,
    *,
    registry: RegistryStub,
    selection: SelectionStub,
    batch_factory: Callable[[tuple[str, ...]], BatchStub] | None = None,
) -> tuple[
    list[tuple[object, tuple[str, ...]]],
    list[tuple[object, tuple[str, ...], int, BatchStub]],
]:
    selection_calls: list[tuple[object, tuple[str, ...]]] = []
    executor_calls: list[
        tuple[object, tuple[str, ...], int, BatchStub]
    ] = []

    def fake_inspect(workspace_name: str) -> RegistryStub:
        assert workspace_name == "world-os-dev-agent"
        return registry

    def fake_select(
        registry_arg: object,
        changed_files_arg: tuple[str, ...],
    ) -> SelectionStub:
        selection_calls.append((registry_arg, changed_files_arg))
        return selection

    def fake_execute(
        registry_arg: object,
        test_ids_arg: tuple[str, ...],
        *,
        timeout_seconds: int,
    ) -> BatchStub:
        batch = (
            batch_factory(test_ids_arg)
            if batch_factory is not None
            else BatchStub(
                workspace_name="world-os-dev-agent",
                requested_test_ids=test_ids_arg,
                results=(),
                passed=True,
                executed=True,
                reason="ok",
            )
        )
        assert batch.requested_test_ids == test_ids_arg
        executor_calls.append(
            (registry_arg, test_ids_arg, timeout_seconds, batch)
        )
        return batch

    monkeypatch.setattr(
        runner_module,
        "inspect_repository_test_registry",
        fake_inspect,
    )
    monkeypatch.setattr(
        runner_module,
        "plan_test_selection",
        fake_select,
    )
    monkeypatch.setattr(
        runner_module,
        "execute_registered_tests",
        fake_execute,
    )
    return selection_calls, executor_calls


def _assert_no_execution(result: object) -> None:
    assert result.focused_tests_executed is False
    assert result.focused_tests_passed is False
    assert result.regression_tests_executed is False
    assert result.regression_tests_passed is False


def test_non_behavioral_target_requires_no_execution(
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,) -> None:
    calls = {"inspect": 0, "selection": 0, "executor": 0}

    monkeypatch.setattr(
        runner_module,
        "inspect_repository_test_registry",
        lambda _workspace: calls.__setitem__("inspect", calls["inspect"] + 1),
    )
    monkeypatch.setattr(
        runner_module,
        "plan_test_selection",
        lambda _registry, _files: calls.__setitem__(
            "selection", calls["selection"] + 1
        ),
    )
    monkeypatch.setattr(
        runner_module,
        "execute_registered_tests",
        lambda _registry, _ids, *, timeout_seconds: calls.__setitem__(
            "executor", calls["executor"] + 1
        ),
    )

    result = runner_module.run_patch_quality_evidence(workspace_name="world-os-dev-agent", target_file="app/test_example.py")

    assert result.behavioral_source_change is False
    assert result.execution_supported is True
    assert result.focused_test_ids == ()
    assert result.regression_test_ids == ()
    _assert_no_execution(result)
    assert calls == {"inspect": 0, "selection": 0, "executor": 0}


def test_behavioral_target_without_focused_tests_fails_closed(
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,) -> None:
    registry = RegistryStub()
    selection_calls, executor_calls = _install_mocks(
        monkeypatch,
        runner_module,
        registry=registry,
        selection=SelectionStub((), ("test_alpha",)),
    )

    result = runner_module.run_patch_quality_evidence(workspace_name="world-os-dev-agent", target_file="app/example.py")

    assert selection_calls == [(registry, ("app/example.py",))]
    assert executor_calls == []
    assert result.behavioral_source_change is True
    assert result.execution_supported is True
    assert result.focused_test_ids == ()
    assert result.regression_test_ids == ("test_alpha",)
    _assert_no_execution(result)
    assert any("no focused tests selected" in r for r in result.reasons)


def test_focused_pass_without_regression(
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,) -> None:
    registry = RegistryStub()
    selection_calls, executor_calls = _install_mocks(
        monkeypatch,
        runner_module,
        registry=registry,
        selection=SelectionStub(("test_focus",), ()),
    )

    result = runner_module.run_patch_quality_evidence(workspace_name="world-os-dev-agent", target_file="app/example.py", timeout_seconds=37)

    assert selection_calls == [(registry, ("app/example.py",))]
    assert [
        (item[0], item[1], item[2]) for item in executor_calls
    ] == [(registry, ("test_focus",), 37)]
    assert executor_calls[0][3].requested_test_ids == ("test_focus",)
    assert result.behavioral_source_change is True
    assert result.execution_supported is True
    assert result.focused_tests_executed is True
    assert result.focused_tests_passed is True
    assert result.regression_tests_executed is False
    assert result.regression_tests_passed is False
    assert any("no regression tests selected" in r for r in result.reasons)



def test_candidate_overlay_forwarded_to_focused_execution(
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry = RegistryStub()

    selection_calls: list[
        tuple[object, tuple[str, ...]]
    ] = []

    executor_calls: list[
        tuple[
            object,
            tuple[str, ...],
            int,
            str | None,
            object | None,
        ]
    ] = []

    candidate_file = tmp_path / "candidate.py"
    candidate_file.write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    def fake_inspect(
        workspace_name: str,
    ) -> RegistryStub:
        assert workspace_name == "world-os-dev-agent"
        return registry

    def fake_select(
        registry_arg: object,
        changed_files_arg: tuple[str, ...],
    ) -> SelectionStub:
        selection_calls.append(
            (registry_arg, changed_files_arg)
        )
        return SelectionStub(
            ("test_focus",),
            (),
        )

    def fake_execute(
        registry_arg: object,
        test_ids_arg: tuple[str, ...],
        *,
        timeout_seconds: int,
        candidate_target_file: str | None = None,
        candidate_file: object | None = None,
    ) -> BatchStub:
        executor_calls.append(
            (
                registry_arg,
                test_ids_arg,
                timeout_seconds,
                candidate_target_file,
                candidate_file,
            )
        )

        return BatchStub(
            workspace_name="world-os-dev-agent",
            requested_test_ids=test_ids_arg,
            results=(),
            passed=True,
            executed=True,
            reason="ok",
        )

    monkeypatch.setattr(
        runner_module,
        "inspect_repository_test_registry",
        fake_inspect,
    )
    monkeypatch.setattr(
        runner_module,
        "plan_test_selection",
        fake_select,
    )
    monkeypatch.setattr(
        runner_module,
        "execute_registered_tests",
        fake_execute,
    )

    result = runner_module.run_patch_quality_evidence(
        workspace_name="world-os-dev-agent",
        target_file="app/example.py",
        timeout_seconds=37,
        candidate_target_file="app/example.py",
        candidate_file=candidate_file,
    )

    assert selection_calls == [
        (registry, ("app/example.py",))
    ]

    assert executor_calls == [
        (
            registry,
            ("test_focus",),
            37,
            "app/example.py",
            candidate_file,
        )
    ]

    assert result.behavioral_source_change is True
    assert result.execution_supported is True
    assert result.focused_test_ids == ("test_focus",)
    assert result.regression_test_ids == ()
    assert result.focused_tests_executed is True
    assert result.focused_tests_passed is True
    assert result.regression_tests_executed is False
    assert result.regression_tests_passed is False


def test_candidate_overlay_forwarded_to_focused_and_regression_execution(
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry = RegistryStub()

    selection_calls: list[
        tuple[object, tuple[str, ...]]
    ] = []

    executor_calls: list[
        tuple[
            object,
            tuple[str, ...],
            int,
            str | None,
            object | None,
        ]
    ] = []

    candidate_file = tmp_path / "candidate.py"
    candidate_file.write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    def fake_inspect(
        workspace_name: str,
    ) -> RegistryStub:
        assert workspace_name == "world-os-dev-agent"
        return registry

    def fake_select(
        registry_arg: object,
        changed_files_arg: tuple[str, ...],
    ) -> SelectionStub:
        selection_calls.append(
            (registry_arg, changed_files_arg)
        )
        return SelectionStub(
            ("test_focus",),
            ("test_regression",),
        )

    def fake_execute(
        registry_arg: object,
        test_ids_arg: tuple[str, ...],
        *,
        timeout_seconds: int,
        candidate_target_file: str | None = None,
        candidate_file: object | None = None,
    ) -> BatchStub:
        executor_calls.append(
            (
                registry_arg,
                test_ids_arg,
                timeout_seconds,
                candidate_target_file,
                candidate_file,
            )
        )

        return BatchStub(
            workspace_name="world-os-dev-agent",
            requested_test_ids=test_ids_arg,
            results=(),
            passed=True,
            executed=True,
            reason="ok",
        )

    monkeypatch.setattr(
        runner_module,
        "inspect_repository_test_registry",
        fake_inspect,
    )
    monkeypatch.setattr(
        runner_module,
        "plan_test_selection",
        fake_select,
    )
    monkeypatch.setattr(
        runner_module,
        "execute_registered_tests",
        fake_execute,
    )

    result = runner_module.run_patch_quality_evidence(
        workspace_name="world-os-dev-agent",
        target_file="app/example.py",
        timeout_seconds=37,
        candidate_target_file="app/example.py",
        candidate_file=candidate_file,
    )

    assert selection_calls == [
        (registry, ("app/example.py",))
    ]

    assert executor_calls == [
        (
            registry,
            ("test_focus",),
            37,
            "app/example.py",
            candidate_file,
        ),
        (
            registry,
            ("test_regression",),
            37,
            "app/example.py",
            candidate_file,
        ),
    ]

    assert result.behavioral_source_change is True
    assert result.execution_supported is True
    assert result.focused_test_ids == ("test_focus",)
    assert result.regression_test_ids == (
        "test_regression",
    )
    assert result.focused_tests_executed is True
    assert result.focused_tests_passed is True
    assert result.regression_tests_executed is True
    assert result.regression_tests_passed is True


def test_focused_failure_skips_regression(
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,) -> None:
    registry = RegistryStub()
    selection_calls, executor_calls = _install_mocks(
        monkeypatch,
        runner_module,
        registry=registry,
        selection=SelectionStub(("test_focus",), ("test_regression",)),
        batch_factory=lambda ids: BatchStub(
            "world-os-dev-agent", ids, (), False, True, "failed"
        ),
    )

    result = runner_module.run_patch_quality_evidence(workspace_name="world-os-dev-agent", target_file="app/example.py")

    assert selection_calls == [(registry, ("app/example.py",))]
    assert [
        (item[0], item[1], item[2]) for item in executor_calls
    ] == [(registry, ("test_focus",), 60)]
    assert result.behavioral_source_change is True
    assert result.execution_supported is True
    assert result.focused_tests_executed is True
    assert result.focused_tests_passed is False
    assert result.regression_tests_executed is False
    assert result.regression_tests_passed is False
    assert any("regression" in r.lower() and "skip" in r.lower() for r in result.reasons)


def test_focused_executed_false_is_unsupported(
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,) -> None:
    registry = RegistryStub()
    selection_calls, executor_calls = _install_mocks(
        monkeypatch,
        runner_module,
        registry=registry,
        selection=SelectionStub(("test_focus",), ()),
        batch_factory=lambda ids: BatchStub(
            "world-os-dev-agent", ids, (), True, False, "not executed"
        ),
    )

    result = runner_module.run_patch_quality_evidence(workspace_name="world-os-dev-agent", target_file="app/example.py")

    assert selection_calls == [(registry, ("app/example.py",))]
    assert executor_calls[0][3].requested_test_ids == ("test_focus",)
    assert result.behavioral_source_change is True
    assert result.execution_supported is False
    _assert_no_execution(result)


def test_focused_executor_exception_is_structured(
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,) -> None:
    registry = RegistryStub()
    selection_calls: list[tuple[object, tuple[str, ...]]] = []
    executor_calls: list[tuple[object, tuple[str, ...], int]] = []

    def fake_inspect(_workspace: str) -> RegistryStub:
        return registry

    def fake_select(
        registry_arg: object,
        changed_files_arg: tuple[str, ...],
    ) -> SelectionStub:
        selection_calls.append((registry_arg, changed_files_arg))
        return SelectionStub(("test_focus",), ())

    def fake_execute(
        registry_arg: object,
        test_ids_arg: tuple[str, ...],
        *,
        timeout_seconds: int,
    ) -> BatchStub:
        executor_calls.append((registry_arg, test_ids_arg, timeout_seconds))
        raise RuntimeError("execution rejected")

    monkeypatch.setattr(
        runner_module,
        "inspect_repository_test_registry",
        fake_inspect,
    )
    monkeypatch.setattr(
        runner_module,
        "plan_test_selection",
        fake_select,
    )
    monkeypatch.setattr(
        runner_module,
        "execute_registered_tests",
        fake_execute,
    )

    result = runner_module.run_patch_quality_evidence(workspace_name="world-os-dev-agent", target_file="app/example.py")

    assert isinstance(result, runner_module.PatchQualityExecutionResult)
    assert selection_calls == [(registry, ("app/example.py",))]
    assert executor_calls == [(registry, ("test_focus",), 60)]
    assert result.behavioral_source_change is True
    assert result.execution_supported is False
    _assert_no_execution(result)
    assert any("RuntimeError" in r and "execution rejected" in r for r in result.reasons)


def test_focused_and_regression_pass(
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,) -> None:
    registry = RegistryStub()
    selection_calls, executor_calls = _install_mocks(
        monkeypatch,
        runner_module,
        registry=registry,
        selection=SelectionStub(("test_focus",), ("test_regression",)),
    )

    result = runner_module.run_patch_quality_evidence(workspace_name="world-os-dev-agent", target_file="app/example.py", timeout_seconds=37)

    assert selection_calls == [(registry, ("app/example.py",))]
    assert [
        (item[0], item[1], item[2]) for item in executor_calls
    ] == [
        (registry, ("test_focus",), 37),
        (registry, ("test_regression",), 37),
    ]
    assert [item[3].requested_test_ids for item in executor_calls] == [
        ("test_focus",),
        ("test_regression",),
    ]
    assert result.behavioral_source_change is True
    assert result.execution_supported is True
    assert result.focused_tests_executed is True
    assert result.focused_tests_passed is True
    assert result.regression_tests_executed is True
    assert result.regression_tests_passed is True


def test_regression_failure_preserves_focused_pass(
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,) -> None:
    registry = RegistryStub()
    selection_calls, executor_calls = _install_mocks(
        monkeypatch,
        runner_module,
        registry=registry,
        selection=SelectionStub(("test_focus",), ("test_regression",)),
        batch_factory=lambda ids: BatchStub(
            "world-os-dev-agent", ids, (), ids == ("test_focus",), True, "ok"
        ),
    )

    result = runner_module.run_patch_quality_evidence(workspace_name="world-os-dev-agent", target_file="app/example.py")

    assert selection_calls == [(registry, ("app/example.py",))]
    assert len(executor_calls) == 2
    assert executor_calls[0][3].requested_test_ids == ("test_focus",)
    assert executor_calls[1][3].requested_test_ids == ("test_regression",)
    assert result.behavioral_source_change is True
    assert result.execution_supported is True
    assert result.focused_tests_executed is True
    assert result.focused_tests_passed is True
    assert result.regression_tests_executed is True
    assert result.regression_tests_passed is False


def test_regression_executed_false_is_unsupported(
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,) -> None:
    registry = RegistryStub()
    selection_calls, executor_calls = _install_mocks(
        monkeypatch,
        runner_module,
        registry=registry,
        selection=SelectionStub(("test_focus",), ("test_regression",)),
        batch_factory=lambda ids: BatchStub(
            "world-os-dev-agent",
            ids,
            (),
            True,
            ids == ("test_focus",),
            "ok",
        ),
    )

    result = runner_module.run_patch_quality_evidence(workspace_name="world-os-dev-agent", target_file="app/example.py")

    assert selection_calls == [(registry, ("app/example.py",))]
    assert len(executor_calls) == 2
    assert result.behavioral_source_change is True
    assert result.execution_supported is False
    assert result.focused_tests_executed is True
    assert result.focused_tests_passed is True
    assert result.regression_tests_executed is False
    assert result.regression_tests_passed is False


def test_registry_failure_returns_structured_evidence(
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,) -> None:
    calls = {"selection": 0, "executor": 0}

    monkeypatch.setattr(
        runner_module,
        "inspect_repository_test_registry",
        lambda _workspace: (_ for _ in ()).throw(
            RuntimeError("registry failed")
        ),
    )
    monkeypatch.setattr(
        runner_module,
        "plan_test_selection",
        lambda *_args: calls.__setitem__("selection", calls["selection"] + 1),
    )
    monkeypatch.setattr(
        runner_module,
        "execute_registered_tests",
        lambda *_args, **_kwargs: calls.__setitem__(
            "executor", calls["executor"] + 1
        ),
    )

    result = runner_module.run_patch_quality_evidence(workspace_name="world-os-dev-agent", target_file="app/example.py")

    assert isinstance(result, runner_module.PatchQualityExecutionResult)
    assert result.behavioral_source_change is True
    assert result.execution_supported is False
    _assert_no_execution(result)
    assert any("RuntimeError" in r and "registry failed" in r for r in result.reasons)
    assert calls == {"selection": 0, "executor": 0}


def test_selection_failure_returns_structured_evidence(
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,) -> None:
    registry = RegistryStub()
    selection_calls: list[tuple[object, tuple[str, ...]]] = []
    executor_calls = 0

    def fake_inspect(_workspace: str) -> RegistryStub:
        return registry

    def fake_select(
        registry_arg: object,
        changed_files_arg: tuple[str, ...],
    ) -> SelectionStub:
        selection_calls.append((registry_arg, changed_files_arg))
        raise RuntimeError("selection failed")

    def fake_execute(*_args, **_kwargs) -> None:
        nonlocal executor_calls
        executor_calls += 1
        raise AssertionError("executor must not be called")

    monkeypatch.setattr(
        runner_module,
        "inspect_repository_test_registry",
        fake_inspect,
    )
    monkeypatch.setattr(
        runner_module,
        "plan_test_selection",
        fake_select,
    )
    monkeypatch.setattr(
        runner_module,
        "execute_registered_tests",
        fake_execute,
    )

    result = runner_module.run_patch_quality_evidence(workspace_name="world-os-dev-agent", target_file="app/example.py")

    assert selection_calls == [(registry, ("app/example.py",))]
    assert executor_calls == 0
    assert result.behavioral_source_change is True
    assert result.execution_supported is False
    _assert_no_execution(result)
    assert any("RuntimeError" in r and "selection failed" in r for r in result.reasons)


def test_quality_evidence_payload_exact_shape(
    runner_module: ModuleType,
) -> None:
    result = runner_module.PatchQualityExecutionResult(
        workspace_name="world-os-dev-agent",
        target_file="app/example.py",
        behavioral_source_change=True,
        execution_supported=True,
        focused_test_ids=("test_focus",),
        regression_test_ids=("test_regression",),
        focused_tests_executed=True,
        focused_tests_passed=False,
        regression_tests_executed=True,
        regression_tests_passed=True,
        reasons=("example",),
    )

    payload = runner_module.quality_evidence_payload(result)

    assert payload == {
        "focused_tests_executed": True,
        "focused_tests_passed": False,
        "regression_tests_executed": True,
        "regression_tests_passed": True,
    }
    assert set(payload) == {
        "focused_tests_executed",
        "focused_tests_passed",
        "regression_tests_executed",
        "regression_tests_passed",
    }


def test_input_validation(
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = {"inspect": 0, "selection": 0, "executor": 0}

    monkeypatch.setattr(
        runner_module,
        "inspect_repository_test_registry",
        lambda _workspace: calls.__setitem__("inspect", calls["inspect"] + 1),
    )
    monkeypatch.setattr(
        runner_module,
        "plan_test_selection",
        lambda _registry, _files: calls.__setitem__(
            "selection", calls["selection"] + 1
        ),
    )
    monkeypatch.setattr(
        runner_module,
        "execute_registered_tests",
        lambda _registry, _ids, *, timeout_seconds: calls.__setitem__(
            "executor", calls["executor"] + 1
        ),
    )

    candidate_file = tmp_path / "candidate.py"
    candidate_file.write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    invalid_calls = (
        lambda: runner_module.run_patch_quality_evidence(workspace_name="", target_file="app/example.py"),
        lambda: runner_module.run_patch_quality_evidence(workspace_name="world-os-dev-agent", target_file=""),
        lambda: runner_module.run_patch_quality_evidence(workspace_name="world-os-dev-agent", target_file="app/example.py", timeout_seconds=0),
        lambda: runner_module.run_patch_quality_evidence(workspace_name="world-os-dev-agent", target_file="app/example.py", timeout_seconds=301),
        lambda: runner_module.run_patch_quality_evidence(workspace_name="world-os-dev-agent", target_file="app/example.py", timeout_seconds="60"),
        lambda: runner_module.run_patch_quality_evidence(
            workspace_name="world-os-dev-agent",
            target_file="app/example.py",
            candidate_target_file="app/example.py",
            candidate_file=None,
        ),
        lambda: runner_module.run_patch_quality_evidence(
            workspace_name="world-os-dev-agent",
            target_file="app/example.py",
            candidate_target_file=None,
            candidate_file=candidate_file,
        ),
    )

    for invalid_call in invalid_calls:
        with pytest.raises(ValueError):
            invalid_call()

    assert calls == {"inspect": 0, "selection": 0, "executor": 0}