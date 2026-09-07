from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.test_registry import (
    RepositoryTestRegistry,
    TestSelectionPlan,
)
from app.workspace_registry import (
    get_workspace_profile,
)


@dataclass(frozen=True)
class CompileCheckPlan:
    workspace_name: str
    workspace_path: str
    changed_python_targets: tuple[str, ...]
    focused_test_targets: tuple[str, ...]
    compile_targets: tuple[str, ...]
    executable: bool
    reason: str


@dataclass(frozen=True)
class CompileTargetResult:
    target: str
    passed: bool
    error_type: str | None
    error_message: str | None


@dataclass(frozen=True)
class CompileCheckResult:
    workspace_name: str
    targets: tuple[CompileTargetResult, ...]
    passed: bool
    executed: bool
    reason: str


def _normalize_relative_python_path(
    path: str,
) -> str | None:
    normalized = (
        path
        .replace("\\", "/")
        .strip()
    )

    parts = tuple(
        part
        for part in normalized.split("/")
        if part
    )

    if normalized.startswith("/"):
        raise RuntimeError(
            f"Unsafe compile target path: {path!r}"
        )

    if ".." in parts:
        raise RuntimeError(
            f"Unsafe compile target path: {path!r}"
        )

    if not normalized.startswith("app/"):
        return None

    if not normalized.endswith(".py"):
        return None

    return normalized


def plan_compile_checks(
    workspace_name: str,
    registry: RepositoryTestRegistry,
    selection: TestSelectionPlan,
    changed_files: tuple[str, ...],
) -> CompileCheckPlan:
    if not registry.inspected:
        raise RuntimeError(
            "Test registry must be inspected before compile planning."
        )

    if registry.workspace_name != workspace_name:
        raise RuntimeError(
            "Registry workspace does not match requested workspace."
        )

    if selection.executable is not False:
        raise RuntimeError(
            "Test selection plan must remain non-executing."
        )

    if not changed_files:
        raise RuntimeError(
            "changed_files must not be empty."
        )

    workspace = get_workspace_profile(
        workspace_name
    )

    changed_python_targets = {
        normalized
        for path in changed_files
        for normalized in (
            _normalize_relative_python_path(path),
        )
        if normalized is not None
    }

    registry_by_id = {
        entry.test_id: entry
        for entry in registry.tests
    }

    focused_test_targets: set[str] = set()

    for test_id in selection.focused_test_ids:
        entry = registry_by_id.get(test_id)

        if entry is None:
            raise RuntimeError(
                f"Focused test is not present in registry: {test_id}"
            )

        focused_test_targets.add(
            entry.compile_target
        )

    ordered_changed = tuple(
        sorted(
            changed_python_targets,
            key=str.casefold,
        )
    )

    ordered_focused = tuple(
        sorted(
            focused_test_targets,
            key=str.casefold,
        )
    )

    compile_targets = tuple(
        sorted(
            changed_python_targets
            | focused_test_targets,
            key=str.casefold,
        )
    )

    for relative in compile_targets:
        absolute = workspace.path / relative

        if not absolute.exists():
            raise RuntimeError(
                f"Compile target does not exist: {relative}"
            )

        if not absolute.is_file():
            raise RuntimeError(
                f"Compile target is not a file: {relative}"
            )

    return CompileCheckPlan(
        workspace_name=workspace.name,
        workspace_path=str(workspace.path),
        changed_python_targets=ordered_changed,
        focused_test_targets=ordered_focused,
        compile_targets=compile_targets,
        executable=False,
        reason=(
            "Deterministic non-executing compile-check plan. "
            "Targets include changed app Python files and focused "
            "test compile targets. No compile command, test, CI, "
            "Git, or repository mutation was executed."
        ),
    )

def execute_compile_checks(
    plan: CompileCheckPlan,
) -> CompileCheckResult:
    if plan.executable is not False:
        raise RuntimeError(
            "CompileCheckPlan must be non-executing before safe execution."
        )

    workspace = get_workspace_profile(
        plan.workspace_name
    )

    if str(workspace.path) != plan.workspace_path:
        raise RuntimeError(
            "CompileCheckPlan workspace path does not match registry."
        )

    results: list[CompileTargetResult] = []

    for relative in plan.compile_targets:
        normalized = _normalize_relative_python_path(
            relative
        )

        if normalized is None:
            raise RuntimeError(
                f"Compile target is not an app Python file: {relative}"
            )

        absolute = workspace.path / normalized

        if not absolute.exists():
            raise RuntimeError(
                f"Compile target does not exist: {normalized}"
            )

        if not absolute.is_file():
            raise RuntimeError(
                f"Compile target is not a file: {normalized}"
            )

        try:
            source = absolute.read_text(
                encoding="utf-8-sig"
            )

            compile(
                source,
                str(absolute),
                "exec",
            )

        except SyntaxError as exc:
            results.append(
                CompileTargetResult(
                    target=normalized,
                    passed=False,
                    error_type="SyntaxError",
                    error_message=str(exc),
                )
            )

        except UnicodeError as exc:
            results.append(
                CompileTargetResult(
                    target=normalized,
                    passed=False,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )

        else:
            results.append(
                CompileTargetResult(
                    target=normalized,
                    passed=True,
                    error_type=None,
                    error_message=None,
                )
            )

    ordered_results = tuple(results)

    return CompileCheckResult(
        workspace_name=workspace.name,
        targets=ordered_results,
        passed=all(
            result.passed
            for result in ordered_results
        ),
        executed=True,
        reason=(
            "Safe in-process Python syntax compilation using built-in "
            "compile(). Source files were read only; no module code was "
            "executed, no bytecode or __pycache__ was written, and no "
            "tests, CI actions, subprocesses, Git actions, or repository "
            "mutations were performed."
        ),
    )

