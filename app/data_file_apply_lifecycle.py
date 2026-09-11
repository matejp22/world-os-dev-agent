from __future__ import annotations

from app.data_file_types import (
    DataFileOperation,
    DataFileStatus,
)


def data_file_post_apply_statuses(
    *,
    operation: DataFileOperation,
) -> tuple[DataFileStatus, DataFileStatus, DataFileStatus]:
    """Return the verified post-apply lifecycle sequence for an operation."""
    if type(operation) is not str:
        raise ValueError("operation must be exactly str.")

    if operation == "CREATE":
        return (
            "APPLYING",
            "CREATED_VERIFIED",
            "APPLIED",
        )

    if operation == "REPLACE":
        return (
            "APPLYING",
            "REPLACED_VERIFIED",
            "APPLIED",
        )

    raise ValueError(f"Unsupported operation: {operation!r}.")