from app.data_file_types import DataFileKind
from app.data_file_candidate import (
    canonicalize_roadmap_data_candidate,
)


def build_roadmap_candidate_bytes(
    *,
    data_kind: DataFileKind,
    value: dict[str, object],
) -> bytes:
    """Build canonical validated bytes for one roadmap data candidate."""
    if type(data_kind) is not str:
        raise ValueError("data_kind must be exactly a string.")

    if data_kind not in {"MASTER_ROADMAP", "PROJECT_ROADMAP"}:
        raise ValueError("data_kind must be a supported roadmap kind.")

    if type(value) is not dict:
        raise ValueError("value must be exactly a dict.")

    result = canonicalize_roadmap_data_candidate(
        data_kind=data_kind,
        value=value,
    )

    if type(result) is not bytes:
        raise RuntimeError("Canonical roadmap candidate must be exactly bytes.")

    if not result:
        raise RuntimeError("Canonical roadmap candidate must not be empty.")

    return result