from __future__ import annotations

import importlib.util
import inspect
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

from app.test_registry import RepositoryTestRegistry


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


def _registry(
    workspace_name: str,
    *,
    inspected: bool = True,
    workspace_path: Path | None = None,
) -> RepositoryTestRegistry:
    return RepositoryTestRegistry(
        workspace_name=workspace_name,
        workspace_path=str(
            workspace_path
            if workspace_path is not None
            else Path.cwd()
        ),
        tests=(),
        inspected=inspected,
        reason="contract",
    )


def test_execution_workspace_allowlist_is_exact() -> None:
    assert module.EXECUTION_WORKSPACES == (
        _EXPECTED_EXECUTION_WORKSPACES
    )
    assert "world-os-web" not in module.EXECUTION_WORKSPACES


def test_dev_agent_registry_is_allowed() -> None:
    module._validate_registry(
        _registry("world-os-dev-agent")
    )


def test_research_engine_registry_is_allowed() -> None:
    module._validate_registry(
        _registry("world-os-research-engine")
    )


def test_web_registry_remains_blocked() -> None:
    with pytest.raises(
        RuntimeError,
        match="approved execution workspaces",
    ):
        module._validate_registry(
            _registry("world-os-web")
        )


def test_unknown_workspace_remains_blocked() -> None:
    with pytest.raises(
        RuntimeError,
        match="approved execution workspaces",
    ):
        module._validate_registry(
            _registry("unknown-workspace")
        )


def test_uninspected_registry_remains_blocked() -> None:
    with pytest.raises(RuntimeError):
        module._validate_registry(
            _registry(
                "world-os-dev-agent",
                inspected=False,
            )
        )


def test_missing_workspace_path_remains_blocked() -> None:
    missing_path = (
        Path.cwd()
        / "__world_os_missing_test_execution_workspace__"
    )

    with pytest.raises(RuntimeError):
        module._validate_registry(
            _registry(
                "world-os-dev-agent",
                workspace_path=missing_path,
            )
        )


def test_execution_result_reason_is_workspace_neutral() -> None:
    source = inspect.getsource(
        module.execute_registered_tests
    )

    assert "world-os-dev-agent tests" not in source.lower()