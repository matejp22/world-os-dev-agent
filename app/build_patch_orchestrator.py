from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
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
from app.workspace_registry import (
    get_workspace_profile,
    resolve_workspace_python_target,
)


ROOT = Path(__file__).resolve().parent.parent
TEMP_DIR = ROOT / "temp"
QUEUE_DIR = ROOT / "pending_patches"

MAX_REVISIONS = 2


@dataclass
class BuildPatchResult:
    patch_id: str
    goal: str
    workspace_name: str
    target_file: str
    original_sha256: str | None
    candidate_sha256: str
    candidate_file: str
    diff_file: str
    compile_passed: bool
    semantic_decision: str
    semantic_review: str
    revision_round: int
    status: str
    format_version: str
    superseded_patch_ids: list[str] = field(default_factory=list)
    supersedes_patch_id: str | None = None


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

    if original_bytes.endswith(b"\n"):
        clean_content = clean_content.rstrip("\n") + "\n"
    else:
        clean_content = clean_content.rstrip("\n")

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


def normalize_new_candidate(
    new_content: str,
) -> bytes:
    clean_content = new_content.lstrip(
        "\ufeff"
    )

    clean_content = (
        clean_content
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    return clean_content.encode(
        "utf-8"
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


def _write_queue_record(
    result: BuildPatchResult,
) -> Path:
    QUEUE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    queue_file = (
        QUEUE_DIR
        / f"{result.patch_id}.json"
    )

    if queue_file.exists():
        raise RuntimeError(
            "Refusing to overwrite historical patch record: "
            + result.patch_id
        )

    payload = asdict(
        result
    )

    payload["created_at"] = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    queue_file.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return queue_file


def _parse_revised_content(
    revised: str,
    target_file: str,
) -> str:
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

    return extract_section(
        revised,
        "NEW_FILE_CONTENT:",
    )


def run_build_patch(
    goal: str,
    workspace_name: str = "world-os-dev-agent",
) -> BuildPatchResult:
    clean_goal = goal.strip()

    if not clean_goal:
        raise RuntimeError(
            "Build goal is empty."
        )

    workspace = get_workspace_profile(
        workspace_name
    )

    canonical_workspace_name = workspace.name

    print(
        "BUILD PATCH: generating candidate...",
        flush=True,
    )

    raw_candidate = generate_candidate(
        clean_goal,
        canonical_workspace_name,
    )

    print(
        "BUILD PATCH: candidate generated.",
        flush=True,
    )

    target_file, new_content = parse_candidate(
        raw_candidate
    )

    print(
        f"BUILD PATCH: target = {target_file}",
        flush=True,
    )

    target_parts = tuple(
        part
        for part in target_file.split("/")
        if part
    )

    is_existing_test_script = (
        len(target_parts) == 2
        and target_parts[0] == "scripts"
        and target_parts[1].startswith("test_")
        and target_parts[1].endswith(".py")
    )

    target_path = resolve_workspace_python_target(
        canonical_workspace_name,
        target_file,
        must_exist=is_existing_test_script,
        allow_existing_test_script=is_existing_test_script,
    )

    target_exists = target_path.exists()

    format_version = (
        "FULL_FILE_V2"
        if target_exists
        else "NEW_FILE_V2"
    )

    TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    QUEUE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    previous_patch_id: str | None = None
    lineage: list[str] = []

    for revision_round in range(
        0,
        MAX_REVISIONS + 1,
    ):
        patch_id = str(
            uuid4()
        )

        if target_exists:
            (
                original_bytes,
                candidate_bytes,
            ) = normalize_candidate(
                target_path=target_path,
                new_content=new_content,
            )

            original_sha: str | None = sha256_bytes(
                original_bytes
            )

            candidate_sha = sha256_bytes(
                candidate_bytes
            )

            if candidate_sha == original_sha:
                raise RuntimeError(
                    "Candidate contains no changes."
                )

        else:
            original_bytes = b""
            original_sha = None

            candidate_bytes = normalize_new_candidate(
                new_content
            )

            candidate_sha = sha256_bytes(
                candidate_bytes
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
                result = BuildPatchResult(
                    patch_id=patch_id,
                    goal=clean_goal,
                    workspace_name=canonical_workspace_name,
                    target_file=target_file,
                    original_sha256=original_sha,
                    candidate_sha256=candidate_sha,
                    candidate_file=str(
                        candidate_file
                    ),
                    diff_file=str(
                        diff_file
                    ),
                    compile_passed=False,
                    semantic_decision="COMPILE_FAILED",
                    semantic_review=compile_output,
                    revision_round=revision_round,
                    status="REVISION_LIMIT_REACHED",
                    format_version=format_version,
                    superseded_patch_ids=list(
                        lineage
                    ),
                    supersedes_patch_id=previous_patch_id,
                )

                _write_queue_record(
                    result
                )

                return result

            result = BuildPatchResult(
                patch_id=patch_id,
                goal=clean_goal,
                workspace_name=canonical_workspace_name,
                target_file=target_file,
                original_sha256=original_sha,
                candidate_sha256=candidate_sha,
                candidate_file=str(
                    candidate_file
                ),
                diff_file=str(
                    diff_file
                ),
                compile_passed=False,
                semantic_decision="COMPILE_FAILED",
                semantic_review=compile_output,
                revision_round=revision_round,
                status="DRAFT",
                format_version=format_version,
                superseded_patch_ids=list(
                    lineage
                ),
                supersedes_patch_id=previous_patch_id,
            )

            _write_queue_record(
                result
            )

            print(
                "BUILD PATCH: py_compile failed; "
                "requesting compile repair...",
                flush=True,
            )

            revised = revise_candidate(
                goal=clean_goal,
                target_file=target_file,
                current_content=candidate_text,
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

            new_content = _parse_revised_content(
                revised,
                target_file,
            )

            lineage.append(
                patch_id
            )

            previous_patch_id = patch_id

            continue

        print(
            f"BUILD PATCH: revision round {revision_round} "
            "- semantic review...",
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

        if decision == "APPROVE_FOR_HUMAN_REVIEW":
            status = "READY_FOR_HUMAN_REVIEW"

        elif decision == "REJECT":
            status = "REJECTED"

        elif decision == "REVISE":
            status = (
                "REVISION_LIMIT_REACHED"
                if revision_round >= MAX_REVISIONS
                else "DRAFT"
            )

        else:
            status = "DRAFT"

        result = BuildPatchResult(
            patch_id=patch_id,
            goal=clean_goal,
            workspace_name=canonical_workspace_name,
            target_file=target_file,
            original_sha256=original_sha,
            candidate_sha256=candidate_sha,
            candidate_file=str(
                candidate_file
            ),
            diff_file=str(
                diff_file
            ),
            compile_passed=True,
            semantic_decision=decision,
            semantic_review=review,
            revision_round=revision_round,
            status=status,
            format_version=format_version,
            superseded_patch_ids=list(
                lineage
            ),
            supersedes_patch_id=previous_patch_id,
        )

        _write_queue_record(
            result
        )

        if decision in {
            "APPROVE_FOR_HUMAN_REVIEW",
            "REJECT",
        }:
            return result

        if decision != "REVISE":
            return result

        if revision_round >= MAX_REVISIONS:
            return result

        print(
            f"BUILD PATCH: requesting revision {revision_round + 1}...",
            flush=True,
        )

        revised = revise_candidate(
            goal=clean_goal,
            target_file=target_file,
            current_content=candidate_text,
            diff=diff,
            semantic_review=review,
        )

        new_content = _parse_revised_content(
            revised,
            target_file,
        )

        lineage.append(
            patch_id
        )

        previous_patch_id = patch_id

    raise RuntimeError(
        "Autonomous revision loop exited unexpectedly."
    )


if __name__ == "__main__":
    raise SystemExit(
        "This module is a reusable service. "
        "Use run_build_patch(goal) from an approved orchestration path."
    )