from __future__ import annotations

import json

from app.data_file_validator import validate_roadmap_data_candidate


_SUPPORTED_DATA_KINDS = frozenset(
    {
        "MASTER_ROADMAP",
        "PROJECT_ROADMAP",
    }
)


def canonicalize_roadmap_data_candidate(
    *,
    data_kind: str,
    value: dict[str, object],
) -> bytes:
    """Validate and canonicalize an in-memory roadmap data candidate."""
    if not isinstance(data_kind, str) or not data_kind:
        raise RuntimeError("data_kind must be a non-empty string.")

    if data_kind not in _SUPPORTED_DATA_KINDS:
        raise RuntimeError(
            f"Unsupported roadmap data_kind: {data_kind!r}"
        )

    if type(value) is not dict:
        raise RuntimeError("value must be a dict exactly.")

    try:
        candidate_bytes = (
            json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise RuntimeError(
            "value could not be serialized as canonical JSON."
        ) from exc

    validate_roadmap_data_candidate(
        data_kind=data_kind,
        candidate_bytes=candidate_bytes,
    )

    return candidate_bytes