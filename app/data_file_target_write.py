from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.data_file_types import DataFilePatchRecord


def write_verified_data_file_target(
    *,
    record: DataFilePatchRecord,
    target_path: Path,
    candidate_bytes: bytes,
) -> None:
    """Atomically publish already-verified DATA_FILE_V1 candidate bytes."""
    if not isinstance(record, DataFilePatchRecord):
        raise ValueError("record must be a DataFilePatchRecord instance.")

    if not isinstance(target_path, Path):
        raise ValueError("target_path must be a pathlib.Path instance.")

    if type(candidate_bytes) is not bytes:
        raise ValueError("candidate_bytes must be exactly bytes.")

    if record.operation not in {"CREATE", "REPLACE"}:
        raise ValueError("Unsupported data file operation.")

    parent = target_path.parent

    if not parent.exists():
        raise ValueError("Target parent directory does not exist.")

    if not parent.is_dir():
        raise ValueError("Target parent is not a directory.")

    if record.operation == "CREATE":
        if target_path.exists() or target_path.is_symlink():
            raise ValueError("CREATE target already exists.")
    else:
        if target_path.is_symlink():
            raise ValueError("REPLACE target must not be a symlink.")

        if not target_path.exists():
            raise ValueError("REPLACE target does not exist.")

        if not target_path.is_file():
            raise ValueError("REPLACE target is not a regular file.")

    temporary_path: Path | None = None

    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target_path.name}.",
            suffix=".tmp",
            dir=str(parent),
        )
        temporary_path = Path(temporary_name)

        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(candidate_bytes)
            handle.flush()
            os.fsync(handle.fileno())

        if record.operation == "REPLACE":
            os.replace(temporary_path, target_path)
            temporary_path = None
            return None

        try:
            os.link(temporary_path, target_path)
        except FileExistsError as exc:
            raise ValueError("CREATE target already exists.") from exc

        temporary_path.unlink()
        temporary_path = None
        return None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass