from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.workspace_registry import (
    resolve_workspace_python_target,
)


ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "pending_patches"

CONFIRM_PHRASE = "APPROVE WORLD OS FULL FILE PATCH"
LEGACY_WORKSPACE_NAME = "world-os-dev-agent"


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

    return queue_file, data


def approve_record(
    patch_id: str,
    confirmation: str,
) -> tuple[Path, dict]:
    queue_file, data = load_record(patch_id)

    format_version = data.get(
        "format_version"
    )

    if format_version not in {
        "FULL_FILE_V2",
        "NEW_FILE_V2",
    }:
        raise RuntimeError(
            "Patch format is not supported."
        )

    if data.get("status") != "READY_FOR_HUMAN_REVIEW":
        raise RuntimeError(
            "Patch is not READY_FOR_HUMAN_REVIEW."
        )

    if data.get("compile_passed") is not True:
        raise RuntimeError(
            "Candidate did not pass py_compile."
        )

    original_sha256 = data.get(
        "original_sha256"
    )

    if (
        format_version == "FULL_FILE_V2"
        and not original_sha256
    ):
        raise RuntimeError(
            "original_sha256 is missing."
        )

    if not data.get("candidate_sha256"):
        raise RuntimeError(
            "candidate_sha256 is missing."
        )

    if not data.get("candidate_file"):
        raise RuntimeError(
            "candidate_file is missing."
        )

    if not data.get("diff_file"):
        raise RuntimeError(
            "diff_file is missing."
        )

    if confirmation != CONFIRM_PHRASE:
        raise RuntimeError(
            "Human approval confirmation phrase mismatch."
        )

    workspace_name = data.get("workspace_name")

    if workspace_name is None:
        workspace_name = LEGACY_WORKSPACE_NAME
    elif not isinstance(workspace_name, str) or not workspace_name.strip():
        raise RuntimeError(
            "workspace_name is missing or empty."
        )

    target_file = data.get("target_file")

    if not isinstance(target_file, str) or not target_file.strip():
        raise RuntimeError(
            "target_file is missing or empty."
        )

    must_exist = (
        format_version == "FULL_FILE_V2"
    )

    target_path = resolve_workspace_python_target(
        workspace_name,
        target_file,
        must_exist=must_exist,
        allow_existing_test_script=(
            format_version == "FULL_FILE_V2"
        ),
    )

    canonical_workspace_name = workspace_name.strip()

    if format_version == "FULL_FILE_V2":
        current_sha256 = sha256_file(
            target_path
        )

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