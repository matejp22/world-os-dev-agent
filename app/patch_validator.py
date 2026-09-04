from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = (PROJECT_ROOT / "app").resolve()


@dataclass
class PatchValidation:
    valid: bool
    reason: str
    target_file: str | None = None
    normalized_diff: str | None = None


FORBIDDEN_PATCH_TOKENS = (
    "git push",
    "git commit",
    "git add",
    "remove-item",
    "supabase db push",
    "drop table",
    "delete from",
    "insert into",
    "update ",
    "alter table",
    ".env",
    "supabase/.temp",
)


def extract_target_file(proposal: str) -> str | None:
    match = re.search(
        r"(?m)^TARGET_FILE:\s*(.+?)\s*$",
        proposal,
    )

    if not match:
        return None

    return match.group(1).strip()


def extract_diff(proposal: str) -> str | None:
    marker = "PROPOSED_PATCH:"

    if marker not in proposal:
        return None

    diff = proposal.split(marker, 1)[1].strip()

    return diff or None


def validate_patch_proposal(proposal: str) -> PatchValidation:
    target_file = extract_target_file(proposal)

    if not target_file:
        return PatchValidation(
            valid=False,
            reason="TARGET_FILE is missing.",
        )

    normalized_target = target_file.replace("\\", "/")

    if not normalized_target.startswith("app/"):
        return PatchValidation(
            valid=False,
            reason="Patch target must be inside app/.",
            target_file=normalized_target,
        )

    if not normalized_target.endswith(".py"):
        return PatchValidation(
            valid=False,
            reason="Patch target must be a Python source file.",
            target_file=normalized_target,
        )

    candidate = (PROJECT_ROOT / normalized_target).resolve()

    try:
        candidate.relative_to(APP_ROOT)
    except ValueError:
        return PatchValidation(
            valid=False,
            reason="Patch target escapes allowed app directory.",
            target_file=normalized_target,
        )

    if not candidate.exists():
        return PatchValidation(
            valid=False,
            reason="Patch target does not exist.",
            target_file=normalized_target,
        )

    diff = extract_diff(proposal)

    if not diff:
        return PatchValidation(
            valid=False,
            reason="PROPOSED_PATCH is missing.",
            target_file=normalized_target,
        )

    lowered = diff.lower()

    for token in FORBIDDEN_PATCH_TOKENS:
        if token in lowered:
            return PatchValidation(
                valid=False,
                reason=f"Forbidden patch token detected: {token}",
                target_file=normalized_target,
            )

    expected_old = f"--- a/{normalized_target}"
    expected_new = f"+++ b/{normalized_target}"

    if expected_old not in diff or expected_new not in diff:
        return PatchValidation(
            valid=False,
            reason="Unified diff does not match TARGET_FILE.",
            target_file=normalized_target,
        )

    return PatchValidation(
        valid=True,
        reason="Patch passed deterministic V0.1 structural validation.",
        target_file=normalized_target,
        normalized_diff=diff,
    )
