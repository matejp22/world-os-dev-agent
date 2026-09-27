from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.data_file_record_store import load_data_file_patch_record
from app.data_file_types import DataFilePatchRecord


_SUPPORTED_RECOVERY_STATUSES = frozenset(
    {
        "APPROVED",
        "APPLYING",
        "CREATED_VERIFIED",
        "REPLACED_VERIFIED",
        "APPLIED",
    }
)


@dataclass(frozen=True)
class DataFileRecoveryQueueEntry:
    queue_path: Path
    record: DataFilePatchRecord
    candidate_path: Path


def discover_data_file_recovery_candidates(
    *,
    queue_dir: Path,
) -> tuple[DataFileRecoveryQueueEntry, ...]:
    if not isinstance(queue_dir, Path):
        raise ValueError("queue_dir must be a pathlib.Path instance.")

    if not queue_dir.exists():
        return ()

    if not queue_dir.is_dir():
        raise ValueError("queue_dir must be a directory.")

    entries: list[DataFileRecoveryQueueEntry] = []

    for queue_path in queue_dir.glob("*.json"):
        try:
            record = load_data_file_patch_record(queue_path)
        except ValueError:
            continue

        if record.status not in _SUPPORTED_RECOVERY_STATUSES:
            continue

        entries.append(
            DataFileRecoveryQueueEntry(
                queue_path=queue_path,
                record=record,
                candidate_path=Path(record.candidate_file),
            )
        )

    entries.sort(key=lambda entry: entry.queue_path.name)
    return tuple(entries)