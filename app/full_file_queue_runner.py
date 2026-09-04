from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.ai_full_file_reviewer import review_full_file_candidate
from app.full_file_validator import GOAL, prepare_candidate


ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "pending_patches"


@dataclass
class FullFilePatchRecord:
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
    status: str
    format_version: str


def read_semantic_decision(
    review: str,
) -> str:
    first_line = review.strip().splitlines()[0].strip()

    if first_line in {
        "REJECT",
        "REVISE",
        "APPROVE_FOR_HUMAN_REVIEW",
    }:
        return first_line

    return "UNKNOWN"


def status_for_decision(
    decision: str,
) -> str:
    if decision == "REJECT":
        return "REJECTED"

    if decision == "APPROVE_FOR_HUMAN_REVIEW":
        return "READY_FOR_HUMAN_REVIEW"

    return "DRAFT"


validation = prepare_candidate()

diff = validation.diff_file.read_text(
    encoding="utf-8",
)

semantic_review = review_full_file_candidate(
    goal=GOAL,
    target_file=validation.target_file,
    diff=diff,
)

semantic_decision = read_semantic_decision(
    semantic_review
)

status = status_for_decision(
    semantic_decision
)

record = FullFilePatchRecord(
    patch_id=str(uuid4()),
    created_at=datetime.now(timezone.utc).isoformat(),
    goal=GOAL,
    target_file=validation.target_file,
    original_sha256=validation.original_sha256,
    candidate_sha256=validation.candidate_sha256,
    candidate_file=str(validation.temp_file),
    diff_file=str(validation.diff_file),
    compile_passed=validation.compile_passed,
    semantic_decision=semantic_decision,
    semantic_review=semantic_review,
    status=status,
    format_version="FULL_FILE_V2",
)

QUEUE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

queue_file = (
    QUEUE_DIR
    / f"{record.patch_id}.json"
)

queue_file.write_text(
    json.dumps(
        asdict(record),
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)

print("=" * 70)
print("WORLD OS DEV AGENT - FULL FILE PATCH QUEUE V2")
print("=" * 70)
print()

print("PATCH ID:")
print(record.patch_id)
print()

print("FORMAT:")
print(record.format_version)
print()

print("TARGET FILE:")
print(record.target_file)
print()

print("ORIGINAL SHA256:")
print(record.original_sha256)
print()

print("CANDIDATE SHA256:")
print(record.candidate_sha256)
print()

print("PY_COMPILE:")
print(
    "PASS"
    if record.compile_passed
    else "FAIL"
)
print()

print("SEMANTIC DECISION:")
print(record.semantic_decision)
print()

print("SEMANTIC REVIEW:")
print(record.semantic_review)
print()

print("STATUS:")
print(record.status)
print()

print("QUEUE FILE:")
print(queue_file)
print()

print("ORIGINAL FILE MODIFIED:")
print("False")
