from __future__ import annotations

import hashlib
from pathlib import Path

from app.full_file_approval import load_record
from app.full_file_apply_v2 import atomic_write_json
from app.patch_quality_evidence_runner import (
    PatchQualityExecutionResult,
    quality_evidence_payload,
)


_EXPECTED_PAYLOAD_KEYS = frozenset(
    {
        "focused_tests_executed",
        "focused_tests_passed",
        "regression_tests_executed",
        "regression_tests_passed",
    }
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _required_string(record: dict, name: str) -> str:
    value = record.get(name)

    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{name} must be a non-empty string.")

    return value.strip()


def _result_string(result: PatchQualityExecutionResult, name: str) -> str:
    value = getattr(result, name)

    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Result {name} must be a non-empty string.")

    return value.strip()


def _validate_payload(result: PatchQualityExecutionResult) -> dict[str, bool]:
    payload = quality_evidence_payload(result)

    if set(payload) != _EXPECTED_PAYLOAD_KEYS:
        raise RuntimeError("Quality evidence payload keys are invalid.")

    if any(type(value) is not bool for value in payload.values()):
        raise RuntimeError("Quality evidence payload values must be bool.")

    return payload


def _verify_candidate(record: dict) -> tuple[str, Path, str]:
    candidate_file = _required_string(record, "candidate_file")
    candidate_sha256 = _required_string(record, "candidate_sha256")
    candidate_path = Path(candidate_file)

    if not candidate_path.exists():
        raise RuntimeError("Candidate artifact does not exist.")

    if not candidate_path.is_file():
        raise RuntimeError("Candidate artifact is not a regular file.")

    if _sha256_file(candidate_path) != candidate_sha256:
        raise RuntimeError("Candidate artifact SHA256 does not match.")

    return candidate_file, candidate_path, candidate_sha256


def _verify_reload(
    *,
    original_queue_file: Path,
    reloaded_queue_file: Path,
    record: dict,
    workspace_name: str,
    target_file: str,
    payload: dict[str, bool],
    candidate_file: str,
    candidate_sha256: str,
) -> None:
    if reloaded_queue_file != original_queue_file:
        raise RuntimeError("Reloaded queue path does not match.")

    if not isinstance(record, dict):
        raise RuntimeError("Reloaded patch record must be an object.")

    if record.get("status") != "READY_FOR_HUMAN_REVIEW":
        raise RuntimeError("Patch status changed during persistence.")

    if record.get("workspace_name") != workspace_name:
        raise RuntimeError("Reloaded workspace_name does not match.")

    if record.get("target_file") != target_file:
        raise RuntimeError("Reloaded target_file does not match.")

    if record.get("quality_evidence") != payload:
        raise RuntimeError("Reloaded quality evidence does not match.")

    if record.get("candidate_file") != candidate_file:
        raise RuntimeError("Reloaded candidate_file changed.")

    if record.get("candidate_sha256") != candidate_sha256:
        raise RuntimeError("Reloaded candidate_sha256 changed.")

    _verify_candidate(record)


def persist_patch_quality_evidence(
    *,
    patch_id: str,
    result: PatchQualityExecutionResult,
) -> tuple[Path, dict]:
    if not isinstance(patch_id, str):
        raise TypeError("patch_id must be a string.")

    canonical_patch_id = patch_id.strip()

    if not canonical_patch_id:
        raise ValueError("patch_id must not be empty.")

    if not isinstance(result, PatchQualityExecutionResult):
        raise TypeError(
            "result must be a PatchQualityExecutionResult instance."
        )

    if result.execution_supported is not True:
        raise RuntimeError("Patch quality execution is not trusted.")

    result_workspace_name = _result_string(result, "workspace_name")
    result_target_file = _result_string(result, "target_file")

    queue_file, record = load_record(canonical_patch_id)

    if not isinstance(record, dict):
        raise RuntimeError("Patch record must be an object.")

    if record.get("status") != "READY_FOR_HUMAN_REVIEW":
        raise RuntimeError("Patch is not READY_FOR_HUMAN_REVIEW.")

    if record.get("quality_evidence") is not None:
        raise RuntimeError("Patch already contains quality evidence.")

    workspace_name = _required_string(record, "workspace_name")
    target_file = _required_string(record, "target_file")

    if workspace_name != result_workspace_name:
        raise RuntimeError("Result workspace_name does not match patch record.")

    if target_file != result_target_file:
        raise RuntimeError("Result target_file does not match patch record.")

    candidate_file, candidate_path, candidate_sha256 = _verify_candidate(record)
    payload = _validate_payload(result)

    updated_record = dict(record)
    updated_record["quality_evidence"] = payload

    atomic_write_json(queue_file, updated_record)

    reloaded_queue_file, reloaded_record = load_record(canonical_patch_id)

    _verify_reload(
        original_queue_file=queue_file,
        reloaded_queue_file=reloaded_queue_file,
        record=reloaded_record,
        workspace_name=workspace_name,
        target_file=target_file,
        payload=payload,
        candidate_file=candidate_file,
        candidate_sha256=candidate_sha256,
    )

    if _sha256_file(candidate_path) != candidate_sha256:
        raise RuntimeError("Candidate artifact changed after persistence.")

    return reloaded_queue_file, reloaded_record