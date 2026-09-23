from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath

from app.full_file_apply_v2 import atomic_write_json
from app.test_execution_validation import (
    TEST_EXECUTION_VALIDATION_PATH,
    TestExecutionValidationRecord,
    load_test_execution_validations,
)
from app.workspace_registry import resolve_workspace_python_target


def _validate_non_empty_string(
    value: str,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(
            f"{field_name} must be a non-empty string."
        )

    return value


def _validate_expected_test_sha256(
    expected_test_sha256: str | None,
) -> str | None:
    if expected_test_sha256 is None:
        return None

    if (
        not isinstance(expected_test_sha256, str)
        or len(expected_test_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in expected_test_sha256
        )
    ):
        raise RuntimeError(
            "expected_test_sha256 must be exactly 64 lowercase "
            "hexadecimal characters."
        )

    return expected_test_sha256


def _normalize_test_path(
    test_path: str,
) -> str:
    test_path = _validate_non_empty_string(
        test_path,
        "test_path",
    )

    normalized = test_path.replace(
        "\\",
        "/",
    ).strip()

    if not normalized:
        raise RuntimeError(
            "test_path must not be empty."
        )

    if (
        normalized.startswith("/")
        or normalized.startswith("//")
        or PurePosixPath(normalized).is_absolute()
        or (
            len(normalized) >= 3
            and normalized[0].isalpha()
            and normalized[1:3] == ":/"
        )
    ):
        raise RuntimeError(
            "test_path must be workspace-relative."
        )

    parts = tuple(normalized.split("/"))

    if any(
        not part or part in {".", ".."}
        for part in parts
    ):
        raise RuntimeError(
            "test_path must be a normalized workspace-relative path."
        )

    if not normalized.endswith(".py"):
        raise RuntimeError(
            "test_path must be a Python file."
        )

    return normalized


def _resolve_test_file(
    workspace_name: str,
    normalized_test_path: str,
) -> Path:
    resolved = resolve_workspace_python_target(
        workspace_name,
        normalized_test_path,
        must_exist=True,
        allow_existing_test_script=True,
    ).resolve()

    if resolved.is_symlink():
        raise RuntimeError(
            "Registered test file symlinks are not permitted."
        )

    if not resolved.exists():
        raise RuntimeError(
            "Registered test file does not exist."
        )

    if not resolved.is_file():
        raise RuntimeError(
            "Registered test file must be a regular file."
        )

    return resolved


def _load_existing_records() -> list[TestExecutionValidationRecord]:
    records = list(
        load_test_execution_validations()
    )

    identities: set[tuple[str, str]] = set()

    for record in records:
        identity = (
            record.workspace_name,
            record.test_id,
        )

        if identity in identities:
            raise RuntimeError(
                "Duplicate existing test execution validation identity."
            )

        identities.add(identity)

    return records


def persist_test_execution_validation(
    workspace_name: str,
    test_id: str,
    test_path: str,
    *,
    expected_test_sha256: str | None = None,
) -> TestExecutionValidationRecord:
    workspace_name = _validate_non_empty_string(
        workspace_name,
        "workspace_name",
    )
    test_id = _validate_non_empty_string(
        test_id,
        "test_id",
    )
    expected_test_sha256 = _validate_expected_test_sha256(
        expected_test_sha256,
    )

    normalized_test_path = _normalize_test_path(
        test_path,
    )

    if PurePosixPath(normalized_test_path).stem != test_id:
        raise RuntimeError(
            "test_id must match the test_path stem."
        )

    resolved_test_file = _resolve_test_file(
        workspace_name,
        normalized_test_path,
    )

    try:
        test_sha256 = hashlib.sha256(
            resolved_test_file.read_bytes()
        ).hexdigest()
    except OSError as exc:
        raise RuntimeError(
            "Unable to read registered test file."
        ) from exc

    if (
        expected_test_sha256 is not None
        and test_sha256 != expected_test_sha256
    ):
        raise RuntimeError(
            "The current registered test file SHA256 does not match "
            "the expected validated SHA256."
        )

    record = TestExecutionValidationRecord(
        workspace_name=workspace_name,
        test_id=test_id,
        test_path=normalized_test_path,
        test_sha256=test_sha256,
        execution_validated=True,
    )

    existing_records = _load_existing_records()
    identity = (
        workspace_name,
        test_id,
    )

    updated_records = [
        existing_record
        for existing_record in existing_records
        if (
            existing_record.workspace_name,
            existing_record.test_id,
        ) != identity
    ]
    updated_records.append(record)

    updated_records.sort(
        key=lambda existing_record: (
            existing_record.workspace_name.casefold(),
            existing_record.test_id.casefold(),
        )
    )

    payload = {
        "schema_version": 1,
        "validations": [
            {
                "workspace_name": existing_record.workspace_name,
                "test_id": existing_record.test_id,
                "test_path": existing_record.test_path,
                "test_sha256": existing_record.test_sha256,
                "execution_validated": True,
            }
            for existing_record in updated_records
        ],
    }

    atomic_write_json(
        TEST_EXECUTION_VALIDATION_PATH,
        payload,
    )

    verified_records = load_test_execution_validations()

    verified_matches = [
        verified_record
        for verified_record in verified_records
        if (
            verified_record.workspace_name == workspace_name
            and verified_record.test_id == test_id
        )
    ]

    if len(verified_matches) != 1:
        raise RuntimeError(
            "Persisted test execution validation identity could not be "
            "verified."
        )

    verified_record = verified_matches[0]

    if (
        verified_record.test_path != normalized_test_path
        or verified_record.test_sha256 != test_sha256
        or verified_record.execution_validated is not True
        or (
            expected_test_sha256 is not None
            and verified_record.test_sha256 != expected_test_sha256
        )
    ):
        raise RuntimeError(
            "Persisted test execution validation record did not match "
            "the current test file."
        )

    return verified_record