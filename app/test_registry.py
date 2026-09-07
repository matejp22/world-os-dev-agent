from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.workspace_registry import get_workspace_profile


TestStyle = Literal[
    "PYTEST_FUNCTIONS",
    "SCRIPT_MAIN",
    "SCRIPT_TOP_LEVEL",
]


@dataclass(frozen=True)
class TestRegistryEntry:
    test_id: str
    path: str
    module: str
    style: TestStyle
    test_functions: tuple[str, ...]
    imported_app_modules: tuple[str, ...]
    has_main_guard: bool
    compile_target: str
    execution_validated: bool


@dataclass(frozen=True)
class RepositoryTestRegistry:
    workspace_name: str
    workspace_path: str
    tests: tuple[TestRegistryEntry, ...]
    inspected: bool
    reason: str


@dataclass(frozen=True)
class TestSelectionPlan:
    changed_modules: tuple[str, ...]
    focused_test_ids: tuple[str, ...]
    regression_test_ids: tuple[str, ...]
    executable: bool
    reason: str


def _has_main_guard(tree: ast.Module) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue

        test = node.test

        if not isinstance(test, ast.Compare):
            continue

        if not (
            isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
        ):
            continue

        if len(test.ops) != 1:
            continue

        if not isinstance(test.ops[0], ast.Eq):
            continue

        if len(test.comparators) != 1:
            continue

        comparator = test.comparators[0]

        if (
            isinstance(comparator, ast.Constant)
            and comparator.value == "__main__"
        ):
            return True

    return False


def _top_level_test_functions(
    tree: ast.Module,
) -> tuple[str, ...]:
    names = {
        node.name
        for node in tree.body
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
        and node.name.startswith("test_")
    }

    return tuple(sorted(names))


def _imported_app_modules(
    tree: ast.Module,
) -> tuple[str, ...]:
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""

            if module.startswith("app."):
                modules.add(module)

        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app."):
                    modules.add(alias.name)

    return tuple(
        sorted(
            modules,
            key=str.casefold,
        )
    )


def _classify_test_style(
    *,
    test_functions: tuple[str, ...],
    has_main_guard: bool,
) -> TestStyle:
    if test_functions:
        return "PYTEST_FUNCTIONS"

    if has_main_guard:
        return "SCRIPT_MAIN"

    return "SCRIPT_TOP_LEVEL"


def inspect_repository_test_registry(
    workspace_name: str,
    *,
    max_tests: int = 100,
) -> RepositoryTestRegistry:
    if not isinstance(max_tests, int):
        raise RuntimeError(
            "max_tests must be an integer."
        )

    if max_tests < 1 or max_tests > 200:
        raise RuntimeError(
            "max_tests must be between 1 and 200."
        )

    workspace = get_workspace_profile(
        workspace_name
    )

    app_dir = workspace.path / "app"

    if not app_dir.exists():
        raise RuntimeError(
            f"Workspace app directory does not exist: {app_dir}"
        )

    if not app_dir.is_dir():
        raise RuntimeError(
            f"Workspace app path is not a directory: {app_dir}"
        )

    test_paths = tuple(
        sorted(
            (
                path
                for path in app_dir.glob("test_*.py")
                if path.is_file()
                and path.name != "test_registry.py"
            ),
            key=lambda path: path.name.casefold(),
        )
    )

    if len(test_paths) > max_tests:
        raise RuntimeError(
            "Repository test count exceeds bounded max_tests."
        )

    entries: list[TestRegistryEntry] = []

    for path in test_paths:
        try:
            source = path.read_text(
                encoding="utf-8-sig"
            )
        except Exception as exc:
            raise RuntimeError(
                f"Unable to read test file {path.name}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        try:
            tree = ast.parse(
                source,
                filename=str(path),
            )
        except SyntaxError as exc:
            raise RuntimeError(
                f"Unable to parse test file {path.name}: {exc}"
            ) from exc

        test_functions = (
            _top_level_test_functions(tree)
        )

        imported_app_modules = (
            _imported_app_modules(tree)
        )

        has_main_guard = _has_main_guard(
            tree
        )

        style = _classify_test_style(
            test_functions=test_functions,
            has_main_guard=has_main_guard,
        )

        relative_path = (
            path
            .relative_to(workspace.path)
            .as_posix()
        )

        entries.append(
            TestRegistryEntry(
                test_id=path.stem,
                path=relative_path,
                module=f"app.{path.stem}",
                style=style,
                test_functions=test_functions,
                imported_app_modules=imported_app_modules,
                has_main_guard=has_main_guard,
                compile_target=relative_path,
                execution_validated=False,
            )
        )

    return RepositoryTestRegistry(
        workspace_name=workspace.name,
        workspace_path=str(workspace.path),
        tests=tuple(entries),
        inspected=True,
        reason=(
            "Deterministic read-only discovery of top-level "
            "app/test_*.py files using Python AST inspection. "
            "No tests or CI actions were executed."
        ),
    )

def _changed_path_to_module(path: str) -> str | None:
    normalized = path.replace("\\", "/").strip()

    if not normalized.startswith("app/"):
        return None

    if not normalized.endswith(".py"):
        return None

    module_path = normalized[:-3]

    if module_path.endswith("/__init__"):
        module_path = module_path[:-9]

    return module_path.replace("/", ".")


def plan_test_selection(
    registry: RepositoryTestRegistry,
    changed_files: tuple[str, ...],
) -> TestSelectionPlan:
    if not registry.inspected:
        raise RuntimeError(
            "Test registry must be inspected before selection."
        )

    if not changed_files:
        raise RuntimeError(
            "changed_files must not be empty."
        )

    changed_modules = {
        module
        for path in changed_files
        for module in (_changed_path_to_module(path),)
        if module is not None
    }

    ordered_modules = tuple(
        sorted(
            changed_modules,
            key=str.casefold,
        )
    )

    focused = tuple(
        sorted(
            (
                entry.test_id
                for entry in registry.tests
                if changed_modules.intersection(
                    entry.imported_app_modules
                )
            ),
            key=str.casefold,
        )
    )

    focused_set = set(focused)

    regression = tuple(
        sorted(
            (
                entry.test_id
                for entry in registry.tests
                if entry.test_id not in focused_set
            ),
            key=str.casefold,
        )
    )

    return TestSelectionPlan(
        changed_modules=ordered_modules,
        focused_test_ids=focused,
        regression_test_ids=regression,
        executable=False,
        reason=(
            "Deterministic non-executing test selection. "
            "Focused tests directly import changed app modules; "
            "regression tests are the remaining registered tests. "
            "No tests or CI actions were executed."
        ),
    )

