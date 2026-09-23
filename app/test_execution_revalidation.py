from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from app.test_execution import (
    BLOCKED_TEST_IDS,
    execute_registered_tests,
)
from app.test_execution_validation import (
    TestExecutionValidationRecord,
)
from app.test_execution_validation_persistence import (
    persist_test_execution_validation,
)
from app.test_registry import (
    RepositoryTestRegistry,
    inspect_repository_test_registry,
)


def _validate_inputs(
    workspace_name: str,
    test_id: str,
    timeout_seconds: int,
) -> None:
    if (
        not isinstance(workspace_name, str)
        or not workspace_name.strip()
    ):
        raise RuntimeError(
            "workspace_name must be a non-empty non-whitespace string."
        )

    if (
        not isinstance(test_id, str)
        or not test_id.strip()
    ):
        raise RuntimeError(
            "test_id must be a non-empty non-whitespace string."
        )

    if isinstance(timeout_seconds, bool) or not isinstance(
        timeout_seconds,
        int,
    ):
        raise RuntimeError(
            "timeout_seconds must be an integer."
        )

    if timeout_seconds < 1 or timeout_seconds > 300:
        raise RuntimeError(
            "timeout_seconds must be between 1 and 300."
        )


def _resolve_test_path(
    registry: RepositoryTestRegistry,
    relative_path: str,
) -> tuple[Path, Path]:
    workspace = Path(registry.workspace_path).resolve()
    test_path = (workspace / relative_path).resolve()

    try:
        test_path.relative_to(workspace)
    except ValueError as exc:
        raise RuntimeError(
            "Registered test path escapes workspace."
        ) from exc

    if not test_path.exists():
        raise RuntimeError(
            "Registered test file does not exist."
        )

    if not test_path.is_file():
        raise RuntimeError(
            "Registered test path must be a regular file."
        )

    if test_path.suffix.casefold() != ".py":
        raise RuntimeError(
            "Registered test path must be a Python file."
        )

    return workspace, test_path


def revalidate_blocked_test_execution(
    workspace_name: str,
    test_id: str,
    *,
    timeout_seconds: int = 60,
) -> TestExecutionValidationRecord:
    _validate_inputs(
        workspace_name,
        test_id,
        timeout_seconds,
    )

    if test_id not in BLOCKED_TEST_IDS:
        raise RuntimeError(
            "Only blocked test IDs may be revalidated."
        )

    registry = inspect_repository_test_registry(
        workspace_name
    )

    if registry.inspected is not True:
        raise RuntimeError(
            "Test registry must be inspected before revalidation."
        )

    if registry.workspace_name != workspace_name:
        raise RuntimeError(
            "Inspected registry workspace does not match requested workspace."
        )

    matching_entries = tuple(
        entry
        for entry in registry.tests
        if entry.test_id == test_id
    )

    if len(matching_entries) != 1:
        raise RuntimeError(
            "Exactly one registered test entry must match test_id."
        )

    selected_entry = matching_entries[0]

    if selected_entry.execution_validated is True:
        raise RuntimeError(
            "Test execution is already validated."
        )

    workspace, test_path = _resolve_test_path(
        registry,
        selected_entry.path,
    )

    try:
        pre_execution_sha256 = sha256(
            test_path.read_bytes()
        ).hexdigest()
    except OSError as exc:
        raise RuntimeError(
            "Unable to read test file before execution."
        ) from exc

    temporary_entry = replace(
        selected_entry,
        execution_validated=True,
    )

    temporary_tests = tuple(
        temporary_entry
        if entry.test_id == test_id
        else entry
        for entry in registry.tests
    )

    temporary_registry = replace(
        registry,
        tests=temporary_tests,
    )

    batch = execute_registered_tests(
        temporary_registry,
        (test_id,),
        timeout_seconds=timeout_seconds,
    )

    if (
        batch.workspace_name != registry.workspace_name
        or batch.requested_test_ids != (test_id,)
        or batch.executed is not True
        or batch.passed is not True
        or len(batch.results) != 1
    ):
        raise RuntimeError(
            "Blocked test execution did not satisfy the strict success contract."
        )

    result = batch.results[0]

    if (
        result.test_id != test_id
        or result.executed is not True
        or result.passed is not True
        or result.returncode != 0
    ):
        raise RuntimeError(
            "Blocked test execution result did not satisfy the strict success contract."
        )

    post_workspace, post_test_path = _resolve_test_path(
        registry,
        selected_entry.path,
    )

    if post_workspace != workspace or post_test_path != test_path:
        raise RuntimeError(
            "Registered test path changed during execution."
        )

    try:
        post_execution_sha256 = sha256(
            post_test_path.read_bytes()
        ).hexdigest()
    except OSError as exc:
        raise RuntimeError(
            "Unable to read test file after execution."
        ) from exc

    if post_execution_sha256 != pre_execution_sha256:
        raise RuntimeError(
            "Test file SHA256 changed during execution."
        )

    record = persist_test_execution_validation(
        workspace_name,
        test_id,
        selected_entry.path,
        expected_test_sha256=pre_execution_sha256,
    )

    if (
        record.workspace_name != workspace_name
        or record.test_id != test_id
        or record.test_path != selected_entry.path
        or record.test_sha256 != pre_execution_sha256
        or record.execution_validated is not True
    ):
        raise RuntimeError(
            "Persisted test execution validation record was not verified."
        )

    return record