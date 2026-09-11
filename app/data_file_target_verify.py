from __future__ import annotations

import hashlib
from pathlib import Path

from app.data_file_types import DataFilePatchRecord


def verify_data_file_target_state(
    *,
    record: DataFilePatchRecord,
    target_path: Path,
) -> None:
    """Verify the explicitly supplied DATA_FILE_V1 target state."""
    if not isinstance(record, DataFilePatchRecord):
        raise ValueError("record must be a DataFilePatchRecord instance.")

    if not isinstance(target_path, Path):
        raise ValueError("target_path must be a pathlib.Path instance.")

    if record.operation == "CREATE":
        if target_path.exists() or target_path.is_symlink():
            raise ValueError("CREATE target already exists.")
        return None

    if record.operation == "REPLACE":
        if target_path.is_symlink():
            raise ValueError("REPLACE target must not be a symlink.")

        if not target_path.exists():
            raise ValueError("REPLACE target does not exist.")

        if not target_path.is_file():
            raise ValueError("REPLACE target is not a regular file.")

        if record.original_sha256 is None:
            raise ValueError("REPLACE record is missing original_sha256.")

        target_bytes = target_path.read_bytes()
        target_sha256 = hashlib.sha256(target_bytes).hexdigest()

        if target_sha256.lower() != record.original_sha256.lower():
            raise ValueError("REPLACE target SHA256 does not match the record.")

        return None

    raise ValueError("Unsupported data file operation.")