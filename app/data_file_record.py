from __future__ import annotations

from datetime import datetime
from typing import Mapping, cast

from app.data_file_types import (
    DataFileKind,
    DataFileOperation,
    DataFilePatchRecord,
    DataFileStatus,
)


_EXPECTED_FIELDS = frozenset(
    {
        "patch_id",
        "format_version",
        "operation",
        "data_kind",
        "workspace_name",
        "target_file",
        "original_sha256",
        "candidate_sha256",
        "candidate_file",
        "diff_file",
        "validation_passed",
        "semantic_decision",
        "semantic_review",
        "status",
        "created_at",
    }
)

_FORMAT_VERSION = "DATA_FILE_V1"

_ALLOWED_OPERATIONS = frozenset({"CREATE", "REPLACE"})

_ALLOWED_DATA_KINDS = frozenset(
    {
        "MASTER_ROADMAP",
        "PROJECT_ROADMAP",
    }
)

_ALLOWED_STATUSES = frozenset(
    {
        "DRAFT",
        "READY_FOR_HUMAN_REVIEW",
        "APPROVED",
        "APPLYING",
        "CREATED_VERIFIED",
        "REPLACED_VERIFIED",
        "APPLIED",
        "REJECTED",
        "ROLLED_BACK",
        "ROLLBACK_FAILED",
    }
)


def _require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{field_name} must be a non-empty string.")

    return value


def _require_sha256(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise RuntimeError(f"{field_name} must be a string.")

    if len(value) != 64:
        raise RuntimeError(
            f"{field_name} must contain exactly 64 hexadecimal characters."
        )

    if any(character not in "0123456789abcdefABCDEF" for character in value):
        raise RuntimeError(
            f"{field_name} must contain exactly 64 hexadecimal characters."
        )

    return value


def _require_choice(
    value: object,
    field_name: str,
    allowed: frozenset[str],
) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise RuntimeError(f"{field_name} contains an unsupported value.")

    return value


def data_file_patch_record_from_dict(
    value: dict[str, object],
) -> DataFilePatchRecord:
    """Parse and validate a DATA_FILE_V1 queue-record dictionary."""
    if not isinstance(value, dict):
        raise RuntimeError("value must be a dict.")

    actual_fields = frozenset(value)

    missing_fields = _EXPECTED_FIELDS - actual_fields
    if missing_fields:
        raise RuntimeError(
            "Record is missing required fields: "
            + ", ".join(sorted(missing_fields))
            + "."
        )

    unknown_fields = actual_fields - _EXPECTED_FIELDS
    if unknown_fields:
        raise RuntimeError(
            "Record contains unknown fields: "
            + ", ".join(sorted(unknown_fields))
            + "."
        )

    patch_id = _require_non_empty_string(value["patch_id"], "patch_id")

    format_version = value["format_version"]
    if format_version != _FORMAT_VERSION:
        raise RuntimeError("format_version must equal DATA_FILE_V1.")
    format_version = cast(str, format_version)

    operation = _require_choice(
        value["operation"],
        "operation",
        _ALLOWED_OPERATIONS,
    )
    operation = cast(DataFileOperation, operation)

    data_kind = _require_choice(
        value["data_kind"],
        "data_kind",
        _ALLOWED_DATA_KINDS,
    )
    data_kind = cast(DataFileKind, data_kind)

    workspace_name = _require_non_empty_string(
        value["workspace_name"],
        "workspace_name",
    )

    target_file = _require_non_empty_string(
        value["target_file"],
        "target_file",
    )

    original_sha256_value = value["original_sha256"]

    if operation == "CREATE":
        if original_sha256_value is not None:
            raise RuntimeError(
                "original_sha256 must be None for CREATE records."
            )

        original_sha256 = None
    else:
        original_sha256 = _require_sha256(
            original_sha256_value,
            "original_sha256",
        )

    candidate_sha256 = _require_sha256(
        value["candidate_sha256"],
        "candidate_sha256",
    )

    candidate_file = _require_non_empty_string(
        value["candidate_file"],
        "candidate_file",
    )

    diff_file = _require_non_empty_string(
        value["diff_file"],
        "diff_file",
    )

    validation_passed = value["validation_passed"]
    if type(validation_passed) is not bool:
        raise RuntimeError("validation_passed must be bool exactly.")

    semantic_decision = _require_non_empty_string(
        value["semantic_decision"],
        "semantic_decision",
    )

    semantic_review = value["semantic_review"]
    if not isinstance(semantic_review, str):
        raise RuntimeError("semantic_review must be a string.")

    status = _require_choice(
        value["status"],
        "status",
        _ALLOWED_STATUSES,
    )
    status = cast(DataFileStatus, status)

    created_at = _require_non_empty_string(
        value["created_at"],
        "created_at",
    )

    try:
        parsed_created_at = datetime.fromisoformat(created_at)
    except ValueError as exc:
        raise RuntimeError(
            "created_at must be a valid ISO-8601 timestamp."
        ) from exc

    if parsed_created_at.tzinfo is None:
        raise RuntimeError(
            "created_at must include timezone information."
        )

    if parsed_created_at.utcoffset() is None:
        raise RuntimeError(
            "created_at must include a valid timezone offset."
        )

    return DataFilePatchRecord(
        patch_id=patch_id,
        format_version=format_version,
        operation=operation,
        data_kind=data_kind,
        workspace_name=workspace_name,
        target_file=target_file,
        original_sha256=original_sha256,
        candidate_sha256=candidate_sha256,
        candidate_file=candidate_file,
        diff_file=diff_file,
        validation_passed=validation_passed,
        semantic_decision=semantic_decision,
        semantic_review=semantic_review,
        status=status,
        created_at=created_at,
    )