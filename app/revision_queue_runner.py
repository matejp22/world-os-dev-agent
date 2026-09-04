from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.ai_file_candidate import generate_candidate
from app.ai_full_file_revision import revise_candidate
from app.ai_full_file_reviewer import review_full_file_candidate
from app.deterministic_diff import build_unified_diff
from app.full_file_validator import (
    GOAL,
    ROOT,
    APP_ROOT,
    TEMP_DIR,
    extract_section,
    parse_candidate,
    sha256_bytes,
    detect_newline,
)


QUEUE_DIR = ROOT / "pending_patches"
MAX_REVISIONS = 2


@dataclass
class RevisionQueueRecord:
    patch_id: str
    created_at: str
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


def normalize_candidate_bytes(
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

    clean_new_content = new_content.lstrip(
        "\ufeff"
    )

    clean_new_content = (
        clean_new_content
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    clean_new_content = clean_new_content.replace(
        "\n",
        newline,
    )

    candidate_bytes = clean_new_content.encode(
        "utf-8"
    )

    if has_bom:
        candidate_bytes = (
            b"\xef\xbb\xbf"
            + candidate_bytes
        )

    return original_bytes, candidate_bytes


def compile_candidate(
    candidate_file: Path,
) -> bool:
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

    return result.returncode == 0


def parse_decision(
    review: str,
) -> str:
    if not review.strip():
        return "UNKNOWN"

    return review.strip().splitlines()[0].strip()


candidate = generate_candidate(
    GOAL
)

target_file, new_content = parse_candidate(
    candidate
)

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


final_record = None


for revision_number in range(
    0,
    MAX_REVISIONS + 1,
):
    original_bytes, candidate_bytes = normalize_candidate_bytes(
        target_path=target_path,
        new_content=new_content,
    )

    original_sha256 = sha256_bytes(
        original_bytes
    )

    candidate_sha256 = sha256_bytes(
        candidate_bytes
    )

    TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    candidate_file = (
        TEMP_DIR
        / f"queued_revision_candidate_{revision_number}.py"
    )

    candidate_file.write_bytes(
        candidate_bytes
    )

    compile_passed = compile_candidate(
        candidate_file
    )

    if not compile_passed:
        final_record = RevisionQueueRecord(
            patch_id=str(uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            goal=GOAL,
            target_file=target_file,
            original_sha256=original_sha256,
            candidate_sha256=candidate_sha256,
            candidate_file=str(candidate_file),
            diff_file="",
            compile_passed=False,
            semantic_decision="REJECT",
            semantic_review="Candidate failed py_compile.",
            revision_round=revision_number,
            status="REJECTED",
            format_version="FULL_FILE_V2",
        )
        break

    old_text = original_bytes.decode(
        "utf-8-sig"
    )

    new_text = candidate_bytes.decode(
        "utf-8-sig"
    )

    diff = build_unified_diff(
        target_file=target_file,
        old_content=old_text,
        new_content=new_text,
    )

    diff_file = (
        TEMP_DIR
        / f"queued_revision_candidate_{revision_number}.diff"
    )

    diff_file.write_text(
        diff,
        encoding="utf-8",
    )

    review = review_full_file_candidate(
        goal=GOAL,
        target_file=target_file,
        diff=diff,
    )

    decision = parse_decision(
        review
    )

    if decision == "APPROVE_FOR_HUMAN_REVIEW":
        final_record = RevisionQueueRecord(
            patch_id=str(uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            goal=GOAL,
            target_file=target_file,
            original_sha256=original_sha256,
            candidate_sha256=candidate_sha256,
            candidate_file=str(candidate_file),
            diff_file=str(diff_file),
            compile_passed=True,
            semantic_decision=decision,
            semantic_review=review,
            revision_round=revision_number,
            status="READY_FOR_HUMAN_REVIEW",
            format_version="FULL_FILE_V2",
        )
        break

    if decision == "REJECT":
        final_record = RevisionQueueRecord(
            patch_id=str(uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            goal=GOAL,
            target_file=target_file,
            original_sha256=original_sha256,
            candidate_sha256=candidate_sha256,
            candidate_file=str(candidate_file),
            diff_file=str(diff_file),
            compile_passed=True,
            semantic_decision=decision,
            semantic_review=review,
            revision_round=revision_number,
            status="REJECTED",
            format_version="FULL_FILE_V2",
        )
        break

    if decision != "REVISE":
        final_record = RevisionQueueRecord(
            patch_id=str(uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            goal=GOAL,
            target_file=target_file,
            original_sha256=original_sha256,
            candidate_sha256=candidate_sha256,
            candidate_file=str(candidate_file),
            diff_file=str(diff_file),
            compile_passed=True,
            semantic_decision=decision,
            semantic_review=review,
            revision_round=revision_number,
            status="REJECTED",
            format_version="FULL_FILE_V2",
        )
        break

    if revision_number >= MAX_REVISIONS:
        final_record = RevisionQueueRecord(
            patch_id=str(uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            goal=GOAL,
            target_file=target_file,
            original_sha256=original_sha256,
            candidate_sha256=candidate_sha256,
            candidate_file=str(candidate_file),
            diff_file=str(diff_file),
            compile_passed=True,
            semantic_decision=decision,
            semantic_review=review,
            revision_round=revision_number,
            status="DRAFT",
            format_version="FULL_FILE_V2",
        )
        break

    current_content = target_path.read_text(
        encoding="utf-8-sig",
    )

    revised = revise_candidate(
        goal=GOAL,
        target_file=target_file,
        current_content=current_content,
        diff=diff,
        semantic_review=review,
    )

    revised_target = extract_section(
        revised,
        "TARGET_FILE:",
        "RATIONALE:",
    ).replace("\\", "/")

    revised_content = extract_section(
        revised,
        "NEW_FILE_CONTENT:",
    )

    if revised_target != target_file:
        raise RuntimeError(
            "Revision changed the target file."
        )

    new_content = revised_content


if final_record is None:
    raise RuntimeError(
        "Revision pipeline produced no final record."
    )


QUEUE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

queue_file = (
    QUEUE_DIR
    / f"{final_record.patch_id}.json"
)

queue_file.write_text(
    json.dumps(
        asdict(final_record),
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print("=" * 70)
print("WORLD OS DEV AGENT - REVISION QUEUE V2")
print("=" * 70)
print()

print("PATCH ID:")
print(final_record.patch_id)
print()

print("FORMAT:")
print(final_record.format_version)
print()

print("TARGET FILE:")
print(final_record.target_file)
print()

print("REVISION ROUND:")
print(final_record.revision_round)
print()

print("PY_COMPILE:")
print(
    "PASS"
    if final_record.compile_passed
    else "FAIL"
)
print()

print("SEMANTIC DECISION:")
print(final_record.semantic_decision)
print()

print("STATUS:")
print(final_record.status)
print()

print("CANDIDATE FILE:")
print(final_record.candidate_file)
print()

print("DIFF FILE:")
print(final_record.diff_file or "<none>")
print()

print("QUEUE FILE:")
print(queue_file)
print()

print("ORIGINAL SOURCE FILE MODIFIED:")
print("False")
