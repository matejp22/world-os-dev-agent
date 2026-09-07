from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from app.test_registry import (
    RepositoryTestRegistry,
    TestRegistryEntry,
)


EXECUTION_WORKSPACE = "world-os-dev-agent"

BLOCKED_TEST_IDS = frozenset(
    {
        "test_full_file_diff_pipeline",
        "test_repaired_patch_pipeline",
    }
)


@dataclass(frozen=True)
class TestExecutionResult:
    test_id: str
    style: str
    returncode: int
    passed: bool
    stdout: str
    stderr: str
    executed: bool
    reason: str


@dataclass(frozen=True)
class TestExecutionBatchResult:
    workspace_name: str
    requested_test_ids: tuple[str, ...]
    results: tuple[TestExecutionResult, ...]
    passed: bool
    executed: bool
    reason: str


def _registry_entry_map(
    registry: RepositoryTestRegistry,
) -> dict[str, TestRegistryEntry]:
    return {
        entry.test_id: entry
        for entry in registry.tests
    }


def _validate_registry(
    registry: RepositoryTestRegistry,
) -> None:
    if not registry.inspected:
        raise RuntimeError(
            "Test registry must be inspected before execution."
        )

    if registry.workspace_name != EXECUTION_WORKSPACE:
        raise RuntimeError(
            "Test execution is restricted to world-os-dev-agent."
        )

    workspace = Path(
        registry.workspace_path
    )

    if not workspace.exists():
        raise RuntimeError(
            "Registered workspace path does not exist."
        )

    if not workspace.is_dir():
        raise RuntimeError(
            "Registered workspace path is not a directory."
        )


def _validate_requested_test_ids(
    registry: RepositoryTestRegistry,
    test_ids: tuple[str, ...],
) -> tuple[TestRegistryEntry, ...]:
    if not test_ids:
        raise RuntimeError(
            "test_ids must not be empty."
        )

    if len(test_ids) > 100:
        raise RuntimeError(
            "Requested test count exceeds bounded maximum."
        )

    if len(set(test_ids)) != len(test_ids):
        raise RuntimeError(
            "Duplicate test IDs are not allowed."
        )

    entry_map = _registry_entry_map(
        registry
    )

    entries: list[TestRegistryEntry] = []

    for test_id in test_ids:
        if test_id not in entry_map:
            raise RuntimeError(
                f"Unknown registered test ID: {test_id}"
            )

        if test_id in BLOCKED_TEST_IDS:
            raise RuntimeError(
                f"Test is blocked until explicitly validated: {test_id}"
            )

        entry = entry_map[test_id]

        if entry.style not in {
            "PYTEST_FUNCTIONS",
            "SCRIPT_MAIN",
            "SCRIPT_TOP_LEVEL",
        }:
            raise RuntimeError(
                f"Unsupported registered test style: {entry.style}"
            )

        entries.append(
            entry
        )

    return tuple(
        entries
    )


def _build_test_command(
    entry: TestRegistryEntry,
    workspace: Path,
) -> tuple[str, ...]:
    target = (
        workspace
        / entry.path
    )

    try:
        target.relative_to(
            workspace
        )
    except ValueError as exc:
        raise RuntimeError(
            "Registered test path escapes workspace."
        ) from exc

    if not target.exists():
        raise RuntimeError(
            f"Registered test file does not exist: {entry.path}"
        )

    if not target.is_file():
        raise RuntimeError(
            f"Registered test path is not a file: {entry.path}"
        )

    if target.suffix.lower() != ".py":
        raise RuntimeError(
            "Only registered Python test files may execute."
        )

    if entry.style == "PYTEST_FUNCTIONS":
        return (
            sys.executable,
            "-m",
            "pytest",
            entry.path,
        )

    if entry.style in {
        "SCRIPT_MAIN",
        "SCRIPT_TOP_LEVEL",
    }:
        return (
            sys.executable,
            entry.path,
        )

    raise RuntimeError(
        f"Unsupported test style: {entry.style}"
    )


def execute_registered_tests(
    registry: RepositoryTestRegistry,
    test_ids: tuple[str, ...],
    *,
    timeout_seconds: int = 60,
) -> TestExecutionBatchResult:
    _validate_registry(
        registry
    )

    if not isinstance(
        timeout_seconds,
        int,
    ):
        raise RuntimeError(
            "timeout_seconds must be an integer."
        )

    if (
        timeout_seconds < 1
        or timeout_seconds > 300
    ):
        raise RuntimeError(
            "timeout_seconds must be between 1 and 300."
        )

    entries = _validate_requested_test_ids(
        registry,
        test_ids,
    )

    workspace = Path(
        registry.workspace_path
    )

    env = os.environ.copy()

    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONPATH"] = str(
        workspace
    )

    results: list[TestExecutionResult] = []

    for entry in entries:
        command = _build_test_command(
            entry,
            workspace,
        )

        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=timeout_seconds,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            results.append(
                TestExecutionResult(
                    test_id=entry.test_id,
                    style=entry.style,
                    returncode=-1,
                    passed=False,
                    stdout=(
                        exc.stdout
                        if isinstance(exc.stdout, str)
                        else ""
                    ),
                    stderr=(
                        exc.stderr
                        if isinstance(exc.stderr, str)
                        else ""
                    ),
                    executed=True,
                    reason=(
                        f"Test exceeded timeout of "
                        f"{timeout_seconds} seconds."
                    ),
                )
            )

            continue

        results.append(
            TestExecutionResult(
                test_id=entry.test_id,
                style=entry.style,
                returncode=completed.returncode,
                passed=completed.returncode == 0,
                stdout=completed.stdout.strip(),
                stderr=completed.stderr.strip(),
                executed=True,
                reason=(
                    "Registered test completed successfully."
                    if completed.returncode == 0
                    else "Registered test returned a non-zero exit code."
                ),
            )
        )

    passed = all(
        result.passed
        for result in results
    )

    return TestExecutionBatchResult(
        workspace_name=registry.workspace_name,
        requested_test_ids=test_ids,
        results=tuple(results),
        passed=passed,
        executed=True,
        reason=(
            "Executed only explicitly registered and execution-eligible "
            "world-os-dev-agent tests. No arbitrary command string was accepted."
        ),
    )
