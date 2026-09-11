from __future__ import annotations

import hashlib
from pathlib import Path

from app.data_file_types import DataFilePatchRecord
from app.data_file_validator import validate_roadmap_data_candidate


def verify_data_file_candidate(
    *,
    record: DataFilePatchRecord,
    candidate_path: Path,
) -> bytes:
    """Verify a DATA_FILE_V1 candidate artifact without modifying it."""
    if not isinstance(record, DataFilePatchRecord):
        raise ValueError("record must be a DataFilePatchRecord instance.")

    if not isinstance(candidate_path, Path):
        raise ValueError("candidate_path must be a pathlib.Path instance.")

    if not candidate_path.exists():
        raise ValueError("Candidate file does not exist.")

    if not candidate_path.is_file():
        raise ValueError("Candidate path is not a regular file.")

    candidate_bytes = candidate_path.read_bytes()

    candidate_sha256 = hashlib.sha256(candidate_bytes).hexdigest()

    if candidate_sha256.lower() != record.candidate_sha256.lower():
        raise ValueError("Candidate SHA256 does not match the patch record.")

    try:
        validate_roadmap_data_candidate(
            data_kind=record.data_kind,
            candidate_bytes=candidate_bytes,
        )
    except (RuntimeError, ValueError) as exc:
        raise ValueError("Candidate roadmap data is invalid.") from exc

    return candidate_bytes