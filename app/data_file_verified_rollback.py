from __future__ import annotations
import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from app.data_file_record_store import load_data_file_patch_record
from app.data_file_record_transition_write import persist_data_file_patch_record_transition
from app.data_file_target import resolve_roadmap_data_target
from app.data_file_types import DataFilePatchRecord

DataFileRollbackStatus = Literal[
    "ROLLBACK_ARTIFACT_CREATED", "ROLLBACK_ARTIFACT_VERIFIED",
    "ROLLED_BACK", "ALREADY_ROLLED_BACK", "NOT_ROLLBACKABLE",
]

@dataclass(frozen=True)
class DataFileRollbackArtifactResult:
    patch_id: str
    target_file: str
    rollback_artifact: str
    original_sha256: str
    status: DataFileRollbackStatus
    reason: str

@dataclass(frozen=True)
class DataFileRollbackResult:
    patch_id: str
    operation: str
    initial_status: str
    final_status: str
    rollback_status: DataFileRollbackStatus
    target_file: str
    original_sha256: str
    candidate_sha256: str
    observed_target_sha256: str
    reason: str

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _valid_sha(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdefABCDEF" for c in value)

def _read_or_none(path: Path) -> bytes | None:
    try:
        if path.is_symlink() or not path.exists() or not path.is_file():
            return None
        return path.read_bytes()
    except OSError:
        return None
    except ValueError:
        return None

def _strict_read(path: Path) -> bytes:
    try:
        if path.is_symlink() or not path.exists() or not path.is_file():
            raise ValueError("Unsafe file.")
        return path.read_bytes()
    except OSError as exc:
        raise ValueError("File read failed.") from exc

def _safe_dir(path: Path) -> bool:
    try:
        return not path.is_symlink() and path.exists() and path.is_dir()
    except OSError:
        return False
    except ValueError:
        return False

def _cleanup(path: Path | None) -> None:
    if path is None:
        return
    try:
        if path.exists() or path.is_symlink():
            path.unlink()
    except OSError:
        return
    except ValueError:
        return

def _require_absent(path: Path) -> None:
    try:
        exists = path.exists()
        symlink = path.is_symlink()
    except OSError as exc:
        raise RuntimeError("Absence verification failed.") from exc
    except ValueError as exc:
        raise RuntimeError("Absence verification failed.") from exc
    if exists or symlink:
        raise RuntimeError("Path remains after destructive operation.")

def _cleanup_after_publication(path: Path) -> None:
    try:
        path.unlink()
    except OSError as exc:
        raise RuntimeError("Published temp cleanup failed.") from exc
    except ValueError as exc:
        raise RuntimeError("Published temp cleanup failed.") from exc
    _require_absent(path)

def _stage(parent: Path, data: bytes, expected_sha: str) -> Path:
    fd = -1
    staged: Path | None = None
    try:
        fd, raw = tempfile.mkstemp(prefix=".data-file-rollback-", dir=parent)
        staged = Path(raw)
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        observed = _strict_read(staged)
        if observed != data or _sha(observed) != expected_sha:
            raise ValueError("Staged bytes failed verification.")
        return staged
    except OSError as exc:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        _cleanup(staged)
        raise ValueError("Staging failed.") from exc
    except ValueError:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        _cleanup(staged)
        raise

def _result(record: DataFilePatchRecord, rollback_status: DataFileRollbackStatus,
            final_status: str, observed: str = "", reason: str = "") -> DataFileRollbackResult:
    return DataFileRollbackResult(
        record.patch_id, record.operation, record.status, final_status, rollback_status,
        record.target_file, record.original_sha256, record.candidate_sha256, observed, reason,
    )

def _nr(record: DataFilePatchRecord, reason: str, observed: str = "") -> DataFileRollbackResult:
    return _result(record, "NOT_ROLLBACKABLE", record.status, observed, reason)

def _persist(queue_path: Path, expected_current_bytes: bytes, record: DataFilePatchRecord) -> None:
    transitioned = persist_data_file_patch_record_transition(
        path=queue_path,
        expected_current_bytes=expected_current_bytes,
        record=record,
        next_status="ROLLED_BACK",
    )
    current_queue_bytes = queue_path.read_bytes()
    reloaded = load_data_file_patch_record(queue_path)
    if reloaded != transitioned:
        raise RuntimeError("Reloaded record differs from transition.")
    if reloaded.status != "ROLLED_BACK":
        raise RuntimeError("Persisted status is not ROLLED_BACK.")
    final_queue_bytes = queue_path.read_bytes()
    if final_queue_bytes != current_queue_bytes:
        raise RuntimeError("Queue changed during rollback verification.")

def prepare_data_file_rollback_artifact(
    *,
    record: DataFilePatchRecord,
    rollback_artifact_path: Path,
) -> DataFileRollbackArtifactResult:
    if not isinstance(record, DataFilePatchRecord):
        raise ValueError("record must be DataFilePatchRecord.")
    if not isinstance(rollback_artifact_path, Path):
        raise ValueError("rollback_artifact_path must be Path.")
    if record.format_version != "DATA_FILE_V1":
        raise ValueError("format_version must be DATA_FILE_V1.")
    if record.operation != "REPLACE":
        raise ValueError("operation must be REPLACE.")
    if record.status != "APPROVED":
        raise ValueError("status must be APPROVED.")
    if record.validation_passed is not True:
        raise ValueError("validation_passed must be true.")
    if record.semantic_decision != "APPROVE_FOR_HUMAN_REVIEW":
        raise ValueError("semantic decision must be approved.")
    if not _valid_sha(record.original_sha256):
        raise ValueError("original_sha256 is invalid.")
    try:
        target = resolve_roadmap_data_target(
            record.workspace_name, record.target_file, must_exist=True,
        )
    except RuntimeError as exc:
        raise ValueError("Target resolution failed.") from exc
    original = _strict_read(target)
    if _sha(original) != record.original_sha256:
        raise ValueError("Original target SHA mismatch.")
    parent = rollback_artifact_path.parent
    if not _safe_dir(parent):
        raise ValueError("Rollback artifact parent is unsafe.")
    try:
        exists = rollback_artifact_path.exists()
        symlink = rollback_artifact_path.is_symlink()
    except OSError as exc:
        raise ValueError("Artifact state could not be read.") from exc
    except ValueError as exc:
        raise ValueError("Artifact state could not be read.") from exc
    if exists or symlink:
        existing = _strict_read(rollback_artifact_path)
        if existing != original or _sha(existing) != record.original_sha256:
            raise ValueError("Existing rollback artifact mismatch.")
        return DataFileRollbackArtifactResult(
            record.patch_id, record.target_file, str(rollback_artifact_path),
            record.original_sha256, "ROLLBACK_ARTIFACT_VERIFIED",
            "Existing rollback artifact verified.",
        )
    staged: Path | None = None
    try:
        staged = _stage(parent, original, record.original_sha256)
        try:
            destination_exists = rollback_artifact_path.exists()
            destination_symlink = rollback_artifact_path.is_symlink()
        except OSError as exc:
            raise ValueError("Artifact destination state failed.") from exc
        except ValueError as exc:
            raise ValueError("Artifact destination state failed.") from exc
        if destination_exists or destination_symlink:
            raise ValueError("Artifact destination appeared.")
        try:
            os.link(staged, rollback_artifact_path)
        except OSError as exc:
            raise ValueError("Artifact publication failed.") from exc
        except ValueError as exc:
            raise ValueError("Artifact publication failed.") from exc
    except ValueError:
        _cleanup(staged)
        raise
    _cleanup_after_publication(staged)
    try:
        published = _strict_read(rollback_artifact_path)
    except ValueError as exc:
        raise RuntimeError("Published artifact could not be verified.") from exc
    if published != original or _sha(published) != record.original_sha256:
        raise RuntimeError("Published rollback artifact mismatch.")
    return DataFileRollbackArtifactResult(
        record.patch_id, record.target_file, str(rollback_artifact_path),
        record.original_sha256, "ROLLBACK_ARTIFACT_CREATED",
        "Rollback artifact created and verified.",
    )

def _rollback_create(
    queue_path: Path,
    expected_current_bytes: bytes,
    record: DataFilePatchRecord,
    artifact: Path | None,
) -> DataFileRollbackResult:
    if artifact is not None:
        return _nr(record, "CREATE rollback must not use an artifact.")
    try:
        target = resolve_roadmap_data_target(
            record.workspace_name, record.target_file, must_exist=False,
        )
    except RuntimeError:
        return _nr(record, "Target resolution failed.")
    except ValueError:
        return _nr(record, "Target resolution failed.")
    try:
        exists = target.exists()
        symlink = target.is_symlink()
    except OSError:
        return _nr(record, "Target state is unsafe.")
    except ValueError:
        return _nr(record, "Target state is unsafe.")
    if not exists and not symlink:
        _persist(queue_path, expected_current_bytes, record)
        return _result(record, "ROLLED_BACK", "ROLLED_BACK", reason="Created target already absent.")
    if symlink:
        return _nr(record, "Target is a symlink.")
    current = _read_or_none(target)
    if current is None:
        return _nr(record, "Target cannot be safely read.")
    observed = _sha(current)
    if observed != record.candidate_sha256:
        return _nr(record, "Target is not candidate-owned.", observed)
    try:
        target.unlink()
    except OSError:
        return _nr(record, "Target deletion failed.", observed)
    except ValueError:
        return _nr(record, "Target deletion failed.", observed)
    _require_absent(target)
    _persist(queue_path, expected_current_bytes, record)
    return _result(record, "ROLLED_BACK", "ROLLED_BACK", observed, "Created target removed.")

def _rollback_replace(
    queue_path: Path,
    expected_current_bytes: bytes,
    record: DataFilePatchRecord,
    artifact_path: Path | None,
) -> DataFileRollbackResult:
    if artifact_path is None or not _valid_sha(record.original_sha256):
        return _nr(record, "Verified rollback artifact is required.")
    artifact = _read_or_none(artifact_path)
    if artifact is None or _sha(artifact) != record.original_sha256:
        return _nr(record, "Rollback artifact is invalid.")
    try:
        target = resolve_roadmap_data_target(
            record.workspace_name, record.target_file, must_exist=True,
        )
    except RuntimeError:
        return _nr(record, "Target resolution failed.")
    except ValueError:
        return _nr(record, "Target resolution failed.")
    current = _read_or_none(target)
    if current is None:
        return _nr(record, "Target cannot be safely read.")
    observed = _sha(current)
    if observed == record.original_sha256:
        _persist(queue_path, expected_current_bytes, record)
        return _result(
            record, "ROLLED_BACK", "ROLLED_BACK", observed,
            "Original target already restored.",
        )
    if observed != record.candidate_sha256:
        return _nr(record, "Target is not candidate-owned.", observed)
    if not _safe_dir(target.parent):
        return _nr(record, "Target parent is unsafe.", observed)
    try:
        staged = _stage(target.parent, artifact, record.original_sha256)
    except ValueError:
        return _nr(record, "Restore staging failed.", observed)
    try:
        os.replace(staged, target)
    except OSError:
        _cleanup(staged)
        return _nr(record, "Restore publication failed.", observed)
    except ValueError:
        _cleanup(staged)
        return _nr(record, "Restore publication failed.", observed)
    _require_absent(staged)
    try:
        restored = _strict_read(target)
    except ValueError as exc:
        raise RuntimeError("Restored target could not be verified.") from exc
    if restored != artifact or _sha(restored) != record.original_sha256:
        raise RuntimeError("Restored target mismatch.")
    _persist(queue_path, expected_current_bytes, record)
    return _result(
        record, "ROLLED_BACK", "ROLLED_BACK", record.original_sha256,
        "Original target restored.",
    )

def rollback_data_file_partial_apply(
    *,
    queue_path: Path,
    expected_current_bytes: bytes,
    record: DataFilePatchRecord,
    rollback_artifact_path: Path | None,
) -> DataFileRollbackResult:
    if not isinstance(queue_path, Path):
        raise ValueError("queue_path must be Path.")
    if type(expected_current_bytes) is not bytes:
        raise ValueError("expected_current_bytes must be exactly bytes.")
    if not isinstance(record, DataFilePatchRecord):
        raise ValueError("record must be DataFilePatchRecord.")
    if rollback_artifact_path is not None and not isinstance(rollback_artifact_path, Path):
        raise ValueError("rollback_artifact_path must be Path or None.")
    if record.format_version != "DATA_FILE_V1":
        raise ValueError("format_version must be DATA_FILE_V1.")
    loaded = load_data_file_patch_record(queue_path)
    if loaded != record:
        raise ValueError("Loaded queue record does not match supplied record.")
    current_queue_bytes = queue_path.read_bytes()
    if current_queue_bytes != expected_current_bytes:
        raise ValueError("Queue bytes changed.")
    if record.status == "ROLLED_BACK":
        return _result(
            record, "ALREADY_ROLLED_BACK", "ROLLED_BACK",
            reason="Record is already rolled back.",
        )
    if record.status not in {"APPLYING", "CREATED_VERIFIED", "REPLACED_VERIFIED"}:
        return _nr(record, "Lifecycle status is not rollbackable.")
    if record.status == "CREATED_VERIFIED" and record.operation != "CREATE":
        return _nr(record, "Lifecycle operation mismatch.")
    if record.status == "REPLACED_VERIFIED" and record.operation != "REPLACE":
        return _nr(record, "Lifecycle operation mismatch.")
    if record.operation == "CREATE":
        return _rollback_create(
            queue_path, expected_current_bytes, record, rollback_artifact_path,
        )
    if record.operation == "REPLACE":
        return _rollback_replace(
            queue_path, expected_current_bytes, record, rollback_artifact_path,
        )
    return _nr(record, "Operation is not rollbackable.")