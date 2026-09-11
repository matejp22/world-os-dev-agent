from __future__ import annotations

import hashlib

from app.data_file_record import (
    data_file_patch_record_from_dict,
)
from app.data_file_types import (
    DataFileKind,
    DataFileOperation,
    DataFilePatchRecord,
    DataFileStatus,
)


_ALLOWED_OPERATIONS = frozenset({"CREATE", "REPLACE"})
_ALLOWED_DATA_KINDS = frozenset({"MASTER_ROADMAP", "PROJECT_ROADMAP"})
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


def _require_exact_string(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field_name} must be a string exactly.")
    return value


def _require_non_empty_string(value: object, field_name: str) -> str:
    result = _require_exact_string(value, field_name)
    if not result.strip():
        raise ValueError(f"{field_name} must be non-empty.")
    return result


def _require_choice(
    value: object,
    field_name: str,
    allowed: frozenset[str],
) -> str:
    result = _require_exact_string(value, field_name)
    if result not in allowed:
        raise ValueError(f"{field_name} contains an unsupported value.")
    return result


def _require_sha256(value: object, field_name: str) -> str:
    result = _require_exact_string(value, field_name)
    if len(result) != 64 or any(
        character not in "0123456789abcdefABCDEF"
        for character in result
    ):
        raise ValueError(
            f"{field_name} must contain exactly 64 hexadecimal characters."
        )
    return result.lower()


def build_data_file_patch_record(
    *,
    patch_id: str,
    operation: DataFileOperation,
    data_kind: DataFileKind,
    workspace_name: str,
    target_file: str,
    original_sha256: str | None,
    candidate_bytes: bytes,
    candidate_file: str,
    diff_file: str,
    semantic_decision: str,
    semantic_review: str,
    status: DataFileStatus,
    created_at: str,
) -> DataFilePatchRecord:
    """Build and validate one pure DATA_FILE_V1 patch record."""
    patch_id = _require_non_empty_string(patch_id, "patch_id")
    operation = _require_choice(
        operation,
        "operation",
        _ALLOWED_OPERATIONS,
    )
    data_kind = _require_choice(
        data_kind,
        "data_kind",
        _ALLOWED_DATA_KINDS,
    )
    workspace_name = _require_non_empty_string(
        workspace_name,
        "workspace_name",
    )
    target_file = _require_non_empty_string(target_file, "target_file")
    candidate_file = _require_non_empty_string(
        candidate_file,
        "candidate_file",
    )
    diff_file = _require_non_empty_string(diff_file, "diff_file")
    semantic_decision = _require_non_empty_string(
        semantic_decision,
        "semantic_decision",
    )
    semantic_review = _require_non_empty_string(
        semantic_review,
        "semantic_review",
    )
    status = _require_choice(status, "status", _ALLOWED_STATUSES)
    created_at = _require_non_empty_string(created_at, "created_at")

    if type(candidate_bytes) is not bytes:
        raise ValueError("candidate_bytes must be bytes exactly.")

    if operation == "CREATE":
        if original_sha256 is not None:
            raise ValueError(
                "original_sha256 must be None for CREATE records."
            )
        normalized_original_sha256 = None
    else:
        normalized_original_sha256 = _require_sha256(
            original_sha256,
            "original_sha256",
        )

    candidate_sha256 = hashlib.sha256(candidate_bytes).hexdigest()

    record = DataFilePatchRecord(
        patch_id=patch_id,
        format_version="DATA_FILE_V1",
        operation=operation,
        data_kind=data_kind,
        workspace_name=workspace_name,
        target_file=target_file,
        original_sha256=normalized_original_sha256,
        candidate_sha256=candidate_sha256,
        candidate_file=candidate_file,
        diff_file=diff_file,
        validation_passed=True,
        semantic_decision=semantic_decision,
        semantic_review=semantic_review,
        status=status,
        created_at=created_at,
    )

    record_data: dict[str, object] = {
        "patch_id": record.patch_id,
        "format_version": record.format_version,
        "operation": record.operation,
        "data_kind": record.data_kind,
        "workspace_name": record.workspace_name,
        "target_file": record.target_file,
        "original_sha256": record.original_sha256,
        "candidate_sha256": record.candidate_sha256,
        "candidate_file": record.candidate_file,
        "diff_file": record.diff_file,
        "validation_passed": record.validation_passed,
        "semantic_decision": record.semantic_decision,
        "semantic_review": record.semantic_review,
        "status": record.status,
        "created_at": record.created_at,
    }

    try:
        parsed_record = data_file_patch_record_from_dict(record_data)
    except RuntimeError as exc:
        raise ValueError(str(exc)) from exc

    if parsed_record != record:
        raise ValueError("Validated record does not match constructed record.")

    return parsed_record