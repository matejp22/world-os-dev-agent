import ast

import pytest

import app.test_registry as test_registry


def _parse(source: str) -> ast.Module:
    return ast.parse(source)


def test_literal_tuple_declaration() -> None:
    tree = _parse(
        """
FOCUSED_TARGET_MODULES = (
    "app.console",
    "app.some_module",
)
"""
    )

    assert test_registry._declared_focused_modules(tree) == (
        "app.console",
        "app.some_module",
    )


def test_literal_list_declaration() -> None:
    tree = _parse(
        """
FOCUSED_TARGET_MODULES = ["app.console"]
"""
    )

    assert test_registry._declared_focused_modules(tree) == (
        "app.console",
    )


def test_missing_declaration_returns_empty_tuple() -> None:
    tree = _parse("VALUE = 1")

    assert test_registry._declared_focused_modules(tree) == ()


def test_duplicate_modules_are_deduplicated_and_sorted() -> None:
    tree = _parse(
        """
FOCUSED_TARGET_MODULES = (
    "app.Zeta",
    "app.alpha",
    "app.zETA",
    "app.Beta",
)
"""
    )

    assert test_registry._declared_focused_modules(tree) == (
        "app.alpha",
        "app.Beta",
        "app.Zeta",
    )


@pytest.mark.parametrize(
    "source",
    (
        'FOCUSED_TARGET_MODULES = "app.console"',
        'FOCUSED_TARGET_MODULES = ("app.console", 1)',
        'FOCUSED_TARGET_MODULES = ("outside.module",)',
        'FOCUSED_TARGET_MODULES = (load_target(),)',
        'FOCUSED_TARGET_MODULES = (target_module,)',
        """
FOCUSED_TARGET_MODULES = ("app.console",)
FOCUSED_TARGET_MODULES = ("app.other",)
""",
    ),
)
def test_invalid_declaration_raises_runtime_error(
    source: str,
) -> None:
    tree = _parse(source)

    with pytest.raises(RuntimeError):
        test_registry._declared_focused_modules(tree)


def test_declared_module_selects_focused_test() -> None:
    entry = test_registry.TestRegistryEntry(
        test_id="test_example",
        path="app/test_example.py",
        module="app.test_example",
        style="PYTEST_FUNCTIONS",
        test_functions=("test_example",),
        imported_app_modules=(),
        declared_focused_modules=("app.console",),
        has_main_guard=False,
        compile_target="app/test_example.py",
        execution_validated=False,
    )
    registry = test_registry.RepositoryTestRegistry(
        workspace_name="world-os-dev-agent",
        workspace_path=".",
        tests=(entry,),
        inspected=True,
        reason="test contract",
    )

    plan = test_registry.plan_test_selection(
        registry,
        ("app/console.py",),
    )

    assert plan.focused_test_ids == ("test_example",)


def test_import_based_selection_remains_supported() -> None:
    entry = test_registry.TestRegistryEntry(
        test_id="test_import_example",
        path="app/test_import_example.py",
        module="app.test_import_example",
        style="PYTEST_FUNCTIONS",
        test_functions=("test_import_example",),
        imported_app_modules=("app.console",),
        declared_focused_modules=(),
        has_main_guard=False,
        compile_target="app/test_import_example.py",
        execution_validated=False,
    )
    registry = test_registry.RepositoryTestRegistry(
        workspace_name="world-os-dev-agent",
        workspace_path=".",
        tests=(entry,),
        inspected=True,
        reason="test contract",
    )

    plan = test_registry.plan_test_selection(
        registry,
        ("app/console.py",),
    )

    assert plan.focused_test_ids == ("test_import_example",)


def test_union_supports_imported_and_declared_modules() -> None:
    entry = test_registry.TestRegistryEntry(
        test_id="test_union_example",
        path="app/test_union_example.py",
        module="app.test_union_example",
        style="PYTEST_FUNCTIONS",
        test_functions=("test_union_example",),
        imported_app_modules=("app.console",),
        declared_focused_modules=("app.some_module",),
        has_main_guard=False,
        compile_target="app/test_union_example.py",
        execution_validated=False,
    )
    registry = test_registry.RepositoryTestRegistry(
        workspace_name="world-os-dev-agent",
        workspace_path=".",
        tests=(entry,),
        inspected=True,
        reason="test contract",
    )

    imported_plan = test_registry.plan_test_selection(
        registry,
        ("app/console.py",),
    )
    declared_plan = test_registry.plan_test_selection(
        registry,
        ("app/some_module.py",),
    )

    assert imported_plan.focused_test_ids == ("test_union_example",)
    assert declared_plan.focused_test_ids == ("test_union_example",)