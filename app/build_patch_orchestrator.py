from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.ai_file_candidate import generate_candidate
from app.ai_full_file_reviewer import review_full_file_candidate
from app.ai_full_file_revision import revise_candidate
from app.deterministic_diff import build_unified_diff
from app.full_file_validator import (
    detect_newline,
    extract_section,
    parse_candidate,
    sha256_bytes,
)


ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = (ROOT / "app").resolve()
TEMP_DIR = ROOT / "temp"
QUEUE_DIR = ROOT / "pending_patches"

MAX_REVISIONS = 2


@dataclass
class BuildPatchResult:
    patch_id: str
    goal: str
    target_file: str
    original_sha256: str
    candidate_sha256: str
    candidate_file: str
    diff_file: str
    compile_passed: bool
    semantic_decision: str
    semantic_review: str
    revision_round: int
    status: str
    format_version: str


def semantic_decision(review: str) -> str:
    if not review.strip():
        return "UNKNOWN"

    first_line = review.strip().splitlines()[0].strip()

    if first_line in {
        "REJECT",
        "REVISE",
        "APPROVE_FOR_HUMAN_REVIEW",
    }:
        return first_line

    return "UNKNOWN"


def status_for_decision(decision: str) -> str:
    if decision == "APPROVE_FOR_HUMAN_REVIEW":
        return "READY_FOR_HUMAN_REVIEW"

    if decision == "REJECT":
        return "REJECTED"

    return "DRAFT"


def resolve_target(target_file: str) -> Path:
    target_path = (
        ROOT / target_file
    ).resolve()

    try:
        target_path.relative_to(
            APP_ROOT
        )
    except ValueError as exc:
        raise RuntimeError(
            "Target escapes app directory."
        ) from exc

    if not target_path.exists():
        raise RuntimeError(
            "Target file does not exist."
        )

    if not target_path.is_file():
        raise RuntimeError(
            "Target path is not a regular file."
        )

    if target_path.suffix.lower() != ".py":
        raise RuntimeError(
            "Only existing Python files under app/ are supported."
        )

    return target_path


def normalize_candidate(
    target_path: Path,
    new_content: str,
) -> tuple[bytes, bytes]:
    original_bytes = target_path.read_bytes()

    has_bom = original_bytes.startswith(
        b"\xef\xbb\xbf"
    )

    newline = detect_newline(
        original_bytes
    )

    clean_content = new_content.lstrip(
        "\ufeff"
    )

    clean_content = (
        clean_content
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    clean_content = clean_content.replace(
        "\n",
        newline,
    )

    candidate_bytes = clean_content.encode(
        "utf-8"
    )

    if has_bom:
        candidate_bytes = (
            b"\xef\xbb\xbf"
            + candidate_bytes
        )

    return (
        original_bytes,
        candidate_bytes,
    )


def compile_candidate(
    candidate_file: Path,
) -> tuple[bool, str]:
    result = subprocess.run(
        [
            "python",
            "-m",
            "py_compile",
            str(candidate_file),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    output = (
        result.stderr
        or result.stdout
        or ""
    ).strip()

    return (
        result.returncode == 0,
        output,
    )


def run_build_patch(
    goal: str,
) -> BuildPatchResult:
    clean_goal = goal.strip()

    if not clean_goal:
        raise RuntimeError(
            "Build goal is empty."
        )

    print("BUILD PATCH: generating candidate...", flush=True)

    raw_candidate = generate_candidate(
        clean_goal
    )

    print("BUILD PATCH: candidate generated.", flush=True)

    print("BUILD PATCH: parsing candidate...", flush=True)

    target_file, new_content = parse_candidate(
        raw_candidate
    )

    print(
        f"BUILD PATCH: target = {target_file}",
        flush=True,
    )

    target_path = resolve_target(
        target_file
    )

    patch_id = str(
        uuid4()
    )

    TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    QUEUE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_review = ""
    final_decision = "UNKNOWN"
    final_original_sha = ""
    final_candidate_sha = ""
    final_candidate_file: Path | None = None
    final_diff_file: Path | None = None
    final_compile_passed = False
    final_revision_round = 0

    for revision_round in range(
        0,
        MAX_REVISIONS + 1,
    ):
        (
            original_bytes,
            candidate_bytes,
        ) = normalize_candidate(
            target_path=target_path,
            new_content=new_content,
        )

        original_sha = sha256_bytes(
            original_bytes
        )

        candidate_sha = sha256_bytes(
            candidate_bytes
        )

        if candidate_sha == original_sha:
            raise RuntimeError(
                "Candidate contains no changes."
            )

        candidate_file = (
            TEMP_DIR
            / f"{patch_id}.candidate.py"
        )

        candidate_file.write_bytes(
            candidate_bytes
        )

        old_text = original_bytes.decode(
            "utf-8-sig"
        )

        candidate_text = candidate_bytes.decode(
            "utf-8-sig"
        )

        diff = build_unified_diff(
            target_file=target_file,
            old_content=old_text,
            new_content=candidate_text,
        )

        diff_file = (
            TEMP_DIR
            / f"{patch_id}.diff"
        )

        diff_file.write_text(
            diff,
            encoding="utf-8",
        )

        print(
            f"BUILD PATCH: revision round {revision_round} - py_compile...",
            flush=True,
        )

        compile_passed, compile_output = compile_candidate(
            candidate_file
        )

        if not compile_passed:
            if revision_round >= MAX_REVISIONS:
                raise RuntimeError(
                    "Candidate py_compile failed:\n"
                    + compile_output
                )

            current_content = target_path.read_text(
                encoding="utf-8-sig",
            )

            print(
                "BUILD PATCH: py_compile failed; requesting compile repair...",
                flush=True,
            )

            revised = revise_candidate(
                goal=clean_goal,
                target_file=target_file,
                current_content=current_content,
                diff=diff,
                semantic_review=(
                    "PY_COMPILE FAILURE:\n"
                    + compile_output
                    + "\n\n"
                    "Correct only the compile/syntax problem while "
                    "preserving the requested change. Do not alter the "
                    "target file."
                ),
            )

            revised_target = extract_section(
                revised,
                "TARGET_FILE:",
                "RATIONALE:",
            ).replace(
                "\\",
                "/",
            )

            if revised_target != target_file:
                raise RuntimeError(
                    "Revision attempted to change target file."
                )

            new_content = extract_section(
                revised,
                "NEW_FILE_CONTENT:",
            )

            continue

        print(
            f"BUILD PATCH: revision round {revision_round} - semantic review...",
            flush=True,
        )

        review = review_full_file_candidate(
            goal=clean_goal,
            target_file=target_file,
            diff=diff,
        )

        decision = semantic_decision(
            review
        )

        print(
            f"BUILD PATCH: semantic decision = {decision}",
            flush=True,
        )

        final_review = review
        final_decision = decision
        final_original_sha = original_sha
        final_candidate_sha = candidate_sha
        final_candidate_file = candidate_file
        final_diff_file = diff_file
        final_compile_passed = compile_passed
        final_revision_round = revision_round

        if decision == "APPROVE_FOR_HUMAN_REVIEW":
            break

        if decision == "REJECT":
            break

        if decision != "REVISE":
            break

        if revision_round >= MAX_REVISIONS:
            break

        current_content = target_path.read_text(
            encoding="utf-8-sig",
        )

        print(
            f"BUILD PATCH: requesting revision {revision_round + 1}...",
            flush=True,
        )

        revised = revise_candidate(
            goal=clean_goal,
            target_file=target_file,
            current_content=current_content,
            diff=diff,
            semantic_review=review,
        )

        revised_target = extract_section(
            revised,
            "TARGET_FILE:",
            "RATIONALE:",
        ).replace(
            "\\",
            "/",
        )

        if revised_target != target_file:
            raise RuntimeError(
                "Revision attempted to change target file."
            )

        new_content = extract_section(
            revised,
            "NEW_FILE_CONTENT:",
        )

    if final_candidate_file is None:
        raise RuntimeError(
            "No candidate file was produced."
        )

    if final_diff_file is None:
        raise RuntimeError(
            "No diff file was produced."
        )

    status = status_for_decision(
        final_decision
    )

    result = BuildPatchResult(
        patch_id=patch_id,
        goal=clean_goal,
        target_file=target_file,
        original_sha256=final_original_sha,
        candidate_sha256=final_candidate_sha,
        candidate_file=str(
            final_candidate_file
        ),
        diff_file=str(
            final_diff_file
        ),
        compile_passed=final_compile_passed,
        semantic_decision=final_decision,
        semantic_review=final_review,
        revision_round=final_revision_round,
        status=status,
        format_version="FULL_FILE_V2",
    )

    queue_file = (
        QUEUE_DIR
        / f"{patch_id}.json"
    )

    queue_payload = asdict(
        result
    )

    queue_payload["created_at"] = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    queue_file.write_text(
        json.dumps(
            queue_payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        f"BUILD PATCH: queue record created = {queue_file}",
        flush=True,
    )

    print(
        f"BUILD PATCH: final status = {result.status}",
        flush=True,
    )

    return result


if __name__ == "__main__":
    raise SystemExit(
        "This module is a reusable service. "
        "Use run_build_patch(goal) from an approved orchestration path."
    )