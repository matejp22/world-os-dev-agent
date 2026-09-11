from __future__ import annotations

from pathlib import Path

from app.data_file_record_store import load_data_file_patch_record
from app.data_file_record_transition import (
    transition_data_file_patch_record,
)
from app.data_file_record_write import (
    write_existing_data_file_patch_record,
)
from app.data_file_types import (
    DataFilePatchRecord,
    DataFileStatus,
)


def persist_data_file_patch_record_transition(
    *,
    path: Path,
    expected_current_bytes: bytes,
    record: DataFilePatchRecord,
    next_status: DataFileStatus,
) -> DataFilePatchRecord:
    """Persist one explicitly requested DATA_FILE_V1 status transition."""
    if not isinstance(path, Path):
        raise ValueError("path must be a pathlib.Path instance.")

    if type(expected_current_bytes) is not bytes:
        raise ValueError("expected_current_bytes must be exactly bytes.")

    if not isinstance(record, DataFilePatchRecord):
        raise ValueError(
            "record must be a DataFilePatchRecord instance."
        )

    if type(next_status) is not str:
        raise ValueError("next_status must be exactly str.")

    loaded_record = load_data_file_patch_record(path)

    if loaded_record != record:
        raise ValueError(
            "loaded record does not match the supplied record."
        )

    transitioned_record = transition_data_file_patch_record(
        record=record,
        next_status=next_status,
    )

    write_existing_data_file_patch_record(
        path=path,
        expected_current_bytes=expected_current_bytes,
        record=transitioned_record,
    )

    persisted_record = load_data_file_patch_record(path)

    if persisted_record != transitioned_record:
        raise RuntimeError(
            "persisted record does not match the transitioned record."
        )

    return persisted_record