from __future__ import annotations

from dataclasses import replace

from app.data_file_lifecycle import (
    validate_data_file_status_transition,
)
from app.data_file_types import (
    DataFilePatchRecord,
    DataFileStatus,
)


def transition_data_file_patch_record(
    *,
    record: DataFilePatchRecord,
    next_status: DataFileStatus,
) -> DataFilePatchRecord:
    """Return a new record after a validated lifecycle transition."""
    if not isinstance(record, DataFilePatchRecord):
        raise ValueError(
            "record must be a DataFilePatchRecord instance."
        )

    if type(next_status) is not str:
        raise ValueError("next_status must be exactly str.")

    validate_data_file_status_transition(
        current_status=record.status,
        next_status=next_status,
        operation=record.operation,
    )

    return replace(
        record,
        status=next_status,
    )