from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.test_execution_validation import is_test_execution_validated
from app.workspace_registry import get_workspace_profile


TestStyle = Literal[
    "PYTEST_FUNCTIONS",
    "SCRIPT_MAIN",
    "SCRIPT_TOP_LEVEL",
    "NODE_SCRIPT",
]


@dataclass(frozen=True)
class TestRegistryEntry:
    test_id: str
    path: str
    module: str
    style: TestStyle
    test_functions: tuple[str, ...]
    imported_app_modules: tuple[str, ...]
    declared_focused_modules: tuple[str, ...]
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


def _declared_focused_modules(
    tree: ast.Module,
) -> tuple[str, ...]:
    declarations: list[ast.Assign] = []

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            if isinstance(node, ast.AnnAssign):
                if (
                    isinstance(node.target, ast.Name)
                    and node.target.id == "FOCUSED_TARGET_MODULES"
                ):
                    raise RuntimeError(
                        "FOCUSED_TARGET_MODULES must use a plain assignment."
                    )
            continue

        matching_targets = [
            target
            for target in node.targets
            if (
                isinstance(target, ast.Name)
                and target.id == "FOCUSED_TARGET_MODULES"
            )
        ]

        if matching_targets:
            if len(node.targets) != 1:
                raise RuntimeError(
                    "FOCUSED_TARGET_MODULES must be a single-name assignment."
                )

            declarations.append(node)

    if not declarations:
        return ()

    if len(declarations) != 1:
        raise RuntimeError(
            "FOCUSED_TARGET_MODULES must be declared exactly once."
        )

    value = declarations[0].value

    if not isinstance(value, (ast.Tuple, ast.List)):
        raise RuntimeError(
            "FOCUSED_TARGET_MODULES must be a literal tuple or list."
        )

    modules_by_casefold: dict[str, str] = {}

    for element in value.elts:
        if not (
            isinstance(element, ast.Constant)
            and isinstance(element.value, str)
        ):
            raise RuntimeError(
                "FOCUSED_TARGET_MODULES members must be literal strings."
            )

        module = element.value

        if not module.startswith("app."):
            raise RuntimeError(
                "FOCUSED_TARGET_MODULES modules must start with 'app.'."
            )

        module_key = module.casefold()

        if module_key not in modules_by_casefold:
            modules_by_casefold[module_key] = module

    return tuple(
        sorted(
            modules_by_casefold.values(),
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

    if workspace.name == "world-os-web":
        # Explicit read-only metadata registration. Execution is not
        # enabled here and requires a separate restricted executor.
        import json

        if workspace.access_mode != "READ_ONLY":
            raise RuntimeError(
                "Web OSM test requires READ_ONLY workspace policy."
            )

        relative_path = "scripts/osm_geometry_preview_contract_test.mjs"
        test_path = workspace.path / relative_path
        package_path = workspace.path / "package.json"

        if not test_path.is_file() or not package_path.is_file():
            raise RuntimeError(
                "Explicit Web OSM test prerequisites are missing."
            )

        package = json.loads(package_path.read_text(encoding="utf-8"))
        scripts = package.get("scripts")

        if (
            not isinstance(scripts, dict)
            or scripts.get("test:osm-preview-contract")
            != "node scripts/osm_geometry_preview_contract_test.mjs"
        ):
            raise RuntimeError(
                "Web OSM npm script contract mismatch."
            )

        return RepositoryTestRegistry(
            workspace_name=workspace.name,
            workspace_path=str(workspace.path),
            tests=(
                TestRegistryEntry(
                    test_id="web_osm_preview_contract",
                    path=relative_path,
                    module="scripts.osm_geometry_preview_contract_test",
                    style="NODE_SCRIPT",
                    test_functions=(),
                    imported_app_modules=(),
                    declared_focused_modules=(),
                    has_main_guard=False,
                    compile_target=relative_path,
                    execution_validated=False,
                ),
            ),
            inspected=True,
            reason=(
                "Explicit read-only registration of the Web OSM "
                "preview contract test. Execution remains disabled."
            ),
        )

    app_dir = workspace.path / "app"
    tests_dir = workspace.path / "tests"

    if not app_dir.exists():
        raise RuntimeError(
            f"Workspace app directory does not exist: {app_dir}"
        )

    if not app_dir.is_dir():
        raise RuntimeError(
            f"Workspace app path is not a directory: {app_dir}"
        )

    app_test_paths = tuple(
        path
        for path in app_dir.glob("test_*.py")
        if path.is_file()
        and path.name != "test_registry.py"
    )

    tests_tree_paths = (
        tuple(
            path
            for path in tests_dir.rglob("test_*.py")
            if path.is_file()
        )
        if tests_dir.exists() and tests_dir.is_dir()
        else ()
    )

    test_paths = tuple(
        sorted(
            app_test_paths + tests_tree_paths,
            key=lambda path: (
                path.relative_to(workspace.path).as_posix().casefold()
            ),
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

        declared_focused_modules = (
            _declared_focused_modules(tree)
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

        if relative_path.startswith("app/"):
            test_id = path.stem
            module = f"app.{path.stem}"
        else:
            test_id = (
                relative_path[:-3]
                .replace("/", "__")
                .replace("\\", "__")
            )
            module = relative_path[:-3].replace("/", ".")

        entries.append(
            TestRegistryEntry(
                test_id=test_id,
                path=relative_path,
                module=module,
                style=style,
                test_functions=test_functions,
                imported_app_modules=imported_app_modules,
                declared_focused_modules=declared_focused_modules,
                has_main_guard=has_main_guard,
                compile_target=relative_path,
                execution_validated=is_test_execution_validated(
                    workspace.name,
                    test_id,
                    relative_path,
                ),
            )
        )

    return RepositoryTestRegistry(
        workspace_name=workspace.name,
        workspace_path=str(workspace.path),
        tests=tuple(entries),
        inspected=True,
        reason=(
            "Deterministic read-only discovery of top-level "
            "app/test_*.py and tests/**/test_*.py files using Python AST inspection. "
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

    # Web OSM focused selection: metadata only, no execution.
    if registry.workspace_name == "world-os-web":
        web_test_id = "web_osm_preview_contract"
        web_target = "src/app/api/internal-preview/osm-geometry/route.ts"
        web_entry = tuple(
            entry for entry in registry.tests
            if entry.test_id == web_test_id
        )

        if (
            len(registry.tests) != 1
            or len(web_entry) != 1
            or web_entry[0].style != "NODE_SCRIPT"
            or web_entry[0].path
            != "scripts/osm_geometry_preview_contract_test.mjs"
            or web_entry[0].execution_validated is not False
        ):
            raise RuntimeError(
                "Web OSM focused selection registry mismatch."
            )

        matched = any(
            isinstance(changed_path, str)
            and changed_path.replace("\\", "/") == web_target
            for changed_path in changed_files
        )

        return TestSelectionPlan(
            changed_modules=(),
            focused_test_ids=(web_test_id,) if matched else (),
            regression_test_ids=() if matched else (web_test_id,),
            executable=False,
            reason=(
                "Web OSM focused selection is deterministic and "
                "non-executing. Only the explicitly registered API "
                "target receives focused test selection."
            ),
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
                    set(entry.imported_app_modules)
                    | set(entry.declared_focused_modules)
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
            "Focused tests directly import or explicitly declare "
            "changed app modules; regression tests are the remaining "
            "registered tests. No tests or CI actions were executed."
        ),
    )
