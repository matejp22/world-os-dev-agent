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


def validate_new_target(
    target_file: str,
) -> Path:
    normalized = target_file.replace(
        "\\",
        "/",
    )

    if not normalized.startswith("app/"):
        raise RuntimeError(
            "NEW_FILE_V2 target must be inside app/."
        )

    if not normalized.endswith(".py"):
        raise RuntimeError(
            "NEW_FILE_V2 target must be a Python file."
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
            "NEW_FILE_V2 target escapes app directory."
        ) from exc

    if target.exists():
        raise RuntimeError(
            "NEW_FILE_V2 target already exists. "
            "Apply refused."
        )

    if not target.parent.exists():
        raise RuntimeError(
            "NEW_FILE_V2 target parent directory does not exist."
        )

    if not target.parent.is_dir():
        raise RuntimeError(
            "NEW_FILE_V2 target parent is not a directory."
        )

    return target


def rollback_owned_new_target(
    target: Path,
    stage_file: Path,
    recorded_candidate_sha: str,
) -> bool:
    if not target.exists():
        return True

    if not stage_file.exists():
        return False

    try:
        same_file = os.path.samefile(
            stage_file,
            target,
        )
    except OSError:
        return False

    if not same_file:
        return False

    try:
        current_sha = sha256_bytes(
            target.read_bytes()
        )
    except OSError:
        return False

    if current_sha != recorded_candidate_sha:
        return False

    try:
        target.unlink()
    except OSError:
        return False

    return not target.exists()


def cleanup_owned_stage_after_success(
    stage_file: Path,
    target: Path,
    recorded_candidate_sha: str,
) -> bool:
    if not stage_file.exists():
        return True

    if not target.exists():
        return False

    try:
        same_file = os.path.samefile(
            stage_file,
            target,
        )
    except OSError:
        return False

    if not same_file:
        return False

    try:
        target_sha = sha256_bytes(
            target.read_bytes()
        )
    except OSError:
        return False

    if target_sha != recorded_candidate_sha:
        return False

    try:
        stage_file.unlink()
    except OSError:
        return False

    return not stage_file.exists()


def apply_new_file_v2(
    queue_file: Path,
    data: dict,
    patch_id: str,
) -> None:
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

    target = validate_new_target(
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

    if not candidate_file.is_file():
        raise RuntimeError(
            "Candidate path is not a regular file."
        )

    recorded_candidate_sha = data.get(
        "candidate_sha256"
    )

    if not recorded_candidate_sha:
        raise RuntimeError(
            "candidate_sha256 is missing."
        )

    candidate_bytes = candidate_file.read_bytes()

    candidate_sha = sha256_bytes(
        candidate_bytes
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

    if target.exists():
        raise RuntimeError(
            "NEW_FILE_V2 target appeared before apply. "
            "Apply refused."
        )

    stage_file = target.with_name(
        f".{target.name}.{patch_id}.new.stage"
    )

    if stage_file.exists():
        raise RuntimeError(
            "NEW_FILE_V2 stage file already exists."
        )

    target_created = False
    commit_point_reached = False

    try:
        with stage_file.open("xb") as handle:
            handle.write(candidate_bytes)
            handle.flush()
            os.fsync(handle.fileno())

        data["status"] = "APPLYING"
        data["apply_started_at"] = (
            datetime.now(timezone.utc).isoformat()
        )
        data["new_file_stage"] = str(
            stage_file
        )

        atomic_write_json(
            queue_file,
            data,
        )

        os.link(
            stage_file,
            target,
        )

        target_created = True

        applied_sha = sha256_bytes(
            target.read_bytes()
        )

        if applied_sha != recorded_candidate_sha:
            raise RuntimeError(
                "Applied NEW_FILE_V2 SHA256 does not match "
                "candidate SHA256."
            )

        target_compile = run_py_compile(
            target
        )

        if target_compile.returncode != 0:
            raise RuntimeError(
                "Applied NEW_FILE_V2 source failed py_compile:\n"
                + (
                    target_compile.stderr
                    or target_compile.stdout
                )
            )

        data["status"] = "CREATED_VERIFIED"
        data["created_verified_at"] = (
            datetime.now(timezone.utc).isoformat()
        )
        data["applied_sha256"] = applied_sha
        data["created_new_file"] = True

        atomic_write_json(
            queue_file,
            data,
        )

        success_cleanup_ok = (
            cleanup_owned_stage_after_success(
                stage_file=stage_file,
                target=target,
                recorded_candidate_sha=recorded_candidate_sha,
            )
        )

        if not success_cleanup_ok:
            raise RuntimeError(
                "NEW_FILE_V2 success cleanup could not prove "
                "stage ownership or remove the stage file."
            )

        commit_point_reached = True

        data["status"] = "APPLIED"
        data["applied_at"] = (
            datetime.now(timezone.utc).isoformat()
        )

        atomic_write_json(
            queue_file,
            data,
        )

    except Exception as exc:
        if commit_point_reached:
            data["status"] = "CREATED_VERIFIED"
            data["final_metadata_persistence_failed"] = True
            data["apply_error"] = str(exc)

            try:
                atomic_write_json(
                    queue_file,
                    data,
                )
            except Exception:
                pass

            raise RuntimeError(
                "NEW_FILE_V2 target is created and verified, "
                "but final APPLIED metadata persistence failed. "
                "Target was intentionally retained; persisted "
                "queue state should remain CREATED_VERIFIED."
            ) from exc

        rollback_ok = True

        if target_created:
            rollback_ok = rollback_owned_new_target(
                target=target,
                stage_file=stage_file,
                recorded_candidate_sha=recorded_candidate_sha,
            )

        stage_cleanup_ok = True

        if stage_file.exists():
            try:
                stage_file.unlink()
            except OSError:
                stage_cleanup_ok = False

        if stage_file.exists():
            stage_cleanup_ok = False

        if not stage_cleanup_ok:
            rollback_ok = False

        if target.exists():
            rollback_ok = False

        data["status"] = (
            "ROLLED_BACK"
            if rollback_ok
            else "ROLLBACK_FAILED"
        )

        data["apply_error"] = str(
            exc
        )

        data["rollback_target_absent"] = (
            not target.exists()
        )

        data["rollback_stage_absent"] = (
            not stage_file.exists()
        )

        try:
            atomic_write_json(
                queue_file,
                data,
            )
        except Exception:
            pass

        raise

    print("=" * 70)
    print("WORLD OS DEV AGENT - NEW_FILE_V2 APPLY")
    print("=" * 70)
    print()
    print("PATCH ID:")
    print(data["patch_id"])
    print()
    print("TARGET FILE:")
    print(data["target_file"])
    print()
    print("TARGET ABSENT BEFORE APPLY:")
    print("PASS")
    print()
    print("CANDIDATE SHA256 VERIFIED:")
    print("PASS")
    print()
    print("CANDIDATE PY_COMPILE:")
    print("PASS")
    print()
    print("ATOMIC CREATE WITHOUT OVERWRITE:")
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

    if data.get("format_version") == "NEW_FILE_V2":
        apply_new_file_v2(
            queue_file=queue_file,
            data=data,
            patch_id=args.patch_id,
        )
        return

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

    if not candidate_file.is_file():
        raise RuntimeError(
            "Candidate path is not a regular file."
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
