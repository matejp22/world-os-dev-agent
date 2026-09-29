from __future__ import annotations

import pytest

import app.build_patch_orchestrator as orchestrator


FOCUSED_TARGET_MODULES = (
    "app.build_patch_orchestrator",
    "app.ai_file_candidate",
)


def test_extract_exact_target_from_multiline_goal() -> None:
    goal = (
        "Build patch for world-os-research-engine.\n\n"
        "Target exactly:\n"
        "tests/test_terminal_extraction_mapper.py\n\n"
        "Fix fixture."
    )

    assert orchestrator._extract_exact_target_from_goal(goal) == (
        "tests/test_terminal_extraction_mapper.py"
    )


def test_extract_exact_target_from_inline_goal() -> None:
    assert orchestrator._extract_exact_target_from_goal(
        "Target exactly: tests/research/test_example.py"
    ) == "tests/research/test_example.py"


def test_generation_retries_wrong_target_before_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            (
                "TARGET_FILE: app/file.py\n\n"
                "RATIONALE:\nwrong\n\n"
                "NEW_FILE_CONTENT:\nVALUE = 1\n"
            ),
            (
                "TARGET_FILE: tests/test_example.py\n\n"
                "RATIONALE:\ncorrect\n\n"
                "NEW_FILE_CONTENT:\ndef test_example():\n"
                "    assert True\n"
            ),
        ]
    )

    monkeypatch.setattr(
        orchestrator,
        "generate_candidate",
        lambda *_args, **_kwargs: next(responses),
    )

    target, content = orchestrator._generate_exact_target_candidate(
        clean_goal=(
            "Target exactly:\n"
            "tests/test_example.py"
        ),
        canonical_workspace_name="world-os-dev-agent",
        exact_target="tests/test_example.py",
    )

    assert target == "tests/test_example.py"
    assert "def test_example" in content


def test_identical_wrong_target_stagnation_is_hard_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = (
        "TARGET_FILE: app/file.py\n\n"
        "RATIONALE:\nwrong\n\n"
        "NEW_FILE_CONTENT:\nVALUE = 1\n"
    )

    monkeypatch.setattr(
        orchestrator,
        "generate_candidate",
        lambda *_args, **_kwargs: response,
    )

    with pytest.raises(
        RuntimeError,
        match="AUTONOMOUS_HARD_BLOCKER",
    ):
        orchestrator._generate_exact_target_candidate(
            clean_goal=(
                "Target exactly:\n"
                "tests/test_example.py"
            ),
            canonical_workspace_name="world-os-dev-agent",
            exact_target="tests/test_example.py",
        )
