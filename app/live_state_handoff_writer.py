from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

from app.live_state import (
    current_milestone_version,
    parse_live_state,
)
from app.milestone_handoff import (
    MilestoneHandoffPlan,
    build_handoff_plan,
    milestone_version,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

LIVE_STATE_PATH = (
    PROJECT_ROOT
    / "context"
    / "LIVE_STATE.md"
)

ROADMAP_PATH = (
    PROJECT_ROOT
    / "context"
    / "ROADMAP.md"
)

EXPECTED_TARGET = "context/LIVE_STATE.md"


@dataclass(frozen=True)
class LiveStateHandoffCandidate:
    target_file: str
    original_sha256: str
    candidate_sha256: str
    current_milestone: str
    next_milestone: str
    candidate_content: str
    validated: bool
    reason: str


def _replace_section_value(
    text: str,
    heading: str,
    new_value: str,
) -> str:
    normalized = (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    pattern = re.compile(
        rf"^({re.escape(heading)}:[ \t]*$)\n"
        rf"(.*?)(?=\n[A-Za-z0-9][^\n]*:[ \t]*$|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )

    updated, count = pattern.subn(
        rf"\1\n{new_value}",
        normalized,
        count=1,
    )

    if count != 1:
        raise RuntimeError(
            f"Unable to replace LIVE_STATE section: {heading}"
        )

    return updated


def _ensure_status_block(
    text: str,
    version: str,
) -> str:
    normalized = (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    pattern = re.compile(
        rf"^{re.escape(version)} STATUS:[ \t]*$\n"
        rf"COMPLETE[ \t]*$",
        flags=re.MULTILINE,
    )

    if pattern.search(normalized):
        return normalized

    anchor = "Current milestone:\n"

    if normalized.count(anchor) != 1:
        raise RuntimeError(
            "Current milestone anchor is missing or ambiguous."
        )

    block = (
        f"{version} STATUS:\n"
        f"COMPLETE\n\n"
    )

    return normalized.replace(
        anchor,
        block + anchor,
        1,
    )


def build_live_state_handoff_candidate(
    expected_live_state_sha256: str,
    live_state_path: Path = LIVE_STATE_PATH,
    roadmap_path: Path = ROADMAP_PATH,
) -> LiveStateHandoffCandidate:
    live_bytes = live_state_path.read_bytes()

    actual_sha = sha256(
        live_bytes
    ).hexdigest()

    if (
        actual_sha.casefold()
        != expected_live_state_sha256.strip().casefold()
    ):
        raise RuntimeError(
            "LIVE_STATE SHA256 mismatch before candidate generation."
        )

    plan = build_handoff_plan(
        expected_live_state_sha256=expected_live_state_sha256,
        live_state_path=live_state_path,
        roadmap_path=roadmap_path,
    )

    if not plan.allowed:
        raise RuntimeError(
            f"Milestone handoff is not allowed: {plan.reason}"
        )

    if not plan.current_milestone:
        raise RuntimeError(
            "Current milestone is missing."
        )

    if not plan.next_milestone:
        raise RuntimeError(
            "Next milestone is missing."
        )

    if not plan.next_milestone_objective:
        raise RuntimeError(
            "Next milestone objective is missing."
        )

    current_version = milestone_version(
        plan.current_milestone
    )

    next_version = milestone_version(
        plan.next_milestone
    )

    if current_version is None:
        raise RuntimeError(
            "Current milestone version is missing."
        )

    if next_version is None:
        raise RuntimeError(
            "Next milestone version is missing."
        )

    original_text = live_bytes.decode(
        "utf-8-sig"
    )

    candidate = _ensure_status_block(
        original_text,
        current_version,
    )

    candidate = _replace_section_value(
        candidate,
        "Current milestone",
        plan.next_milestone,
    )

    candidate = _replace_section_value(
        candidate,
        "Current objective",
        plan.next_milestone_objective,
    )

    candidate = _replace_section_value(
        candidate,
        "Current objective status",
        "ACTIVE",
    )

    candidate = _replace_section_value(
        candidate,
        "Immediate next objective",
        "",
    )

    candidate = _replace_section_value(
        candidate,
        "Next milestone",
        "",
    )

    candidate = _replace_section_value(
        candidate,
        "Next milestone objective",
        "",
    )

    parsed = parse_live_state(
        candidate
    )

    if current_milestone_version(parsed) != next_version:
        raise RuntimeError(
            "Post-candidate current milestone validation failed."
        )

    if parsed.current_objective != plan.next_milestone_objective:
        raise RuntimeError(
            "Post-candidate current objective validation failed."
        )

    if parsed.current_objective_status != "ACTIVE":
        raise RuntimeError(
            "Post-candidate objective status validation failed."
        )

    if parsed.immediate_next_objective is not None:
        raise RuntimeError(
            "Immediate next objective must remain empty."
        )

    if parsed.next_milestone is not None:
        raise RuntimeError(
            "Next milestone must be empty after handoff."
        )

    if parsed.next_milestone_objective is not None:
        raise RuntimeError(
            "Next milestone objective must be empty after handoff."
        )

    if current_version not in parsed.completed_milestones:
        raise RuntimeError(
            "Previous milestone COMPLETE status was not preserved."
        )

    candidate_bytes = candidate.encode(
        "utf-8"
    )

    candidate_sha = sha256(
        candidate_bytes
    ).hexdigest()

    return LiveStateHandoffCandidate(
        target_file=EXPECTED_TARGET,
        original_sha256=actual_sha,
        candidate_sha256=candidate_sha,
        current_milestone=plan.current_milestone,
        next_milestone=plan.next_milestone,
        candidate_content=candidate,
        validated=True,
        reason=(
            "LIVE_STATE handoff candidate generated and validated "
            "without performing any write."
        ),
    )


if __name__ == "__main__":
    current_sha = sha256(
        LIVE_STATE_PATH.read_bytes()
    ).hexdigest()

    result = build_live_state_handoff_candidate(
        expected_live_state_sha256=current_sha,
    )

    print("LIVE_STATE HANDOFF WRITER CANDIDATE")
    print("=" * 72)
    print("Target:", result.target_file)
    print("Original SHA256:", result.original_sha256)
    print("Candidate SHA256:", result.candidate_sha256)
    print("Current milestone:", result.current_milestone)
    print("Next milestone:", result.next_milestone)
    print("Validated:", result.validated)
    print("Reason:", result.reason)
    print()
    print("LIVE_STATE WRITE PERFORMED: NO")
    print("DEV_TASK_STATE WRITE PERFORMED: NO")
    print("GIT WRITE PERFORMED: NO")
    print("RESEARCH/WEB WRITE PERFORMED: NO")
