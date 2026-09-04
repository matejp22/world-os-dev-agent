from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.ai_patch_repair import repair_patch
from app.ai_patch_reviewer import review_patch
from app.patch_validator import validate_patch_proposal


PATCH_ID = "238904e9-52bd-4bd3-8495-7f1bbdf2b5a3"

ROOT = Path(__file__).resolve().parent.parent
QUEUE_FILE = ROOT / "pending_patches" / f"{PATCH_ID}.json"
TEMP_DIR = ROOT / "temp"


def extract_diff(proposal: str) -> str:
    marker = "PROPOSED_PATCH:"

    if marker not in proposal:
        raise RuntimeError("PROPOSED_PATCH missing.")

    diff = proposal.split(marker, 1)[1].strip()

    if not diff:
        raise RuntimeError("Diff is empty.")

    return diff


data = json.loads(
    QUEUE_FILE.read_text(encoding="utf-8")
)

error_text = (
    "git apply --check failed: "
    "error: corrupt patch at line 23"
)

repaired = repair_patch(
    proposal=data["proposal"],
    error_text=error_text,
)

print("=" * 70)
print("REPAIRED PATCH")
print("=" * 70)
print(repaired)
print()

validation = validate_patch_proposal(
    repaired
)

print("=" * 70)
print("STRUCTURAL VALIDATION")
print("=" * 70)
print("VALID:")
print(validation.valid)
print()
print("REASON:")
print(validation.reason)
print()

if not validation.valid:
    raise SystemExit(0)

semantic = review_patch(
    goal=data["goal"],
    proposal=repaired,
)

print("=" * 70)
print("SEMANTIC REVIEW")
print("=" * 70)
print(semantic)
print()

diff = extract_diff(
    repaired
)

TEMP_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

patch_file = (
    TEMP_DIR
    / f"{PATCH_ID}.repaired.patch"
)

patch_file.write_text(
    diff + "\n",
    encoding="utf-8",
)

check = subprocess.run(
    [
        "git",
        "apply",
        "--check",
        str(patch_file),
    ],
    cwd=ROOT,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)

print("=" * 70)
print("GIT APPLY CHECK")
print("=" * 70)
print("EXIT CODE:")
print(check.returncode)
print()
print("STDOUT:")
print(check.stdout.strip() or "<empty>")
print()
print("STDERR:")
print(check.stderr.strip() or "<empty>")
print()
print("NO PATCH WAS APPLIED.")
