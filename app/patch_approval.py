from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = PROJECT_ROOT / "pending_patches"

CONFIRM_PHRASE = "APPROVE WORLD OS DEV PATCH"


def load_patch(patch_id: str) -> tuple[Path, dict]:
    path = QUEUE_DIR / f"{patch_id}.json"

    if not path.exists():
        raise RuntimeError(
            f"Patch not found: {patch_id}"
        )

    data = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    return path, data


def approve_patch(
    patch_id: str,
    confirmation: str,
) -> tuple[Path, dict]:
    path, data = load_patch(
        patch_id
    )

    if data.get("status") != "READY_FOR_HUMAN_REVIEW":
        raise RuntimeError(
            "Patch is not READY_FOR_HUMAN_REVIEW."
        )

    if confirmation != CONFIRM_PHRASE:
        raise RuntimeError(
            "Human approval confirmation phrase mismatch."
        )

    data["status"] = "APPROVED"

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return path, data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WORLD OS DEV AGENT patch approval gate"
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

    path, data = approve_patch(
        patch_id=args.patch_id,
        confirmation=args.confirm,
    )

    print("=" * 70)
    print("WORLD OS DEV AGENT - HUMAN APPROVAL")
    print("=" * 70)
    print()
    print("PATCH ID:")
    print(data["patch_id"])
    print()
    print("TARGET FILE:")
    print(data["target_file"])
    print()
    print("STATUS:")
    print(data["status"])
    print()
    print("QUEUE FILE:")
    print(path)
    print()
    print("PATCH APPROVED.")
    print("PATCH NOT APPLIED.")


if __name__ == "__main__":
    main()
