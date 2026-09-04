from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

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
from app.ai_file_candidate import generate_candidate


MAX_REVISIONS = 2


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
        / f"revision_candidate_{revision_number}.py"
    )

    candidate_file.write_bytes(
        candidate_bytes
    )

    compile_passed = compile_candidate(
        candidate_file
    )

    print("=" * 70)
    print(f"REVISION ROUND {revision_number}")
    print("=" * 70)
    print()

    print("TARGET FILE:")
    print(target_file)
    print()

    print("ORIGINAL SHA256:")
    print(original_sha256)
    print()

    print("CANDIDATE SHA256:")
    print(candidate_sha256)
    print()

    print("PY_COMPILE:")
    print(
        "PASS"
        if compile_passed
        else "FAIL"
    )
    print()

    if not compile_passed:
        print("FINAL STATUS:")
        print("REJECTED")
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

    review = review_full_file_candidate(
        goal=GOAL,
        target_file=target_file,
        diff=diff,
    )

    decision = parse_decision(
        review
    )

    print("SEMANTIC DECISION:")
    print(decision)
    print()

    print("SEMANTIC REVIEW:")
    print(review)
    print()

    if decision == "APPROVE_FOR_HUMAN_REVIEW":
        print("FINAL STATUS:")
        print("READY_FOR_HUMAN_REVIEW")
        break

    if decision == "REJECT":
        print("FINAL STATUS:")
        print("REJECTED")
        break

    if decision != "REVISE":
        print("FINAL STATUS:")
        print("REJECTED_UNKNOWN_DECISION")
        break

    if revision_number >= MAX_REVISIONS:
        print("FINAL STATUS:")
        print("MAX_REVISIONS_REACHED")
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


print()
print("=" * 70)
print("ORIGINAL SOURCE FILE MODIFIED:")
print("False")
