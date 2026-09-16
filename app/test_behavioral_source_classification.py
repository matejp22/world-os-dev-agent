from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType


FOCUSED_TARGET_MODULES = (
    "app.patch_quality_evidence_runner",
    "app.patch_quality_evidence",
)


_CANDIDATE_ENVIRONMENT_VARIABLES = {
    "app.patch_quality_evidence_runner":
        "WORLD_OS_PATCH_QUALITY_EVIDENCE_RUNNER_CANDIDATE",
    "app.patch_quality_evidence":
        "WORLD_OS_PATCH_QUALITY_EVIDENCE_CANDIDATE",
}


_CLASSIFICATION_MATRIX = (
    ("app/example.py", True),
    ("app/research/providers/http_source_content.py", True),
    ("scripts/example.py", True),
    ("app/test_execution.py", True),
    ("app/test_registry.py", True),
    ("app/test_example.py", False),
    ("app/test_patch_quality_gate.py", False),
    ("app/test_patch_quality_evidence_runner.py", False),
    ("scripts/test_example.py", False),
    ("README.md", False),
    ("context/example.py", False),
    ("app/example.txt", False),
    ("app\\test_execution.py", True),
    ("app\\test_registry.py", True),
    ("app\\test_example.py", False),
    ("APP/TEST_EXECUTION.PY", True),
    ("APP/TEST_REGISTRY.PY", True),
)


def _load_module(module_name: str) -> ModuleType:
    environment_variable = _CANDIDATE_ENVIRONMENT_VARIABLES[module_name]
    candidate_value = os.environ.get(environment_variable, "").strip()

    if not candidate_value:
        return importlib.import_module(module_name)

    candidate_path = Path(candidate_value).expanduser().resolve()

    if (
        not candidate_path.exists()
        or not candidate_path.is_file()
        or candidate_path.suffix.casefold() != ".py"
    ):
        raise RuntimeError(
            f"Candidate must be an existing regular .py file: "
            f"{candidate_path}"
        )

    private_name = (
        f"_world_os_candidate_{module_name.rsplit('.', 1)[-1]}"
    )

    spec = importlib.util.spec_from_file_location(
        private_name,
        candidate_path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Unable to create import specification for {candidate_path}"
        )

    candidate_module = importlib.util.module_from_spec(spec)
    sys.modules[private_name] = candidate_module

    try:
        spec.loader.exec_module(candidate_module)
    except Exception:
        sys.modules.pop(private_name, None)
        raise

    return candidate_module


def _classification_results(module: ModuleType) -> tuple[bool, ...]:
    classifier = getattr(module, "_is_behavioral_source", None)

    if not callable(classifier):
        raise AssertionError(
            f"{module.__name__} does not expose "
            "_is_behavioral_source."
        )

    return tuple(
        bool(classifier(path))
        for path, _expected in _CLASSIFICATION_MATRIX
    )


def _assert_expected_results(module: ModuleType) -> None:
    classifier = getattr(module, "_is_behavioral_source", None)

    if not callable(classifier):
        raise AssertionError(
            f"{module.__name__} does not expose "
            "_is_behavioral_source."
        )

    for path, expected in _CLASSIFICATION_MATRIX:
        assert classifier(path) is expected, (
            f"{module.__name__} classified {path!r} incorrectly"
        )


def test_runner_behavioral_source_classification_contract() -> None:
    module = _load_module(
        "app.patch_quality_evidence_runner"
    )

    _assert_expected_results(module)


def test_evidence_behavioral_source_classification_contract() -> None:
    module = _load_module(
        "app.patch_quality_evidence"
    )

    _assert_expected_results(module)


def test_runner_and_evidence_classification_are_identical() -> None:
    runner_module = _load_module(
        "app.patch_quality_evidence_runner"
    )
    evidence_module = _load_module(
        "app.patch_quality_evidence"
    )

    assert _classification_results(runner_module) == (
        _classification_results(evidence_module)
    )