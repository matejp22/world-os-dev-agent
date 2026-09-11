from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from app.data_file_record import data_file_patch_record_from_dict
from app.data_file_types import DataFilePatchRecord


def write_existing_data_file_patch_record(
    *,
    path: Path,
    expected_current_bytes: bytes,
    record: DataFilePatchRecord,
) -> None:
    """Atomically replace one existing DATA_FILE_V1 queue-record file."""
    if not isinstance(path, Path):
        raise ValueError("path must be a pathlib.Path instance.")

    if type(expected_current_bytes) is not bytes:
        raise ValueError("expected_current_bytes must be exactly bytes.")

    if not isinstance(record, DataFilePatchRecord):
        raise ValueError(
            "record must be a DataFilePatchRecord instance."
        )

    if not path.exists():
        raise ValueError("path must exist.")

    if not path.is_file():
        raise ValueError("path must be a regular file.")

    if path.is_symlink():
        raise ValueError("path must not be a symlink.")

    if not path.parent.exists():
        raise ValueError("path.parent must exist.")

    if not path.parent.is_dir():
        raise ValueError("path.parent must be a directory.")

    current_bytes = path.read_bytes()

    if current_bytes != expected_current_bytes:
        raise ValueError("path contents do not match expected_current_bytes.")

    value = {
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
        data_file_patch_record_from_dict(value)
    except RuntimeError as exc:
        raise ValueError(str(exc)) from None

    serialized_bytes = (
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")

    temp_path: str | None = None

    try:
        file_descriptor, temp_path = tempfile.mkstemp(
            dir=path.parent,
        )

        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(serialized_bytes)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        if not path.exists():
            raise ValueError("path must exist.")

        if not path.is_file():
            raise ValueError("path must be a regular file.")

        if path.is_symlink():
            raise ValueError("path must not be a symlink.")

        current_bytes = path.read_bytes()

        if current_bytes != expected_current_bytes:
            raise ValueError("path contents do not match expected_current_bytes.")

        os.replace(temp_path, path)
        temp_path = None

        if not path.exists():
            raise RuntimeError("published path does not exist.")

        if not path.is_file():
            raise RuntimeError("published path is not a regular file.")

        if path.is_symlink():
            raise RuntimeError("published path is a symlink.")

        if path.read_bytes() != serialized_bytes:
            raise RuntimeError("published bytes failed integrity verification.")
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass