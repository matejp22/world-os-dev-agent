from __future__ import annotations

from pathlib import Path

import pytest

from app.workspace_registry import resolve_workspace_python_target


def _patch_workspace(
    monkeypatch: pytest.MonkeyPatch,
    workspace: Path,
) -> None:
    monkeypatch.setattr(
        "app.workspace_registry.get_workspace_profile",
        lambda name: type(
            "Workspace",
            (),
            {"path": workspace},
        )(),
    )


def _write(path: Path, content: str = "VALUE = 1\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_tests_tree_is_rejected_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    _write(workspace / "tests" / "research" / "test_example.py")
    _patch_workspace(monkeypatch, workspace)

    with pytest.raises(RuntimeError):
        resolve_workspace_python_target(
            "world-os-dev-agent",
            "tests/research/test_example.py",
        )


def test_existing_tests_tree_file_resolves_when_explicitly_allowed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    expected = _write(
        workspace / "tests" / "research" / "test_example.py"
    )
    _patch_workspace(monkeypatch, workspace)

    resolved = resolve_workspace_python_target(
        "world-os-dev-agent",
        "tests/research/test_example.py",
        allow_tests_tree=True,
        must_exist=True,
    )

    assert resolved == expected.resolve()


def test_missing_tests_tree_file_can_be_resolved_for_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    research = workspace / "tests" / "research"
    research.mkdir(parents=True)
    _patch_workspace(monkeypatch, workspace)

    resolved = resolve_workspace_python_target(
        "world-os-dev-agent",
        "tests/research/test_new_file.py",
        allow_tests_tree=True,
        must_exist=False,
    )

    assert resolved == (
        workspace / "tests" / "research" / "test_new_file.py"
    ).resolve()


def test_existing_app_python_behavior_is_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    expected = _write(workspace / "app" / "module.py")
    _patch_workspace(monkeypatch, workspace)

    resolved = resolve_workspace_python_target(
        "world-os-dev-agent",
        "app/module.py",
    )

    assert resolved == expected.resolve()


def test_existing_top_level_test_script_behavior_is_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    expected = _write(workspace / "scripts" / "test_example.py")
    _patch_workspace(monkeypatch, workspace)

    resolved = resolve_workspace_python_target(
        "world-os-dev-agent",
        "scripts/test_example.py",
        allow_existing_test_script=True,
    )

    assert resolved == expected.resolve()


@pytest.mark.parametrize(
    "target",
    (
        "tests/../escape.py",
        "tests/research/../escape.py",
    ),
)
def test_tests_tree_traversal_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "tests" / "research").mkdir(parents=True)
    _patch_workspace(monkeypatch, workspace)

    with pytest.raises(RuntimeError):
        resolve_workspace_python_target(
            "world-os-dev-agent",
            target,
            allow_tests_tree=True,
            must_exist=False,
        )


@pytest.mark.parametrize(
    "target",
    (
        "tests/research/test_example.txt",
        "tests/research/test_example.pyc",
    ),
)
def test_tests_tree_non_python_targets_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "tests" / "research").mkdir(parents=True)
    _patch_workspace(monkeypatch, workspace)

    with pytest.raises(RuntimeError):
        resolve_workspace_python_target(
            "world-os-dev-agent",
            target,
            allow_tests_tree=True,
            must_exist=False,
        )


@pytest.mark.parametrize(
    "target",
    (
        ".env/test.py",
        "supabase/test.py",
        "database/test.py",
        "db/test.py",
        "migrations/test.py",
        ".temp/test.py",
        ".git/test.py",
    ),
)
def test_sensitive_targets_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    workspace = tmp_path / "workspace"
    _patch_workspace(monkeypatch, workspace)

    with pytest.raises(RuntimeError):
        resolve_workspace_python_target(
            "world-os-dev-agent",
            target,
            allow_tests_tree=True,
            must_exist=False,
        )


def test_tests_tree_symlink_escape_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    tests_root = workspace / "tests"
    outside_target = tmp_path / "outside" / "test_escape.py"

    tests_root.mkdir(parents=True)
    _write(outside_target)

    research_link = tests_root / "research"

    try:
        research_link.symlink_to(
            outside_target.parent,
            target_is_directory=True,
        )
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlink creation unavailable: {exc}")

    _patch_workspace(monkeypatch, workspace)

    assert outside_target.exists()

    with pytest.raises(RuntimeError):
        resolve_workspace_python_target(
            "world-os-dev-agent",
            "tests/research/test_escape.py",
            allow_tests_tree=True,
            must_exist=True,
        )