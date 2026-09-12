from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Mapping


LifecycleRoadmapSyncStatus = Literal[
    "VERIFIED_FOR_COMPLETION",
    "NOT_VERIFIED",
]

_SUPPORTED_FORMATS = {
    "FULL_FILE_V2",
    "NEW_FILE_V2",
    "DATA_FILE_V1",
}

_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class LifecycleRoadmapSyncDecision:
    patch_id: str
    format_version: str
    target_file: str
    status: LifecycleRoadmapSyncStatus
    verified: bool
    candidate_sha256: str
    observed_target_sha256: str
    reason: str


def _is_sha256(value: object) -> bool:
    return type(value) is str and _SHA256_PATTERN.fullmatch(value) is not None


def _text(value: object) -> str:
    return value if type(value) is str else ""


def _not_verified(
    *,
    patch_id: str,
    format_version: str,
    target_file: str,
    candidate_sha256: str,
    observed_target_sha256: str,
    reason: str,
) -> LifecycleRoadmapSyncDecision:
    return LifecycleRoadmapSyncDecision(
        patch_id=patch_id,
        format_version=format_version,
        target_file=target_file,
        status="NOT_VERIFIED",
        verified=False,
        candidate_sha256=candidate_sha256,
        observed_target_sha256=observed_target_sha256,
        reason=reason,
    )


def evaluate_lifecycle_roadmap_sync(
    *,
    record: Mapping[str, object],
    observed_target_sha256: str,
    expected_patch_id: str,
) -> LifecycleRoadmapSyncDecision:
    if type(expected_patch_id) is not str or not expected_patch_id:
        raise RuntimeError(
            "expected_patch_id must be a non-empty string."
        )

    if not _is_sha256(observed_target_sha256):
        raise RuntimeError(
            "observed_target_sha256 must be exactly 64 hexadecimal characters."
        )

    if not isinstance(record, Mapping):
        raise RuntimeError("record must be a Mapping.")

    patch_id = _text(record.get("patch_id"))
    format_version = _text(record.get("format_version"))
    target_file = _text(record.get("target_file"))
    candidate_sha256 = _text(record.get("candidate_sha256"))

    def reject(reason: str) -> LifecycleRoadmapSyncDecision:
        return _not_verified(
            patch_id=patch_id,
            format_version=format_version,
            target_file=target_file,
            candidate_sha256=candidate_sha256,
            observed_target_sha256=observed_target_sha256,
            reason=reason,
        )

    if not patch_id:
        return reject("patch_id is missing or invalid.")

    if patch_id != expected_patch_id:
        return reject("patch_id does not match expected_patch_id.")

    if format_version not in _SUPPORTED_FORMATS:
        return reject("format_version is unsupported or invalid.")

    if not target_file:
        return reject("target_file is missing or invalid.")

    if not _is_sha256(candidate_sha256):
        return reject("candidate_sha256 is invalid.")

    if observed_target_sha256 != candidate_sha256:
        return reject(
            "observed_target_sha256 does not match candidate_sha256."
        )

    if record.get("status") != "APPLIED":
        return reject("lifecycle status is not APPLIED.")

    if record.get("semantic_decision") != "APPROVE_FOR_HUMAN_REVIEW":
        return reject(
            "semantic_decision is not APPROVE_FOR_HUMAN_REVIEW."
        )

    if format_version in {"FULL_FILE_V2", "NEW_FILE_V2"}:
        if record.get("compile_passed") is not True:
            return reject("compile_passed is not exactly True.")

        applied_sha256 = record.get("applied_sha256")
        if not _is_sha256(applied_sha256):
            return reject("applied_sha256 is invalid.")

        if applied_sha256 != candidate_sha256:
            return reject(
                "applied_sha256 does not match candidate_sha256."
            )

        post_apply = record.get("post_apply")
        if not isinstance(post_apply, Mapping):
            return reject("post_apply is missing or invalid.")

        if post_apply.get("validated") is not True:
            return reject(
                "post_apply validated is not exactly True."
            )

        post_apply_sha256 = post_apply.get("applied_sha256")
        if not _is_sha256(post_apply_sha256):
            return reject(
                "post_apply applied_sha256 is invalid."
            )

        if post_apply_sha256 != candidate_sha256:
            return reject(
                "post_apply applied_sha256 does not match candidate_sha256."
            )

    elif record.get("validation_passed") is not True:
        return reject("validation_passed is not exactly True.")

    return LifecycleRoadmapSyncDecision(
        patch_id=patch_id,
        format_version=format_version,
        target_file=target_file,
        status="VERIFIED_FOR_COMPLETION",
        verified=True,
        candidate_sha256=candidate_sha256,
        observed_target_sha256=observed_target_sha256,
        reason=(
            "Lifecycle status, semantic approval evidence, and target "
            "SHA256 integrity are verified."
        ),
    )