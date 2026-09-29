from __future__ import annotations

import pytest

from app.full_file_validator import parse_candidate


FOCUSED_TARGET_MODULES = ("app.full_file_validator",)


def _candidate(target: str) -> str:
    return (
        f"TARGET_FILE: {target}\n\n"
        "RATIONALE:\nmanual test patch\n\n"
        "NEW_FILE_CONTENT:\n"
        "def test_example():\n"
        "    assert True\n"
    )


def test_manual_candidate_accepts_root_tests_file() -> None:
    target, content = parse_candidate(
        _candidate("tests/test_example.py")
    )

    assert target == "tests/test_example.py"
    assert "def test_example" in content


def test_manual_candidate_accepts_nested_tests_file() -> None:
    target, _ = parse_candidate(
        _candidate("tests/research/test_example.py")
    )

    assert target == "tests/research/test_example.py"


@pytest.mark.parametrize(
    "target",
    (
        "tests/example.py",
        "tests/research/example.py",
        "tests/../test_example.py",
        "docs/test_example.py",
    ),
)
def test_manual_candidate_rejects_invalid_tests_target(
    target: str,
) -> None:
    with pytest.raises(RuntimeError):
        parse_candidate(_candidate(target))
