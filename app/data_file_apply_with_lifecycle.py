from __future__ import annotations

from pathlib import Path

from app.data_file_types import DataFilePatchRecord
from app.data_file_record_store import load_data_file_patch_record
from app.data_file_apply import apply_approved_data_file
from app.data_file_apply_lifecycle import data_file_post_apply_statuses
from app.data_file_record_transition_write import (
    persist_data_file_patch_record_transition,
)


def apply_approved_data_file_with_lifecycle(
    *,
    queue_path: Path,
    expected_current_bytes: bytes,
    record: DataFilePatchRecord,
    candidate_path: Path,
) -> DataFilePatchRecord:
    """Apply one approved DATA_FILE_V1 operation and persist its lifecycle."""
    if not isinstance(queue_path, Path):
        raise ValueError("queue_path must be a pathlib.Path instance.")

    if type(expected_current_bytes) is not bytes:
        raise ValueError("expected_current_bytes must be exactly bytes.")

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

    loaded_record = load_data_file_patch_record(queue_path)

    if loaded_record != record:
        raise ValueError("loaded record does not match the supplied record.")

    if queue_path.read_bytes() != expected_current_bytes:
        raise ValueError("queue bytes do not match expected current bytes.")

    apply_approved_data_file(
        record=record,
        candidate_path=candidate_path,
    )

    current_record = record
    current_bytes = expected_current_bytes

    for next_status in data_file_post_apply_statuses(
        operation=record.operation,
    ):
        current_record = persist_data_file_patch_record_transition(
            path=queue_path,
            expected_current_bytes=current_bytes,
            record=current_record,
            next_status=next_status,
        )
        current_bytes = queue_path.read_bytes()

    if current_record.status != "APPLIED":
        raise RuntimeError("Final lifecycle status must be APPLIED.")

    persisted_record = load_data_file_patch_record(queue_path)

    if persisted_record != current_record:
        raise RuntimeError(
            "persisted record does not match the final lifecycle record."
        )

    if persisted_record.status != "APPLIED":
        raise RuntimeError("Persisted lifecycle status must be APPLIED.")

    return persisted_record