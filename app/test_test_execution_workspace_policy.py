from __future__ import annotations

import importlib.util
import inspect
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

from app.test_registry import (
    RepositoryTestRegistry,
    TestRegistryEntry,
)


FOCUSED_TARGET_MODULES = ("app.test_execution",)

_EXPECTED_EXECUTION_WORKSPACES = frozenset(
    {
        "world-os-dev-agent",
        "world-os-research-engine",
    }
)


def _load_test_execution_module() -> ModuleType:
    candidate = os.environ.get(
        "WORLD_OS_TEST_EXECUTION_CANDIDATE",
        "",
    ).strip()

    if not candidate:
        import app.test_execution as canonical

        return canonical

    candidate_path = Path(candidate).expanduser().resolve()

    if not candidate_path.exists():
        raise RuntimeError(
            "WORLD_OS_TEST_EXECUTION_CANDIDATE path does not exist."
        )

    if not candidate_path.is_file():
        raise RuntimeError(
            "WORLD_OS_TEST_EXECUTION_CANDIDATE must point to a file."
        )

    if candidate_path.suffix.casefold() != ".py":
        raise RuntimeError(
            "WORLD_OS_TEST_EXECUTION_CANDIDATE must point to a .py file."
        )

    spec = importlib.util.spec_from_file_location(
        "_world_os_test_execution_candidate",
        candidate_path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Unable to create a module specification for the candidate."
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module

    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise

    return module


module = _load_test_execution_module()


def _entry(
    *,
    test_id: str = "test_candidate",
    path: str = "tests/test_candidate.py",
    module_name: str = "tests.test_candidate",
    test_functions: tuple[str, ...] = ("test_candidate",),
    imported_app_modules: tuple[str, ...] = (),
) -> TestRegistryEntry:
    return TestRegistryEntry(
        test_id=test_id,
        path=path,
        module=module_name,
        style="PYTEST_FUNCTIONS",
        test_functions=test_functions,
        imported_app_modules=imported_app_modules,
        declared_focused_modules=(),
        has_main_guard=False,
        compile_target=path,
        execution_validated=False,
    )


def _registry(
    workspace_name: str,
    *,
    workspace_path: Path,
    entries: tuple[TestRegistryEntry, ...],
    inspected: bool = True,
) -> RepositoryTestRegistry:
    return RepositoryTestRegistry(
        workspace_name=workspace_name,
        workspace_path=str(workspace_path),
        tests=entries,
        inspected=inspected,
        reason="contract",
    )


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _assert_regular_python_file(path: Path) -> None:
    assert path.exists()
    assert path.is_file()
    assert path.suffix == ".py"


def _assert_registered_test_file(
    workspace: Path,
    entry: TestRegistryEntry,
) -> None:
    registered_path = workspace / entry.path
    assert registered_path.exists()
    assert registered_path.is_file()
    assert registered_path.suffix == ".py"


def _complete_validation_workspace(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, Path, Path]:
    workspace = tmp_path / "workspace"

    target = _write(
        workspace / "app" / "sample" / "target.py",
        "VALUE = 'canonical'\n",
    )

    target_txt = _write(
        workspace / "app" / "sample" / "target.txt",
        "not Python\n",
    )

    directory_target = workspace / "app" / "sample" / "directory_target"
    directory_target.mkdir(parents=True, exist_ok=True)

    test_file = _write(
        workspace / "tests" / "test_candidate.py",
        "def test_candidate():\n"
        "    assert True\n",
    )

    candidate = _write(
        tmp_path / "candidate.py",
        "VALUE = 'candidate'\n",
    )

    _assert_regular_python_file(target)
    assert target_txt.exists()
    assert target_txt.is_file()
    assert directory_target.exists()
    assert directory_target.is_dir()
    _assert_regular_python_file(test_file)
    _assert_regular_python_file(candidate)

    return (
        workspace,
        target,
        target_txt,
        directory_target,
        test_file,
        candidate,
    )


def _execute(
    workspace: Path,
    *,
    candidate_target_file: str | None,
    candidate_file: Path | None,
    entries: tuple[TestRegistryEntry, ...],
) -> object:
    for entry in entries:
        _assert_registered_test_file(workspace, entry)

    registry = _registry(
        "world-os-dev-agent",
        workspace_path=workspace,
        entries=entries,
    )

    return module.execute_registered_tests(
        registry,
        tuple(entry.test_id for entry in entries),
        candidate_target_file=candidate_target_file,
        candidate_file=(
            None
            if candidate_file is None
            else str(candidate_file)
        ),
    )


def test_execution_workspace_allowlist_is_exact() -> None:
    assert module.EXECUTION_WORKSPACES == (
        _EXPECTED_EXECUTION_WORKSPACES
    )
    assert "world-os-web" not in module.EXECUTION_WORKSPACES


def test_dev_agent_registry_is_allowed(tmp_path: Path) -> None:
    module._validate_registry(
        _registry(
            "world-os-dev-agent",
            workspace_path=tmp_path,
            entries=(),
        )
    )


def test_research_engine_registry_is_allowed(tmp_path: Path) -> None:
    module._validate_registry(
        _registry(
            "world-os-research-engine",
            workspace_path=tmp_path,
            entries=(),
        )
    )


def test_web_registry_remains_blocked(tmp_path: Path) -> None:
    with pytest.raises(
        RuntimeError,
        match="approved execution workspaces",
    ):
        module._validate_registry(
            _registry(
                "world-os-web",
                workspace_path=tmp_path,
                entries=(),
            )
        )


def test_unknown_workspace_remains_blocked(tmp_path: Path) -> None:
    with pytest.raises(
        RuntimeError,
        match="approved execution workspaces",
    ):
        module._validate_registry(
            _registry(
                "unknown-workspace",
                workspace_path=tmp_path,
                entries=(),
            )
        )


def test_uninspected_registry_remains_blocked(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        module._validate_registry(
            _registry(
                "world-os-dev-agent",
                workspace_path=tmp_path,
                entries=(),
                inspected=False,
            )
        )


def test_missing_workspace_path_remains_blocked(
    tmp_path: Path,
) -> None:
    missing_path = (
        tmp_path
        / "__world_os_missing_test_execution_workspace__"
    )

    with pytest.raises(RuntimeError):
        module._validate_registry(
            _registry(
                "world-os-dev-agent",
                workspace_path=missing_path,
                entries=(),
            )
        )


def test_execution_result_reason_is_workspace_neutral() -> None:
    source = inspect.getsource(
        module.execute_registered_tests
    )

    assert "world-os-dev-agent tests" not in source.lower()


@pytest.mark.parametrize(
    "candidate_target_file",
    (
        "",
        "./app/sample/target.py",
        "../outside.py",
        "app/sample/directory_target",
        "app/sample/target.txt",
        "app/sample/missing.py",
    ),
)
def test_invalid_relative_candidate_target_file_is_rejected(
    tmp_path: Path,
    candidate_target_file: str,
) -> None:
    (
        workspace,
        target,
        target_txt,
        directory_target,
        test_file,
        candidate,
    ) = _complete_validation_workspace(tmp_path)

    assert target.exists()
    assert target.is_file()
    assert target_txt.exists()
    assert target_txt.is_file()
    assert directory_target.exists()
    assert directory_target.is_dir()
    assert test_file.exists()
    assert test_file.is_file()
    _assert_regular_python_file(candidate)

    entry = _entry()

    with pytest.raises(RuntimeError):
        _execute(
            workspace,
            candidate_target_file=candidate_target_file,
            candidate_file=candidate,
            entries=(entry,),
        )


def test_absolute_outside_workspace_target_is_rejected(
    tmp_path: Path,
) -> None:
    (
        workspace,
        target,
        target_txt,
        directory_target,
        test_file,
        candidate,
    ) = _complete_validation_workspace(tmp_path)

    outside_root = tmp_path / "outside-root"
    outside = _write(
        outside_root / "outside.py",
        "VALUE = 'outside'\n",
    )

    assert outside_root != workspace
    _assert_regular_python_file(outside)
    assert target.exists()
    assert target.is_file()
    assert target_txt.exists()
    assert target_txt.is_file()
    assert directory_target.exists()
    assert directory_target.is_dir()
    assert test_file.exists()
    assert test_file.is_file()
    _assert_regular_python_file(candidate)

    with pytest.raises(RuntimeError):
        _execute(
            workspace,
            candidate_target_file=str(outside),
            candidate_file=candidate,
            entries=(_entry(),),
        )


@pytest.mark.parametrize(
    "candidate_file_kind",
    (
        "missing",
        "directory",
        "non_python",
    ),
)
def test_invalid_candidate_file_is_rejected(
    tmp_path: Path,
    candidate_file_kind: str,
) -> None:
    (
        workspace,
        target,
        target_txt,
        directory_target,
        test_file,
        valid_candidate,
    ) = _complete_validation_workspace(tmp_path)

    assert target.exists()
    assert target.is_file()
    assert target_txt.exists()
    assert target_txt.is_file()
    assert directory_target.exists()
    assert directory_target.is_dir()
    assert test_file.exists()
    assert test_file.is_file()
    _assert_regular_python_file(valid_candidate)

    if candidate_file_kind == "missing":
        candidate_file = tmp_path / "missing.py"
    elif candidate_file_kind == "directory":
        candidate_file = tmp_path / "candidate_directory"
        candidate_file.mkdir()
    else:
        candidate_file = _write(
            tmp_path / "candidate.txt",
            "not Python\n",
        )

    if candidate_file_kind == "missing":
        assert not candidate_file.exists()
    elif candidate_file_kind == "directory":
        assert candidate_file.exists()
        assert candidate_file.is_dir()
    else:
        assert candidate_file.exists()
        assert candidate_file.is_file()
        assert candidate_file.suffix == ".txt"

    with pytest.raises(RuntimeError):
        _execute(
            workspace,
            candidate_target_file="app/sample/target.py",
            candidate_file=candidate_file,
            entries=(_entry(),),
        )


def test_candidate_target_without_candidate_file_is_rejected(
    tmp_path: Path,
) -> None:
    (
        workspace,
        target,
        target_txt,
        directory_target,
        test_file,
        _,
    ) = _complete_validation_workspace(tmp_path)

    assert target.exists()
    assert target.is_file()
    assert target_txt.exists()
    assert target_txt.is_file()
    assert directory_target.exists()
    assert directory_target.is_dir()
    assert test_file.exists()
    assert test_file.is_file()

    with pytest.raises(RuntimeError):
        _execute(
            workspace,
            candidate_target_file="app/sample/target.py",
            candidate_file=None,
            entries=(_entry(),),
        )


def test_candidate_file_without_candidate_target_is_rejected(
    tmp_path: Path,
) -> None:
    (
        workspace,
        target,
        target_txt,
        directory_target,
        test_file,
        candidate,
    ) = _complete_validation_workspace(tmp_path)

    assert target.exists()
    assert target.is_file()
    assert target_txt.exists()
    assert target_txt.is_file()
    assert directory_target.exists()
    assert directory_target.is_dir()
    assert test_file.exists()
    assert test_file.is_file()
    _assert_regular_python_file(candidate)

    with pytest.raises(RuntimeError):
        _execute(
            workspace,
            candidate_target_file=None,
            candidate_file=candidate,
            entries=(_entry(),),
        )


def test_candidate_overlay_preserves_canonical_workspace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"

    _write(
        workspace / "app" / "__init__.py",
        "",
    )

    _write(
        workspace / "app" / "sample" / "__init__.py",
        "",
    )

    target = _write(
        workspace / "app" / "sample" / "target.py",
        "VALUE = 'canonical'\n",
    )

    unrelated = _write(
        workspace / "app" / "sample" / "unrelated.py",
        "VALUE = 'unrelated-canonical'\n",
    )

    canonical_test = _write(
        workspace / "tests" / "test_canonical.py",
        "from app.sample import target, unrelated\n\n"
        "def test_canonical():\n"
        "    assert target.VALUE == 'canonical'\n"
        "    assert unrelated.VALUE == 'unrelated-canonical'\n",
    )

    candidate_test = _write(
        workspace / "tests" / "test_candidate.py",
        "from app.sample import target, unrelated\n\n"
        "def test_candidate():\n"
        "    assert target.VALUE == 'candidate'\n"
        "    assert unrelated.VALUE == 'unrelated-canonical'\n",
    )

    candidate = _write(
        tmp_path / "candidate.py",
        "VALUE = 'candidate'\n",
    )

    canonical_entry = _entry(
        test_id="test_canonical",
        path="tests/test_canonical.py",
        module_name="tests.test_canonical",
        test_functions=("test_canonical",),
        imported_app_modules=(
            "app.sample.target",
            "app.sample.unrelated",
        ),
    )

    candidate_entry = _entry(
        test_id="test_candidate",
        path="tests/test_candidate.py",
        module_name="tests.test_candidate",
        imported_app_modules=(
            "app.sample.target",
            "app.sample.unrelated",
        ),
    )

    _assert_regular_python_file(target)
    _assert_regular_python_file(unrelated)
    _assert_regular_python_file(canonical_test)
    _assert_regular_python_file(candidate_test)
    _assert_regular_python_file(candidate)

    target_before = target.read_bytes()
    unrelated_before = unrelated.read_bytes()

    canonical_result = _execute(
        workspace,
        candidate_target_file=None,
        candidate_file=None,
        entries=(canonical_entry,),
    )

    assert canonical_result.passed is True

    candidate_result = _execute(
        workspace,
        candidate_target_file="app/sample/target.py",
        candidate_file=candidate,
        entries=(candidate_entry,),
    )

    assert candidate_result.passed is True

    canonical_result_after = _execute(
        workspace,
        candidate_target_file=None,
        candidate_file=None,
        entries=(canonical_entry,),
    )

    assert canonical_result_after.passed is True
    assert target.read_bytes() == target_before
    assert unrelated.read_bytes() == unrelated_before