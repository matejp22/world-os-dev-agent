from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.data_file_candidate_verify import verify_data_file_candidate
from app.data_file_record_store import load_data_file_patch_record
from app.data_file_record_transition_write import (
    persist_data_file_patch_record_transition,
)
from app.data_file_target import resolve_roadmap_data_target
from app.data_file_types import DataFilePatchRecord


DataFileRecoveryStatus = Literal[
    "RECOVERED_TO_APPLIED",
    "ALREADY_APPLIED",
    "NOT_RECOVERABLE",
]


@dataclass(frozen=True)
class DataFileRecoveryResult:
    patch_id: str
    operation: str
    initial_status: str
    final_status: str
    recovery_status: DataFileRecoveryStatus
    target_file: str
    candidate_sha256: str
    observed_target_sha256: str
    reason: str


@dataclass(frozen=True)
class _TargetObservation:
    readable: bool
    target_bytes: bytes
    sha256: str


def _observe_target(record: DataFilePatchRecord) -> _TargetObservation:
    try:
        target = resolve_roadmap_data_target(
            workspace_name=record.workspace_name,
            target_file=record.target_file,
            must_exist=True,
        )
    except (RuntimeError, ValueError):
        return _TargetObservation(False, b"", "")

    try:
        if target.is_symlink() or not target.is_file():
            return _TargetObservation(False, b"", "")
        target_bytes = target.read_bytes()
    except OSError:
        return _TargetObservation(False, b"", "")

    return _TargetObservation(
        True,
        target_bytes,
        hashlib.sha256(target_bytes).hexdigest(),
    )


def _result(
    *,
    record: DataFilePatchRecord,
    recovery_status: DataFileRecoveryStatus,
    final_status: str,
    observed_target_sha256: str,
    reason: str,
) -> DataFileRecoveryResult:
    return DataFileRecoveryResult(
        patch_id=record.patch_id,
        operation=record.operation,
        initial_status=record.status,
        final_status=final_status,
        recovery_status=recovery_status,
        target_file=record.target_file,
        candidate_sha256=record.candidate_sha256,
        observed_target_sha256=observed_target_sha256,
        reason=reason,
    )


def recover_data_file_partial_state(
    *,
    queue_path: Path,
    expected_current_bytes: bytes,
    record: DataFilePatchRecord,
    candidate_path: Path,
) -> DataFileRecoveryResult:
    if not isinstance(queue_path, Path):
        raise ValueError("queue_path must be a pathlib.Path instance.")
    if type(expected_current_bytes) is not bytes:
        raise ValueError("expected_current_bytes must be exactly bytes.")
    if not isinstance(record, DataFilePatchRecord):
        raise ValueError("record must be a DataFilePatchRecord instance.")
    if not isinstance(candidate_path, Path):
        raise ValueError("candidate_path must be a pathlib.Path instance.")
    if record.format_version != "DATA_FILE_V1":
        raise ValueError("record.format_version must be DATA_FILE_V1.")
    if record.validation_passed is not True:
        raise ValueError("record.validation_passed must be exactly True.")
    if record.semantic_decision != "APPROVE_FOR_HUMAN_REVIEW":
        raise ValueError(
            "record.semantic_decision must be APPROVE_FOR_HUMAN_REVIEW."
        )

    loaded_record = load_data_file_patch_record(queue_path)
    if loaded_record != record:
        raise ValueError("loaded record does not match the supplied record.")

    current_queue_bytes = queue_path.read_bytes()
    if current_queue_bytes != expected_current_bytes:
        raise ValueError("current queue bytes do not match expected bytes.")

    supported = {
        "APPROVED",
        "APPLYING",
        "CREATED_VERIFIED",
        "REPLACED_VERIFIED",
        "APPLIED",
    }
    if record.status not in supported:
        return _result(
            record=record,
            recovery_status="NOT_RECOVERABLE",
            final_status=record.status,
            observed_target_sha256="",
            reason="Unsupported lifecycle status.",
        )

    if record.status == "CREATED_VERIFIED" and record.operation != "CREATE":
        return _result(
            record=record,
            recovery_status="NOT_RECOVERABLE",
            final_status=record.status,
            observed_target_sha256="",
            reason="Operation/status mismatch.",
        )
    if record.status == "REPLACED_VERIFIED" and record.operation != "REPLACE":
        return _result(
            record=record,
            recovery_status="NOT_RECOVERABLE",
            final_status=record.status,
            observed_target_sha256="",
            reason="Operation/status mismatch.",
        )

    observation = _observe_target(record)

    if record.status == "APPLIED":
        if (
            observation.readable
            and observation.sha256 == record.candidate_sha256
        ):
            return _result(
                record=record,
                recovery_status="ALREADY_APPLIED",
                final_status="APPLIED",
                observed_target_sha256=observation.sha256,
                reason="Target already matches the applied candidate.",
            )
        return _result(
            record=record,
            recovery_status="NOT_RECOVERABLE",
            final_status="APPLIED",
            observed_target_sha256=observation.sha256,
            reason="Applied target integrity could not be proven.",
        )

    candidate_bytes = verify_data_file_candidate(
        record=record,
        candidate_path=candidate_path,
    )

    if (
        not observation.readable
        or observation.sha256 != record.candidate_sha256
        or observation.target_bytes != candidate_bytes
    ):
        return _result(
            record=record,
            recovery_status="NOT_RECOVERABLE",
            final_status=record.status,
            observed_target_sha256=observation.sha256,
            reason="Existing target does not exactly match the candidate.",
        )

    transitions: list[str] = []
    if record.status == "APPROVED":
        transitions.append("APPLYING")
    if record.status in {"APPROVED", "APPLYING"}:
        transitions.append(
            "CREATED_VERIFIED"
            if record.operation == "CREATE"
            else "REPLACED_VERIFIED"
        )
    transitions.append("APPLIED")

    current_record = record
    for next_status in transitions:
        current_record = persist_data_file_patch_record_transition(
            path=queue_path,
            expected_current_bytes=current_queue_bytes,
            record=current_record,
            next_status=next_status,
        )
        current_queue_bytes = queue_path.read_bytes()

    if current_record.status != "APPLIED":
        raise RuntimeError("Final recovery record is not APPLIED.")

    final_record = load_data_file_patch_record(queue_path)
    if final_record != current_record:
        raise RuntimeError("Final recovery record changed unexpectedly.")

    final_queue_bytes = queue_path.read_bytes()
    if final_queue_bytes != current_queue_bytes:
        raise RuntimeError("Final queue bytes changed unexpectedly.")

    final_observation = _observe_target(record)
    if (
        not final_observation.readable
        or final_observation.sha256 != record.candidate_sha256
        or final_observation.target_bytes != candidate_bytes
    ):
        raise RuntimeError(
            "Target changed or could not be proven after lifecycle recovery."
        )

    return _result(
        record=record,
        recovery_status="RECOVERED_TO_APPLIED",
        final_status="APPLIED",
        observed_target_sha256=final_observation.sha256,
        reason=(
            "Target integrity was already proven; only persisted lifecycle "
            "state was recovered."
        ),
    )