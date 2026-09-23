from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from app.context_loader import PROJECT_ROOT
from app.workspace_registry import resolve_workspace_python_target


TEST_EXECUTION_VALIDATION_PATH = (
    PROJECT_ROOT
    / "context"
    / "TEST_EXECUTION_VALIDATION.json"
)

_SCHEMA_VERSION = 1
_WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:/")


@dataclass(frozen=True)
class TestExecutionValidationRecord:
    workspace_name: str
    test_id: str
    test_path: str
    test_sha256: str
    execution_validated: bool


def _normalize_test_path(test_path: str) -> str:
    if not isinstance(test_path, str):
        raise RuntimeError("test_path must be a string.")

    normalized = test_path.replace("\\", "/").strip()

    if not normalized:
        raise RuntimeError("test_path must not be empty.")

    if (
        normalized.startswith("/")
        or normalized.startswith("//")
        or _WINDOWS_DRIVE_PATH.match(normalized) is not None
        or PurePosixPath(normalized).is_absolute()
    ):
        raise RuntimeError(
            "test_path must be a workspace-relative path."
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


def _require_string(
    value: Any,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(
            f"{field_name} must be a non-empty string."
        )

    return value


def _parse_record(
    value: Any,
) -> TestExecutionValidationRecord:
    if not isinstance(value, dict):
        raise RuntimeError(
            "Each validation record must be an object."
        )

    expected_keys = {
        "workspace_name",
        "test_id",
        "test_path",
        "test_sha256",
        "execution_validated",
    }

    if set(value) != expected_keys:
        raise RuntimeError(
            "Validation record keys are malformed."
        )

    workspace_name = _require_string(
        value["workspace_name"],
        "workspace_name",
    )
    test_path = _normalize_test_path(
        _require_string(
            value["test_path"],
            "test_path",
        )
    )

    test_id = _require_string(
        value["test_id"],
        "test_id",
    )

    expected_test_id = PurePosixPath(
        test_path
    ).stem

    if test_id != expected_test_id:
        raise RuntimeError(
            "test_id does not match test_path."
        )

    test_sha256 = _require_string(
        value["test_sha256"],
        "test_sha256",
    )

    if value["execution_validated"] is not True:
        raise RuntimeError(
            "execution_validated must be exactly True."
        )

    return TestExecutionValidationRecord(
        workspace_name=workspace_name,
        test_id=test_id,
        test_path=test_path,
        test_sha256=test_sha256,
        execution_validated=True,
    )


def _load_evidence_object() -> dict[str, Any]:
    try:
        raw = TEST_EXECUTION_VALIDATION_PATH.read_text(
            encoding="utf-8",
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Test execution validation evidence is missing."
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            "Unable to read test execution validation evidence."
        ) from exc

    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Test execution validation evidence is malformed JSON."
        ) from exc

    if not isinstance(value, dict):
        raise RuntimeError(
            "Test execution validation evidence must be an object."
        )

    if set(value) != {"schema_version", "validations"}:
        raise RuntimeError(
            "Test execution validation evidence keys are malformed."
        )

    if value["schema_version"] != _SCHEMA_VERSION:
        raise RuntimeError(
            "Unsupported test execution validation schema version."
        )

    if not isinstance(value["validations"], list):
        raise RuntimeError(
            "validations must be a list."
        )

    return value


def load_test_execution_validations(
) -> tuple[TestExecutionValidationRecord, ...]:
    evidence_path = TEST_EXECUTION_VALIDATION_PATH

    if evidence_path.is_symlink():
        raise RuntimeError(
            "Test execution validation evidence symlinks are not permitted."
        )

    if not evidence_path.exists():
        return ()

    evidence = _load_evidence_object()
    records = tuple(
        _parse_record(item)
        for item in evidence["validations"]
    )

    identities: set[tuple[str, str]] = set()

    for record in records:
        identity = (
            record.workspace_name,
            record.test_id,
        )

        if identity in identities:
            raise RuntimeError(
                "Duplicate test execution validation record."
            )

        identities.add(identity)

    return tuple(
        sorted(
            records,
            key=lambda record: (
                record.workspace_name.casefold(),
                record.test_id.casefold(),
            ),
        )
    )


def is_test_execution_validated(
    workspace_name: str,
    test_id: str,
    test_path: str,
) -> bool:
    if not isinstance(workspace_name, str) or not workspace_name:
        raise RuntimeError(
            "workspace_name must be a non-empty string."
        )

    if not isinstance(test_id, str) or not test_id:
        raise RuntimeError(
            "test_id must be a non-empty string."
        )

    normalized_test_path = _normalize_test_path(
        test_path
    )

    expected_test_id = PurePosixPath(
        normalized_test_path
    ).stem

    if test_id != expected_test_id:
        return False

    try:
        resolved_test_file = resolve_workspace_python_target(
            workspace_name,
            normalized_test_path,
            must_exist=True,
            allow_existing_test_script=True,
        )
    except RuntimeError:
        return False

    records = load_test_execution_validations()

    for record in records:
        if (
            record.workspace_name != workspace_name
            or record.test_id != test_id
            or record.test_path != normalized_test_path
            or record.execution_validated is not True
        ):
            continue

        try:
            current_sha256 = __import__(
                "hashlib"
            ).sha256(
                resolved_test_file.read_bytes()
            ).hexdigest()
        except OSError:
            return False

        return current_sha256 == record.test_sha256

    return False