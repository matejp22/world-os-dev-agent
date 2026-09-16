from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.patch_quality_evidence import evaluate_patch_record_quality
from app.patch_quality_evidence_runner import (
    PatchQualityExecutionResult,
    run_patch_quality_evidence,
)
from app.workspace_registry import (
    require_verified_patch_workspace,
    resolve_workspace_python_target,
)


ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "pending_patches"

CONFIRM_PHRASE = "APPROVE WORLD OS FULL FILE PATCH"
LEGACY_WORKSPACE_NAME = "world-os-dev-agent"


def persist_patch_quality_evidence(
    *,
    patch_id: str,
    result: PatchQualityExecutionResult,
) -> tuple[Path, dict]:
    from app.patch_quality_evidence_persistence import (
        persist_patch_quality_evidence as canonical_persist_patch_quality_evidence,
    )

    return canonical_persist_patch_quality_evidence(
        patch_id=patch_id,
        result=result,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def load_record(
    patch_id: str,
) -> tuple[Path, dict]:
    queue_file = QUEUE_DIR / f"{patch_id}.json"

    if not queue_file.exists():
        raise RuntimeError(
            f"Patch not found: {patch_id}"
        )

    data = json.loads(
        queue_file.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(data, dict):
        raise RuntimeError(
            "Patch record must be an object."
        )

    return queue_file, data


def _derive_artifact_integrity(
    data: dict,
) -> bool:
    candidate_sha256 = data.get("candidate_sha256")
    candidate_file = data.get("candidate_file")
    diff_file = data.get("diff_file")

    if (
        not isinstance(candidate_sha256, str)
        or not candidate_sha256.strip()
        or not isinstance(candidate_file, str)
        or not candidate_file.strip()
        or not isinstance(diff_file, str)
        or not diff_file.strip()
    ):
        return False

    try:
        candidate_path = Path(candidate_file)
        diff_path = Path(diff_file)

        if not candidate_path.is_file():
            return False

        if not diff_path.is_file():
            return False

        return sha256_file(candidate_path) == candidate_sha256
    except (OSError, ValueError):
        return False


def _quality_passed(
    data: dict,
    *,
    format_supported: bool,
    lifecycle_ready: bool,
    compile_passed: bool,
    semantic_approved: bool,
    workspace_policy_passed: bool,
    target_scope_passed: bool,
    artifact_integrity_passed: bool,
) -> None:
    try:
        result = evaluate_patch_record_quality(
            data,
            format_supported=format_supported,
            lifecycle_ready=lifecycle_ready,
            compile_passed=compile_passed,
            semantic_approved=semantic_approved,
            workspace_policy_passed=workspace_policy_passed,
            target_scope_passed=target_scope_passed,
            artifact_integrity_passed=artifact_integrity_passed,
        )
    except RuntimeError as exc:
        raise RuntimeError(
            "Patch quality evaluation failed."
        ) from exc

    if not isinstance(result, tuple) or len(result) != 2:
        raise RuntimeError(
            "Patch quality evaluation returned a malformed result."
        )

    _, quality_result = result

    verdict = getattr(
        quality_result,
        "verdict",
        None,
    )
    safe_for_human_approval = getattr(
        quality_result,
        "safe_for_human_approval",
        None,
    )

    if (
        verdict != "PASS"
        or safe_for_human_approval is not True
    ):
        raise RuntimeError(
            "Patch quality gate did not pass."
        )


def approve_record(
    patch_id: str,
    confirmation: str,
) -> tuple[Path, dict]:
    queue_file, data = load_record(patch_id)

    format_version = data.get("format_version")
    status = data.get("status")
    compile_passed = data.get("compile_passed") is True

    format_supported = format_version in {
        "FULL_FILE_V2",
        "NEW_FILE_V2",
    }
    lifecycle_ready = status == "READY_FOR_HUMAN_REVIEW"

    semantic_review = data.get("semantic_review")
    legacy_semantic_approved = (
        isinstance(semantic_review, dict)
        and semantic_review.get("decision") == "APPROVE"
        and semantic_review.get(
            "safe_for_human_approval"
        ) is True
    )

    semantic_decision = data.get("semantic_decision")
    canonical_semantic_approved = (
        semantic_decision == "APPROVE_FOR_HUMAN_REVIEW"
        and isinstance(semantic_review, str)
        and bool(semantic_review.strip())
        and semantic_review.strip().splitlines()[0].strip()
        == "APPROVE_FOR_HUMAN_REVIEW"
    )

    semantic_approved = (
        legacy_semantic_approved
        or canonical_semantic_approved
    )

    original_sha256 = data.get("original_sha256")
    candidate_sha256 = data.get("candidate_sha256")
    candidate_file = data.get("candidate_file")
    diff_file = data.get("diff_file")

    if data.get("workspace_name") is None:
        workspace_name = LEGACY_WORKSPACE_NAME
    else:
        workspace_name = data.get("workspace_name")

    target_file = data.get("target_file")

    basic_original_valid = (
        format_version != "FULL_FILE_V2"
        or (
            isinstance(original_sha256, str)
            and bool(original_sha256.strip())
        )
    )
    basic_candidate_valid = (
        isinstance(candidate_sha256, str)
        and bool(candidate_sha256.strip())
    )
    basic_candidate_file_valid = (
        isinstance(candidate_file, str)
        and bool(candidate_file.strip())
    )
    basic_diff_file_valid = (
        isinstance(diff_file, str)
        and bool(diff_file.strip())
    )
    workspace_metadata_valid = (
        isinstance(workspace_name, str)
        and bool(workspace_name.strip())
    )
    target_metadata_valid = (
        isinstance(target_file, str)
        and bool(target_file.strip())
    )
    confirmation_valid = confirmation == CONFIRM_PHRASE

    if not confirmation_valid:
        raise RuntimeError(
            "Human approval confirmation phrase mismatch."
        )

    if not lifecycle_ready:
        raise RuntimeError(
            "Patch is not READY_FOR_HUMAN_REVIEW."
        )

    if not format_supported:
        raise RuntimeError(
            "Patch format is not supported."
        )

    if not compile_passed:
        raise RuntimeError(
            "Candidate did not pass py_compile."
        )

    if not semantic_approved:
        raise RuntimeError(
            "Semantic review did not approve the patch."
        )

    if not workspace_metadata_valid:
        raise RuntimeError(
            "workspace_name is missing or empty."
        )

    if not target_metadata_valid:
        raise RuntimeError(
            "target_file is missing or empty."
        )

    if data.get("quality_evidence") is None:
        preflight_workspace_name = workspace_name
        preflight_target_file = target_file

        if (
            not isinstance(preflight_workspace_name, str)
            or not preflight_workspace_name.strip()
        ):
            raise RuntimeError(
                "workspace_name is missing or empty."
            )

        if (
            not isinstance(preflight_target_file, str)
            or not preflight_target_file.strip()
        ):
            raise RuntimeError(
                "target_file is missing or empty."
            )

        result = run_patch_quality_evidence(
            workspace_name=preflight_workspace_name,
            target_file=preflight_target_file,
        )

        persist_patch_quality_evidence(
            patch_id=patch_id,
            result=result,
        )

        queue_file, data = load_record(patch_id)

        canonical_workspace_name = data.get("workspace_name")
        canonical_target_file = data.get("target_file")

        if canonical_workspace_name is None:
            canonical_workspace_name = LEGACY_WORKSPACE_NAME

        if canonical_workspace_name != preflight_workspace_name:
            raise RuntimeError(
                "Persisted quality evidence workspace identity mismatch."
            )

        if canonical_target_file != preflight_target_file:
            raise RuntimeError(
                "Persisted quality evidence target identity mismatch."
            )

        format_version = data.get("format_version")
        status = data.get("status")
        compile_passed = data.get("compile_passed") is True

        format_supported = format_version in {
            "FULL_FILE_V2",
            "NEW_FILE_V2",
        }
        lifecycle_ready = status == "READY_FOR_HUMAN_REVIEW"

        semantic_review = data.get("semantic_review")
        legacy_semantic_approved = (
            isinstance(semantic_review, dict)
            and semantic_review.get("decision") == "APPROVE"
            and semantic_review.get(
                "safe_for_human_approval"
            ) is True
        )

        semantic_decision = data.get("semantic_decision")
        canonical_semantic_approved = (
            semantic_decision == "APPROVE_FOR_HUMAN_REVIEW"
            and isinstance(semantic_review, str)
            and bool(semantic_review.strip())
            and semantic_review.strip().splitlines()[0].strip()
            == "APPROVE_FOR_HUMAN_REVIEW"
        )

        semantic_approved = (
            legacy_semantic_approved
            or canonical_semantic_approved
        )

        original_sha256 = data.get("original_sha256")
        candidate_sha256 = data.get("candidate_sha256")
        candidate_file = data.get("candidate_file")
        diff_file = data.get("diff_file")

        workspace_name = data.get("workspace_name")
        if workspace_name is None:
            workspace_name = LEGACY_WORKSPACE_NAME

        target_file = data.get("target_file")

        basic_original_valid = (
            format_version != "FULL_FILE_V2"
            or (
                isinstance(original_sha256, str)
                and bool(original_sha256.strip())
            )
        )
        basic_candidate_valid = (
            isinstance(candidate_sha256, str)
            and bool(candidate_sha256.strip())
        )
        basic_candidate_file_valid = (
            isinstance(candidate_file, str)
            and bool(candidate_file.strip())
        )
        basic_diff_file_valid = (
            isinstance(diff_file, str)
            and bool(diff_file.strip())
        )
        workspace_metadata_valid = (
            isinstance(workspace_name, str)
            and bool(workspace_name.strip())
        )
        target_metadata_valid = (
            isinstance(target_file, str)
            and bool(target_file.strip())
        )

    workspace_policy_passed = False
    if workspace_metadata_valid:
        try:
            require_verified_patch_workspace(
                workspace_name.strip()
            )
            workspace_policy_passed = True
        except RuntimeError:
            workspace_policy_passed = False

    target_scope_passed = False
    if workspace_metadata_valid and target_metadata_valid:
        try:
            resolve_workspace_python_target(
                workspace_name.strip(),
                target_file.strip(),
                must_exist=False,
                allow_existing_test_script=(
                    format_version == "FULL_FILE_V2"
                ),
            )
            target_scope_passed = True
        except RuntimeError:
            target_scope_passed = False

    artifact_integrity_passed = _derive_artifact_integrity(data)

    _quality_passed(
        data,
        format_supported=format_supported,
        lifecycle_ready=lifecycle_ready,
        compile_passed=compile_passed,
        semantic_approved=semantic_approved,
        workspace_policy_passed=workspace_policy_passed,
        target_scope_passed=target_scope_passed,
        artifact_integrity_passed=artifact_integrity_passed,
    )

    if not format_supported:
        raise RuntimeError(
            "Patch format is not supported."
        )

    if not lifecycle_ready:
        raise RuntimeError(
            "Patch is not READY_FOR_HUMAN_REVIEW."
        )

    if not compile_passed:
        raise RuntimeError(
            "Candidate did not pass py_compile."
        )

    if not semantic_approved:
        raise RuntimeError(
            "Semantic review did not approve the patch."
        )

    if not basic_original_valid:
        raise RuntimeError(
            "original_sha256 is missing."
        )

    if not basic_candidate_valid:
        raise RuntimeError(
            "candidate_sha256 is missing."
        )

    if not basic_candidate_file_valid:
        raise RuntimeError(
            "candidate_file is missing."
        )

    if not basic_diff_file_valid:
        raise RuntimeError(
            "diff_file is missing."
        )

    if not confirmation_valid:
        raise RuntimeError(
            "Human approval confirmation phrase mismatch."
        )

    if not workspace_metadata_valid:
        raise RuntimeError(
            "workspace_name is missing or empty."
        )

    if not target_metadata_valid:
        raise RuntimeError(
            "target_file is missing or empty."
        )

    canonical_workspace_name = workspace_name.strip()
    canonical_target_file = target_file.strip()

    require_verified_patch_workspace(
        canonical_workspace_name
    )

    target_path = resolve_workspace_python_target(
        canonical_workspace_name,
        canonical_target_file,
        must_exist=(format_version == "FULL_FILE_V2"),
        allow_existing_test_script=(
            format_version == "FULL_FILE_V2"
        ),
    )

    if format_version == "FULL_FILE_V2":
        current_sha256 = sha256_file(target_path)

        if current_sha256 != original_sha256:
            raise RuntimeError(
                "Target source changed after candidate preparation. "
                "Approval refused."
            )
    else:
        if target_path.exists():
            raise RuntimeError(
                "NEW_FILE_V2 target already exists. "
                "Approval refused."
            )

    candidate_path = Path(candidate_file)
    diff_path = Path(diff_file)

    if not candidate_path.is_file():
        raise RuntimeError(
            "Candidate artifact is missing or is not a regular file."
        )

    if not diff_path.is_file():
        raise RuntimeError(
            "Diff artifact is missing or is not a regular file."
        )

    if sha256_file(candidate_path) != candidate_sha256:
        raise RuntimeError(
            "Candidate artifact SHA256 does not match."
        )

    data["workspace_name"] = canonical_workspace_name
    data["status"] = "APPROVED"

    queue_file.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return queue_file, data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WORLD OS DEV AGENT FULL_FILE_V2 approval"
    )

    parser.add_argument(
        "--patch-id",
        required=True,
    )

    parser.add_argument(
        "--confirm",
        required=True,
    )

    args = parser.parse_args()

    queue_file, data = approve_record(
        patch_id=args.patch_id,
        confirmation=args.confirm,
    )

    print("=" * 70)
    print("WORLD OS DEV AGENT - FULL FILE HUMAN APPROVAL")
    print("=" * 70)
    print()

    print("PATCH ID:")
    print(data["patch_id"])
    print()

    print("FORMAT:")
    print(data["format_version"])
    print()

    print("WORKSPACE:")
    print(data["workspace_name"])
    print()

    print("TARGET FILE:")
    print(data["target_file"])
    print()

    print("ORIGINAL SHA256:")
    print(data["original_sha256"])
    print()

    print("CANDIDATE SHA256:")
    print(data["candidate_sha256"])
    print()

    print("STATUS:")
    print(data["status"])
    print()

    print("PATCH APPROVED.")
    print("SOURCE FILE NOT MODIFIED.")


if __name__ == "__main__":
    main()