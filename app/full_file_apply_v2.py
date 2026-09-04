from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = (ROOT / "app").resolve()
QUEUE_DIR = ROOT / "pending_patches"
BACKUP_DIR = ROOT / "backups"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write_json(
    path: Path,
    data: dict,
) -> None:
    temp_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    temp_path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    os.replace(
        temp_path,
        path,
    )


def run_py_compile(
    path: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python",
            "-m",
            "py_compile",
            str(path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


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


def validate_target(
    target_file: str,
) -> Path:
    normalized = target_file.replace(
        "\\",
        "/",
    )

    if not normalized.startswith("app/"):
        raise RuntimeError(
            "Target must be inside app/."
        )

    if not normalized.endswith(".py"):
        raise RuntimeError(
            "Target must be a Python file."
        )

    target = (
        ROOT / normalized
    ).resolve()

    try:
        target.relative_to(
            APP_ROOT
        )
    except ValueError as exc:
        raise RuntimeError(
            "Target escapes app directory."
        ) from exc

    if not target.exists():
        raise RuntimeError(
            "Target file does not exist."
        )

    return target


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WORLD OS DEV AGENT FULL_FILE_V2 atomic apply"
    )

    parser.add_argument(
        "--patch-id",
        required=True,
    )

    args = parser.parse_args()

    queue_file, data = load_record(
        args.patch_id
    )

    if data.get("format_version") != "FULL_FILE_V2":
        raise RuntimeError(
            "Patch is not FULL_FILE_V2."
        )

    if data.get("status") != "APPROVED":
        raise RuntimeError(
            "Patch status must be APPROVED."
        )

    target_file = data.get(
        "target_file"
    )

    if not target_file:
        raise RuntimeError(
            "target_file is missing."
        )

    target = validate_target(
        target_file
    )

    candidate_file_value = data.get(
        "candidate_file"
    )

    if not candidate_file_value:
        raise RuntimeError(
            "candidate_file is missing."
        )

    candidate_file = Path(
        candidate_file_value
    ).resolve()

    if not candidate_file.exists():
        raise RuntimeError(
            "Candidate file does not exist."
        )

    recorded_original_sha = data.get(
        "original_sha256"
    )

    recorded_candidate_sha = data.get(
        "candidate_sha256"
    )

    if not recorded_original_sha:
        raise RuntimeError(
            "original_sha256 is missing."
        )

    if not recorded_candidate_sha:
        raise RuntimeError(
            "candidate_sha256 is missing."
        )

    current_bytes = target.read_bytes()
    candidate_bytes = candidate_file.read_bytes()

    current_sha = sha256_bytes(
        current_bytes
    )

    candidate_sha = sha256_bytes(
        candidate_bytes
    )

    if current_sha != recorded_original_sha:
        raise RuntimeError(
            "SOURCE SHA256 MISMATCH. "
            "The source file changed after candidate generation. "
            "Apply refused."
        )

    if candidate_sha != recorded_candidate_sha:
        raise RuntimeError(
            "CANDIDATE SHA256 MISMATCH. "
            "Candidate integrity check failed."
        )

    candidate_compile = run_py_compile(
        candidate_file
    )

    if candidate_compile.returncode != 0:
        raise RuntimeError(
            "Candidate py_compile failed before apply:\n"
            + (
                candidate_compile.stderr
                or candidate_compile.stdout
            )
        )

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    backup_file = (
        BACKUP_DIR
        / f"{target.name}.{args.patch_id}.{timestamp}.bak"
    )

    shutil.copy2(
        target,
        backup_file,
    )

    stage_file = target.with_name(
        f".{target.name}.{args.patch_id}.stage"
    )

    stage_file.write_bytes(
        candidate_bytes
    )

    data["status"] = "APPLYING"
    data["apply_started_at"] = (
        datetime.now(timezone.utc).isoformat()
    )
    data["backup_file"] = str(
        backup_file
    )

    atomic_write_json(
        queue_file,
        data,
    )

    source_replaced = False

    try:
        os.replace(
            stage_file,
            target,
        )

        source_replaced = True

        applied_sha = sha256_bytes(
            target.read_bytes()
        )

        if applied_sha != recorded_candidate_sha:
            raise RuntimeError(
                "Applied source SHA256 does not match candidate SHA256."
            )

        target_compile = run_py_compile(
            target
        )

        if target_compile.returncode != 0:
            raise RuntimeError(
                "Applied source failed py_compile:\n"
                + (
                    target_compile.stderr
                    or target_compile.stdout
                )
            )

        data["status"] = "APPLIED"
        data["applied_at"] = (
            datetime.now(timezone.utc).isoformat()
        )
        data["applied_sha256"] = applied_sha

        try:
            atomic_write_json(
                queue_file,
                data,
            )
        except Exception:
            shutil.copy2(
                backup_file,
                target,
            )

            source_replaced = False

            raise RuntimeError(
                "Queue metadata persistence failed after apply. "
                "Source restored from backup."
            )

    except Exception as exc:
        if source_replaced:
            shutil.copy2(
                backup_file,
                target,
            )

        if stage_file.exists():
            stage_file.unlink()

        rollback_sha = sha256_bytes(
            target.read_bytes()
        )

        rollback_ok = (
            rollback_sha
            == recorded_original_sha
        )

        data["status"] = (
            "ROLLED_BACK"
            if rollback_ok
            else "ROLLBACK_FAILED"
        )

        data["apply_error"] = str(
            exc
        )

        data["rollback_sha256"] = (
            rollback_sha
        )

        try:
            atomic_write_json(
                queue_file,
                data,
            )
        except Exception:
            pass

        raise

    if stage_file.exists():
        stage_file.unlink()

    print("=" * 70)
    print("WORLD OS DEV AGENT - FULL_FILE_V2 APPLY")
    print("=" * 70)
    print()

    print("PATCH ID:")
    print(data["patch_id"])
    print()

    print("TARGET FILE:")
    print(data["target_file"])
    print()

    print("ORIGINAL SHA256 VERIFIED:")
    print("PASS")
    print()

    print("CANDIDATE SHA256 VERIFIED:")
    print("PASS")
    print()

    print("CANDIDATE PY_COMPILE:")
    print("PASS")
    print()

    print("BACKUP:")
    print(backup_file)
    print()

    print("ATOMIC REPLACE:")
    print("PASS")
    print()

    print("TARGET PY_COMPILE:")
    print("PASS")
    print()

    print("FINAL STATUS:")
    print(data["status"])
    print()

    print("WORLD-OS-RESEARCH-ENGINE MODIFIED:")
    print("False")


if __name__ == "__main__":
    main()
