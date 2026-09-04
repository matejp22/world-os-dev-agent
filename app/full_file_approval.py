from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "pending_patches"

CONFIRM_PHRASE = "APPROVE WORLD OS FULL FILE PATCH"


def load_record(
    patch_id: str,
) -> tuple[Path, dict]:
    queue_file = (
        QUEUE_DIR
        / f"{patch_id}.json"
    )

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
    queue_file, data = load_record(
        patch_id
    )

    if data.get("format_version") != "FULL_FILE_V2":
        raise RuntimeError(
            "Patch is not FULL_FILE_V2."
        )

    if data.get("status") != "READY_FOR_HUMAN_REVIEW":
        raise RuntimeError(
            "Patch is not READY_FOR_HUMAN_REVIEW."
        )

    if data.get("compile_passed") is not True:
        raise RuntimeError(
            "Candidate did not pass py_compile."
        )

    if not data.get("original_sha256"):
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
