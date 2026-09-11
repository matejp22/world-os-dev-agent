from __future__ import annotations

import hashlib
from pathlib import Path

from app.data_file_candidate_verify import verify_data_file_candidate
from app.data_file_target import resolve_roadmap_data_target
from app.data_file_target_verify import verify_data_file_target_state
from app.data_file_target_write import write_verified_data_file_target
from app.data_file_types import DataFilePatchRecord


def apply_approved_data_file(
    *,
    record: DataFilePatchRecord,
    candidate_path: Path,
) -> Path:
    """Apply one already-approved DATA_FILE_V1 operation."""
    if not isinstance(record, DataFilePatchRecord):
        raise ValueError("record must be a DataFilePatchRecord instance.")

    if not isinstance(candidate_path, Path):
        raise ValueError("candidate_path must be a pathlib.Path instance.")

    if record.format_version != "DATA_FILE_V1":
        raise ValueError("Unsupported data file format version.")

    if record.status != "APPROVED":
        raise ValueError("Data file record must have APPROVED status.")

    if record.validation_passed is not True:
        raise ValueError("Data file validation must have passed.")

    if record.semantic_decision != "APPROVE_FOR_HUMAN_REVIEW":
        raise ValueError("Data file semantic decision is not approved.")

    if record.operation not in {"CREATE", "REPLACE"}:
        raise ValueError("Unsupported data file operation.")

    target_path = resolve_roadmap_data_target(
        workspace_name=record.workspace_name,
        target_file=record.target_file,
        must_exist=record.operation == "REPLACE",
    )

    candidate_bytes = verify_data_file_candidate(
        record=record,
        candidate_path=candidate_path,
    )

    verify_data_file_target_state(
        record=record,
        target_path=target_path,
    )

    write_verified_data_file_target(
        record=record,
        target_path=target_path,
        candidate_bytes=candidate_bytes,
    )

    if target_path.is_symlink():
        raise RuntimeError("Post-write target must not be a symlink.")

    if not target_path.exists():
        raise RuntimeError("Post-write target does not exist.")

    if not target_path.is_file():
        raise RuntimeError("Post-write target is not a regular file.")

    target_bytes = target_path.read_bytes()

    if target_bytes != candidate_bytes:
        raise RuntimeError("Post-write target bytes do not match the candidate.")

    target_sha256 = hashlib.sha256(target_bytes).hexdigest()

    if target_sha256.lower() != record.candidate_sha256.lower():
        raise RuntimeError("Post-write target SHA256 does not match the record.")

    return target_path