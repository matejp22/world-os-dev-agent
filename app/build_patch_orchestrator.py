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


@dataclass
class _CandidateAttempt:
    result: BuildPatchResult
    candidate_text: str
    diff: str


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


def _build_candidate_attempt(
    *,
    clean_goal: str,
    canonical_workspace_name: str,
    target_file: str,
    target_path: Path,
    target_exists: bool,
    format_version: str,
    new_content: str,
    revision_round: int,
    lineage: list[str],
    previous_patch_id: str | None,
) -> _CandidateAttempt:
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
        semantic_review = compile_output
        decision = "COMPILE_FAILED"
        status = (
            "REVISION_LIMIT_REACHED"
            if revision_round >= MAX_REVISIONS
            else "DRAFT"
        )

    else:
        print(
            f"BUILD PATCH: revision round {revision_round} "
            "- semantic review...",
            flush=True,
        )

        semantic_review = review_full_file_candidate(
            goal=clean_goal,
            target_file=target_file,
            diff=diff,
        )

        decision = semantic_decision(
            semantic_review
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
        compile_passed=compile_passed,
        semantic_decision=decision,
        semantic_review=semantic_review,
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

    return _CandidateAttempt(
        result=result,
        candidate_text=candidate_text,
        diff=diff,
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
        attempt = _build_candidate_attempt(
            clean_goal=clean_goal,
            canonical_workspace_name=canonical_workspace_name,
            target_file=target_file,
            target_path=target_path,
            target_exists=target_exists,
            format_version=format_version,
            new_content=new_content,
            revision_round=revision_round,
            lineage=lineage,
            previous_patch_id=previous_patch_id,
        )

        result = attempt.result

        if result.semantic_decision == "COMPILE_FAILED":
            if revision_round >= MAX_REVISIONS:
                return result

            print(
                "BUILD PATCH: py_compile failed; "
                "requesting compile repair...",
                flush=True,
            )

            revised = revise_candidate(
                goal=clean_goal,
                target_file=target_file,
                current_content=attempt.candidate_text,
                diff=attempt.diff,
                semantic_review=(
                    "PY_COMPILE FAILURE:\n"
                    + result.semantic_review
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
                result.patch_id
            )

            previous_patch_id = result.patch_id

            continue

        if result.semantic_decision in {
            "APPROVE_FOR_HUMAN_REVIEW",
            "REJECT",
        }:
            return result

        if result.semantic_decision != "REVISE":
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
            current_content=attempt.candidate_text,
            diff=attempt.diff,
            semantic_review=result.semantic_review,
        )

        new_content = _parse_revised_content(
            revised,
            target_file,
        )

        lineage.append(
            result.patch_id
        )

        previous_patch_id = result.patch_id

    raise RuntimeError(
        "Autonomous revision loop exited unexpectedly."
    )


if __name__ == "__main__":
    raise SystemExit(
        "This module is a reusable service. "
        "Use run_build_patch(goal) from an approved orchestration path."
    )


def run_manual_revision(
    patch_id: str,
    revision_instruction: str,
) -> BuildPatchResult:
    clean_patch_id = patch_id.strip()
    clean_instruction = revision_instruction.strip()

    if not clean_patch_id:
        raise RuntimeError("patch_id is empty.")

    if not clean_instruction:
        raise RuntimeError("revision_instruction is empty.")

    queue_file = (
        QUEUE_DIR
        / f"{clean_patch_id}.json"
    )

    if not queue_file.exists():
        raise RuntimeError(
            "Patch record does not exist: "
            + clean_patch_id
        )

    try:
        source_record = json.loads(
            queue_file.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise RuntimeError(
            "Unable to load canonical patch record."
        ) from exc

    if not isinstance(source_record, dict):
        raise RuntimeError(
            "Canonical patch record must be an object."
        )

    if source_record.get("patch_id") != clean_patch_id:
        raise RuntimeError(
            "Canonical patch ID does not match the requested patch."
        )

    if (
        source_record.get("status")
        != "READY_FOR_HUMAN_REVIEW"
    ):
        raise RuntimeError(
            "Manual revision requires "
            "READY_FOR_HUMAN_REVIEW status."
        )

    target_file = source_record.get(
        "target_file"
    )

    if (
        not isinstance(target_file, str)
        or not target_file.strip()
    ):
        raise RuntimeError(
            "Patch record has no valid target_file."
        )

    target_file = target_file.strip()

    format_version = source_record.get(
        "format_version"
    )

    if format_version not in {
        "FULL_FILE_V2",
        "NEW_FILE_V2",
    }:
        raise RuntimeError(
            "Unsupported patch format for manual revision."
        )

    workspace_name = source_record.get(
        "workspace_name"
    )

    if (
        not isinstance(workspace_name, str)
        or not workspace_name.strip()
    ):
        raise RuntimeError(
            "Patch record has no valid workspace_name."
        )

    workspace = get_workspace_profile(
        workspace_name.strip()
    )

    canonical_workspace_name = workspace.name

    candidate_file_value = source_record.get(
        "candidate_file"
    )
    diff_file_value = source_record.get(
        "diff_file"
    )

    if (
        not isinstance(candidate_file_value, str)
        or not candidate_file_value.strip()
    ):
        raise RuntimeError(
            "Patch record has no valid candidate_file."
        )

    if (
        not isinstance(diff_file_value, str)
        or not diff_file_value.strip()
    ):
        raise RuntimeError(
            "Patch record has no valid diff_file."
        )

    candidate_file = Path(
        candidate_file_value
    )
    diff_file = Path(
        diff_file_value
    )

    if (
        not candidate_file.exists()
        or not candidate_file.is_file()
    ):
        raise RuntimeError(
            "Candidate artifact is missing."
        )

    if (
        not diff_file.exists()
        or not diff_file.is_file()
    ):
        raise RuntimeError(
            "Diff artifact is missing."
        )

    revision_round = source_record.get(
        "revision_round"
    )

    if (
        type(revision_round) is not int
        or revision_round < 0
    ):
        raise RuntimeError(
            "Patch record has invalid revision_round."
        )

    next_revision_round = (
        revision_round + 1
    )

    if next_revision_round > MAX_REVISIONS:
        raise RuntimeError(
            "Manual revision would exceed MAX_REVISIONS."
        )

    prior_lineage = source_record.get(
        "superseded_patch_ids",
        [],
    )

    if not isinstance(prior_lineage, list):
        raise RuntimeError(
            "Patch lineage is malformed."
        )

    if any(
        not isinstance(item, str)
        or not item.strip()
        for item in prior_lineage
    ):
        raise RuntimeError(
            "Patch lineage contains invalid patch IDs."
        )

    lineage = list(
        dict.fromkeys(
            [
                *prior_lineage,
                clean_patch_id,
            ]
        )
    )

    current_content = (
        candidate_file.read_text(
            encoding="utf-8-sig"
        )
    )

    current_diff = (
        diff_file.read_text(
            encoding="utf-8"
        )
    )

    original_review = source_record.get(
        "semantic_review",
        "",
    )

    if not isinstance(
        original_review,
        str,
    ):
        original_review = ""

    revised = revise_candidate(
        goal=clean_instruction,
        target_file=target_file,
        current_content=current_content,
        diff=current_diff,
        semantic_review=(
            original_review
            + "\n\n"
            + "HUMAN REVISION INSTRUCTION:\n"
            + clean_instruction
        ),
    )

    new_content = _parse_revised_content(
        revised,
        target_file,
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

    target_exists = (
        format_version == "FULL_FILE_V2"
    )

    target_path = resolve_workspace_python_target(
        canonical_workspace_name,
        target_file,
        must_exist=target_exists,
        allow_existing_test_script=(
            is_existing_test_script
        ),
    )

    attempt = _build_candidate_attempt(
        clean_goal=clean_instruction,
        canonical_workspace_name=(
            canonical_workspace_name
        ),
        target_file=target_file,
        target_path=target_path,
        target_exists=target_exists,
        format_version=format_version,
        new_content=new_content,
        revision_round=next_revision_round,
        lineage=lineage,
        previous_patch_id=clean_patch_id,
    )

    return attempt.result
