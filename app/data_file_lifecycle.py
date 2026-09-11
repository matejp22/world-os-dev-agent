from __future__ import annotations

from app.data_file_types import DataFileOperation, DataFileStatus


_VALID_STATUSES = frozenset(
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

_VALID_OPERATIONS = frozenset(
    {
        "CREATE",
        "REPLACE",
    }
)

_ALLOWED_TRANSITIONS = {
    "DRAFT": frozenset(
        {
            "READY_FOR_HUMAN_REVIEW",
            "REJECTED",
        }
    ),
    "READY_FOR_HUMAN_REVIEW": frozenset(
        {
            "APPROVED",
            "REJECTED",
        }
    ),
    "APPROVED": frozenset(
        {
            "APPLYING",
        }
    ),
    "APPLYING": frozenset(
        {
            "CREATED_VERIFIED",
            "REPLACED_VERIFIED",
            "ROLLED_BACK",
            "ROLLBACK_FAILED",
        }
    ),
    "CREATED_VERIFIED": frozenset(
        {
            "APPLIED",
            "ROLLED_BACK",
            "ROLLBACK_FAILED",
        }
    ),
    "REPLACED_VERIFIED": frozenset(
        {
            "APPLIED",
            "ROLLED_BACK",
            "ROLLBACK_FAILED",
        }
    ),
    "APPLIED": frozenset(),
    "REJECTED": frozenset(),
    "ROLLED_BACK": frozenset(),
    "ROLLBACK_FAILED": frozenset(),
}


def validate_data_file_status_transition(
    *,
    current_status: DataFileStatus,
    next_status: DataFileStatus,
    operation: DataFileOperation,
) -> None:
    """Validate one DATA_FILE_V1 lifecycle transition."""
    if type(current_status) is not str:
        raise ValueError("current_status must be exactly str.")

    if type(next_status) is not str:
        raise ValueError("next_status must be exactly str.")

    if type(operation) is not str:
        raise ValueError("operation must be exactly str.")

    if current_status not in _VALID_STATUSES:
        raise ValueError(
            f"Unsupported current_status: {current_status!r}."
        )

    if next_status not in _VALID_STATUSES:
        raise ValueError(
            f"Unsupported next_status: {next_status!r}."
        )

    if operation not in _VALID_OPERATIONS:
        raise ValueError(
            f"Unsupported operation: {operation!r}."
        )

    if current_status == next_status:
        raise ValueError("Same-status transitions are not allowed.")

    allowed_next_statuses = _ALLOWED_TRANSITIONS[current_status]

    if next_status not in allowed_next_statuses:
        raise ValueError(
            "Invalid data-file status transition: "
            f"{current_status!r} -> {next_status!r}."
        )

    if current_status == "APPLYING":
        if (
            next_status == "CREATED_VERIFIED"
            and operation != "CREATE"
        ):
            raise ValueError(
                "CREATED_VERIFIED requires operation 'CREATE'."
            )

        if (
            next_status == "REPLACED_VERIFIED"
            and operation != "REPLACE"
        ):
            raise ValueError(
                "REPLACED_VERIFIED requires operation 'REPLACE'."
            )

    return None