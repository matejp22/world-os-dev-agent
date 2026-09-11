from __future__ import annotations

import json
from typing import Any

from app.master_roadmap_store import master_roadmap_from_dict
from app.roadmap_store import project_roadmap_from_dict


_SUPPORTED_DATA_KINDS = frozenset(
    {
        "MASTER_ROADMAP",
        "PROJECT_ROADMAP",
    }
)

_UTF8_BOM = b"\xef\xbb\xbf"


def validate_roadmap_data_candidate(
    *,
    data_kind: str,
    candidate_bytes: bytes,
) -> object:
    """Validate read-only roadmap candidate bytes using canonical parsers."""
    if not isinstance(data_kind, str) or not data_kind.strip():
        raise RuntimeError("data_kind must be a non-empty string.")

    if data_kind not in _SUPPORTED_DATA_KINDS:
        raise RuntimeError(
            f"Unsupported roadmap data_kind: {data_kind!r}"
        )

    if type(candidate_bytes) is not bytes:
        raise RuntimeError("candidate_bytes must be bytes exactly.")

    if candidate_bytes.startswith(_UTF8_BOM):
        raise RuntimeError("UTF-8 BOM is not permitted.")

    try:
        text = candidate_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise RuntimeError(
            "Candidate bytes are not valid UTF-8."
        ) from exc

    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Candidate contains malformed JSON."
        ) from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("Candidate JSON root must be an object.")

    if data_kind == "MASTER_ROADMAP":
        return master_roadmap_from_dict(parsed)

    return project_roadmap_from_dict(parsed)