from __future__ import annotations

import json
from pathlib import Path

from app.data_file_record import data_file_patch_record_from_dict
from app.data_file_types import DataFilePatchRecord


def load_data_file_patch_record(
    path: Path,
) -> DataFilePatchRecord:
    """Load and validate a DATA_FILE_V1 queue-record JSON file."""
    if not isinstance(path, Path):
        raise ValueError("path must be a pathlib.Path instance.")

    if not path.exists():
        raise ValueError("path must exist.")

    if not path.is_file():
        raise ValueError("path must be a regular file.")

    raw = path.read_bytes()

    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("UTF-8 BOM is not allowed.")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(str(exc)) from None

    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(str(exc)) from None

    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object.")

    try:
        record = data_file_patch_record_from_dict(value)
    except RuntimeError as exc:
        raise ValueError(str(exc)) from None

    return record