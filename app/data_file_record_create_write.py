from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from app.data_file_record import data_file_patch_record_from_dict
from app.data_file_types import DataFilePatchRecord


def write_new_data_file_patch_record(
    *,
    path: Path,
    record: DataFilePatchRecord,
) -> None:
    """Atomically create one new DATA_FILE_V1 queue-record file."""
    if not isinstance(path, Path):
        raise ValueError("path must be a pathlib.Path instance.")

    if not isinstance(record, DataFilePatchRecord):
        raise ValueError(
            "record must be a DataFilePatchRecord instance."
        )

    if path.exists() or path.is_symlink():
        raise FileExistsError("path must not already exist.")

    if not path.parent.exists():
        raise ValueError("path.parent must exist.")

    if not path.parent.is_dir():
        raise ValueError("path.parent must be a directory.")

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
        reconstructed_record = data_file_patch_record_from_dict(value)
    except RuntimeError as exc:
        raise ValueError(str(exc)) from None

    if reconstructed_record != record:
        raise ValueError(
            "serialized record does not match the supplied record."
        )

    serialized_bytes = (
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")

    temporary_path: Path | None = None

    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
        )
        temporary_path = Path(temporary_name)

        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(serialized_bytes)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        if path.exists() or path.is_symlink():
            raise FileExistsError("path must not already exist.")

        try:
            os.link(temporary_path, path)
        except FileExistsError:
            raise FileExistsError(
                "path was created concurrently."
            ) from None

        temporary_path.unlink()
        temporary_path = None

        if not path.exists():
            raise RuntimeError("published path does not exist.")

        if not path.is_file():
            raise RuntimeError("published path is not a regular file.")

        if path.is_symlink():
            raise RuntimeError("published path is a symlink.")

        if path.read_bytes() != serialized_bytes:
            raise RuntimeError(
                "published bytes failed integrity verification."
            )
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass