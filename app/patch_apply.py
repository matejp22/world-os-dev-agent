from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = PROJECT_ROOT / "pending_patches"
BACKUP_DIR = PROJECT_ROOT / "backups"
TEMP_DIR = PROJECT_ROOT / "temp"


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


def extract_diff(proposal: str) -> str:
    marker = "PROPOSED_PATCH:"

    if marker not in proposal:
        raise RuntimeError(
            "Patch proposal does not contain PROPOSED_PATCH."
        )

    diff = proposal.split(marker, 1)[1].strip()

    if diff.startswith("```diff"):
        diff = diff[len("```diff"):].lstrip()

    if diff.endswith("```"):
        diff = diff[:-3].rstrip()

    if not diff:
        raise RuntimeError(
            "Patch diff is empty."
        )

    return diff


def validate_target(target_file: str) -> Path:
    normalized = target_file.replace("\\", "/")

    if not normalized.startswith("app/"):
        raise RuntimeError(
            "Patch target must be inside app/."
        )

    if not normalized.endswith(".py"):
        raise RuntimeError(
            "Patch target must be a Python file."
        )

    target = (PROJECT_ROOT / normalized).resolve()
    app_root = (PROJECT_ROOT / "app").resolve()

    try:
        target.relative_to(app_root)
    except ValueError as exc:
        raise RuntimeError(
            "Patch target escapes app directory."
        ) from exc

    if not target.exists():
        raise RuntimeError(
            f"Target file does not exist: {target}"
        )

    return target


def run_command(
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WORLD OS DEV AGENT safe patch apply"
    )

    parser.add_argument(
        "--patch-id",
        required=True,
    )

    args = parser.parse_args()

    queue_path, data = load_patch(
        args.patch_id
    )

    if data.get("status") != "APPROVED":
        raise RuntimeError(
            "Patch status must be APPROVED before apply."
        )

    target_file = data.get("target_file")

    if not target_file:
        raise RuntimeError(
            "Patch has no target_file."
        )

    target = validate_target(
        target_file
    )

    proposal = data.get("proposal") or ""
    diff = extract_diff(
        proposal
    )

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    backup_path = (
        BACKUP_DIR
        / f"{target.name}.{timestamp}.bak"
    )

    shutil.copy2(
        target,
        backup_path,
    )

    patch_file = (
        TEMP_DIR
        / f"{args.patch_id}.patch"
    )

    patch_file.write_text(
        diff + "\n",
        encoding="utf-8",
    )

    check_result = run_command(
        [
            "git",
            "apply",
            "--check",
            str(patch_file),
        ]
    )

    if check_result.returncode != 0:
        raise RuntimeError(
            "git apply --check failed:\n"
            + (
                check_result.stderr
                or check_result.stdout
            )
        )

    apply_result = run_command(
        [
            "git",
            "apply",
            str(patch_file),
        ]
    )

    if apply_result.returncode != 0:
        raise RuntimeError(
            "git apply failed:\n"
            + (
                apply_result.stderr
                or apply_result.stdout
            )
        )

    compile_result = run_command(
        [
            "python",
            "-m",
            "py_compile",
            str(target),
        ]
    )

    if compile_result.returncode != 0:
        shutil.copy2(
            backup_path,
            target,
        )

        raise RuntimeError(
            "py_compile failed. "
            "Target restored from backup.\n"
            + (
                compile_result.stderr
                or compile_result.stdout
            )
        )

    data["status"] = "APPLIED"
    data["applied_at"] = datetime.now().isoformat()
    data["backup_path"] = str(
        backup_path
    )

    queue_path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("=" * 70)
    print("WORLD OS DEV AGENT - PATCH APPLY")
    print("=" * 70)
    print()
    print("PATCH ID:")
    print(data["patch_id"])
    print()
    print("TARGET FILE:")
    print(data["target_file"])
    print()
    print("BACKUP:")
    print(backup_path)
    print()
    print("GIT APPLY CHECK:")
    print("PASS")
    print()
    print("PATCH APPLY:")
    print("PASS")
    print()
    print("PY_COMPILE:")
    print("PASS")
    print()
    print("STATUS:")
    print(data["status"])


if __name__ == "__main__":
    main()
