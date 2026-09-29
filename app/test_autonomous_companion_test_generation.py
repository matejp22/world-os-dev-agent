from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import app.build_patch_orchestrator as orchestrator


FOCUSED_TARGET_MODULES = (
    "app.build_patch_orchestrator",
    "app.ai_companion_test_candidate",
)


def test_parse_companion_candidate_accepts_tests_tree() -> None:
    raw = (
        "TARGET_FILE: tests/research/test_example.py\n\n"
        "RATIONALE:\nfocused test\n\n"
        "NEW_FILE_CONTENT:\n"
        "def test_example():\n"
        "    assert True\n"
    )

    target, content = (
        orchestrator._parse_companion_test_candidate(raw)
    )

    assert target == "tests/research/test_example.py"
    assert "def test_example" in content


@pytest.mark.parametrize(
    "target",
    [
        "app/test_example.py",
        "scripts/test_example.py",
        "tests/example.py",
        "tests/../test_example.py",
        "docs/test_example.py",
    ],
)
def test_parse_companion_candidate_rejects_invalid_target(
    target: str,
) -> None:
    raw = (
        f"TARGET_FILE: {target}\n\n"
        "RATIONALE:\ninvalid\n\n"
        "NEW_FILE_CONTENT:\n"
        "def test_example():\n"
        "    assert True\n"
    )

    with pytest.raises(RuntimeError):
        orchestrator._parse_companion_test_candidate(raw)


def test_build_companion_test_patch_creates_new_test_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_target = (
        tmp_path
        / "workspace"
        / "tests"
        / "research"
        / "test_example.py"
    )
    test_target.parent.mkdir(parents=True)

    monkeypatch.setattr(
        orchestrator,
        "get_workspace_profile",
        lambda _: SimpleNamespace(
            name="world-os-research-engine",
            path=tmp_path / "workspace",
        ),
    )

    monkeypatch.setattr(
        orchestrator,
        "generate_companion_test_candidate",
        lambda **_kwargs: (
            "TARGET_FILE: tests/research/test_example.py\n\n"
            "RATIONALE:\nfocused test\n\n"
            "NEW_FILE_CONTENT:\n"
            "def test_example():\n"
            "    assert True\n"
        ),
    )

    monkeypatch.setattr(
        orchestrator,
        "resolve_workspace_python_target",
        lambda *_args, **_kwargs: test_target,
    )

    captured = {}

    class Attempt:
        result = SimpleNamespace(
            patch_id="test-patch",
            target_file="tests/research/test_example.py",
            status="READY_FOR_HUMAN_REVIEW",
        )

    def fake_build_candidate_attempt(**kwargs):
        captured.update(kwargs)
        return Attempt()

    monkeypatch.setattr(
        orchestrator,
        "_build_candidate_attempt",
        fake_build_candidate_attempt,
    )

    result = orchestrator._build_companion_test_patch(
        goal="implement example",
        workspace_name="world-os-research-engine",
        source_target_file="app/research/example.py",
        source_candidate_content="VALUE = 2\n",
        source_patch_id="source-patch",
    )

    assert result.status == "READY_FOR_HUMAN_REVIEW"
    assert captured["target_file"] == (
        "tests/research/test_example.py"
    )
    assert captured["target_exists"] is False
    assert captured["format_version"] == "NEW_FILE_V2"
    assert captured["previous_patch_id"] == "source-patch"


def test_companion_target_falls_back_to_existing_tests_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "tests").mkdir(
        parents=True,
    )

    monkeypatch.setattr(
        orchestrator,
        "get_workspace_profile",
        lambda _: SimpleNamespace(
            name="world-os-research-engine",
            path=workspace,
        ),
    )

    selected = (
        orchestrator._select_companion_test_target(
            workspace_name="world-os-research-engine",
            generated_target_file=(
                "tests/importers/port_core_v2/"
                "test_autonomous_policy.py"
            ),
            source_target_file=(
                "app/importers/port_core_v2/"
                "autonomous_policy.py"
            ),
        )
    )

    assert selected == (
        "tests/test_autonomous_policy.py"
    )
