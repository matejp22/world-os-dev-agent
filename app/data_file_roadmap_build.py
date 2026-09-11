from pathlib import Path

from app.data_file_types import (
    DataFileKind,
    DataFileOperation,
    DataFilePatchRecord,
    DataFileStatus,
)

from app.data_file_roadmap_candidate import (
    build_roadmap_candidate_bytes,
)

from app.data_file_build_pipeline import (
    build_data_file_patch,
)


def build_roadmap_data_file_patch(
    *,
    queue_path: Path,
    candidate_path: Path,
    diff_path: Path,
    patch_id: str,
    operation: DataFileOperation,
    data_kind: DataFileKind,
    workspace_name: str,
    target_file: str,
    original_sha256: str | None,
    roadmap_value: dict[str, object],
    diff_bytes: bytes,
    candidate_file: str,
    diff_file: str,
    semantic_decision: str,
    semantic_review: str,
    status: DataFileStatus,
    created_at: str,
) -> DataFilePatchRecord:
    """Build and publish one validated roadmap DATA_FILE_V1 patch."""
    if not isinstance(queue_path, Path):
        raise ValueError("queue_path must be a pathlib.Path instance.")

    if not isinstance(candidate_path, Path):
        raise ValueError("candidate_path must be a pathlib.Path instance.")

    if not isinstance(diff_path, Path):
        raise ValueError("diff_path must be a pathlib.Path instance.")

    if type(roadmap_value) is not dict:
        raise ValueError("roadmap_value must be exactly a dict.")

    if type(diff_bytes) is not bytes:
        raise ValueError("diff_bytes must be exactly bytes.")

    candidate_bytes = build_roadmap_candidate_bytes(
        data_kind=data_kind,
        value=roadmap_value,
    )

    if type(candidate_bytes) is not bytes:
        raise RuntimeError(
            "Roadmap candidate builder must return exactly bytes."
        )

    if not candidate_bytes:
        raise RuntimeError(
            "Roadmap candidate builder must return non-empty bytes."
        )

    record = build_data_file_patch(
        queue_path=queue_path,
        candidate_path=candidate_path,
        diff_path=diff_path,
        patch_id=patch_id,
        operation=operation,
        data_kind=data_kind,
        workspace_name=workspace_name,
        target_file=target_file,
        original_sha256=original_sha256,
        candidate_bytes=candidate_bytes,
        diff_bytes=diff_bytes,
        candidate_file=candidate_file,
        diff_file=diff_file,
        semantic_decision=semantic_decision,
        semantic_review=semantic_review,
        status=status,
        created_at=created_at,
    )

    if not isinstance(record, DataFilePatchRecord):
        raise RuntimeError(
            "Data file build pipeline must return a DataFilePatchRecord."
        )

    return record