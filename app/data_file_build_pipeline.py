from __future__ import annotations

from pathlib import Path

from app.data_file_artifact_write import (
    write_new_data_file_artifacts,
)
from app.data_file_record_create_write import (
    write_new_data_file_patch_record,
)
from app.data_file_record_factory import (
    build_data_file_patch_record,
)
from app.data_file_record_store import (
    load_data_file_patch_record,
)
from app.data_file_types import (
    DataFileKind,
    DataFileOperation,
    DataFilePatchRecord,
    DataFileStatus,
)


def build_data_file_patch(
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
    candidate_bytes: bytes,
    diff_bytes: bytes,
    candidate_file: str,
    diff_file: str,
    semantic_decision: str,
    semantic_review: str,
    status: DataFileStatus,
    created_at: str,
) -> DataFilePatchRecord:
    """Build and publish one DATA_FILE_V1 patch and queue record."""
    if not isinstance(queue_path, Path):
        raise ValueError("queue_path must be a pathlib.Path instance.")

    if not isinstance(candidate_path, Path):
        raise ValueError("candidate_path must be a pathlib.Path instance.")

    if not isinstance(diff_path, Path):
        raise ValueError("diff_path must be a pathlib.Path instance.")

    if type(candidate_bytes) is not bytes:
        raise ValueError("candidate_bytes must be exactly bytes.")

    if type(diff_bytes) is not bytes:
        raise ValueError("diff_bytes must be exactly bytes.")

    if (
        queue_path == candidate_path
        or queue_path == diff_path
        or candidate_path == diff_path
    ):
        raise ValueError(
            "queue_path, candidate_path, and diff_path must be distinct."
        )

    if Path(candidate_file).name != candidate_path.name:
        raise ValueError(
            "candidate_file must match candidate_path by filename."
        )

    if Path(diff_file).name != diff_path.name:
        raise ValueError("diff_file must match diff_path by filename.")

    for path, label in (
        (queue_path, "queue_path"),
        (candidate_path, "candidate_path"),
        (diff_path, "diff_path"),
    ):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"{label} must not already exist.")

        if not path.parent.exists():
            raise ValueError(f"{label}.parent must exist.")

        if not path.parent.is_dir():
            raise ValueError(f"{label}.parent must be a directory.")

    record = build_data_file_patch_record(
        patch_id=patch_id,
        operation=operation,
        data_kind=data_kind,
        workspace_name=workspace_name,
        target_file=target_file,
        original_sha256=original_sha256,
        candidate_bytes=candidate_bytes,
        candidate_file=candidate_file,
        diff_file=diff_file,
        semantic_decision=semantic_decision,
        semantic_review=semantic_review,
        status=status,
        created_at=created_at,
    )

    write_new_data_file_artifacts(
        candidate_path=candidate_path,
        candidate_bytes=candidate_bytes,
        diff_path=diff_path,
        diff_bytes=diff_bytes,
    )

    write_new_data_file_patch_record(
        path=queue_path,
        record=record,
    )

    loaded_record = load_data_file_patch_record(queue_path)

    if loaded_record != record:
        raise RuntimeError(
            "Reloaded queue record does not match the built record."
        )

    return loaded_record