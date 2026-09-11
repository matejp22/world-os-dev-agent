from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

from app.live_state import (
    current_milestone_version,
    load_live_state,
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
class MilestoneHandoffPlan:
    allowed: bool
    target_file: str
    live_state_sha256: str
    current_milestone: str | None
    current_objective_status: str | None
    next_milestone: str | None
    next_milestone_objective: str | None
    next_milestone_defined_in_roadmap: bool
    reason: str


def milestone_version(
    value: str | None,
) -> str | None:
    if not value:
        return None

    match = re.search(
        r"\b(V\d+(?:\.\d+)*)\b",
        value,
    )

    if not match:
        return None

    return match.group(1)


def roadmap_has_explicit_milestone(
    roadmap_text: str,
    version: str,
) -> bool:
    pattern = re.compile(
        rf"^##\s+{re.escape(version)}\b",
        flags=re.MULTILINE,
    )

    return bool(
        pattern.search(
            roadmap_text
        )
    )


def roadmap_milestone_versions(
    roadmap_text: str,
) -> tuple[str, ...]:
    pattern = re.compile(
        r"^##\s+(V\d+(?:\.\d+)*)\b",
        flags=re.MULTILINE,
    )

    versions = tuple(
        match.group(1)
        for match in pattern.finditer(
            roadmap_text
        )
    )

    if len(versions) != len(
        set(versions)
    ):
        raise RuntimeError(
            "ROADMAP contains duplicate milestone versions."
        )

    return versions


def roadmap_expected_successor(
    roadmap_text: str,
    current_version: str,
) -> str | None:
    versions = roadmap_milestone_versions(
        roadmap_text
    )

    matches = [
        index
        for index, version in enumerate(
            versions
        )
        if version == current_version
    ]

    if len(matches) != 1:
        return None

    index = matches[0]

    if index + 1 >= len(versions):
        return None

    return versions[
        index + 1
    ]


def roadmap_expected_predecessor(
    roadmap_text: str,
    current_version: str,
) -> str | None:
    versions = roadmap_milestone_versions(
        roadmap_text
    )

    matches = [
        index
        for index, version in enumerate(
            versions
        )
        if version == current_version
    ]

    if len(matches) != 1:
        return None

    index = matches[0]

    if index == 0:
        return None

    return versions[
        index - 1
    ]


def build_handoff_plan(
    expected_live_state_sha256: str | None = None,
    live_state_path: Path = LIVE_STATE_PATH,
    roadmap_path: Path = ROADMAP_PATH,
) -> MilestoneHandoffPlan:
    if not live_state_path.exists():
        raise RuntimeError(
            "LIVE_STATE.md is missing."
        )

    if not roadmap_path.exists():
        raise RuntimeError(
            "ROADMAP.md is missing."
        )

    live_bytes = live_state_path.read_bytes()

    live_sha = sha256(
        live_bytes
    ).hexdigest()

    state = load_live_state(
        live_state_path
    )

    roadmap_text = roadmap_path.read_text(
        encoding="utf-8-sig"
    )

    current_version = current_milestone_version(
        state
    )

    next_version = milestone_version(
        state.next_milestone
    )

    expected_successor = (
        roadmap_expected_successor(
            roadmap_text,
            current_version,
        )
        if current_version
        else None
    )

    next_defined = (
        roadmap_has_explicit_milestone(
            roadmap_text,
            next_version,
        )
        if next_version
        else False
    )

    if (
        expected_live_state_sha256 is not None
        and live_sha.casefold()
        != expected_live_state_sha256.strip().casefold()
    ):
        return MilestoneHandoffPlan(
            allowed=False,
            target_file=EXPECTED_TARGET,
            live_state_sha256=live_sha,
            current_milestone=state.current_milestone,
            current_objective_status=state.current_objective_status,
            next_milestone=state.next_milestone,
            next_milestone_objective=state.next_milestone_objective,
            next_milestone_defined_in_roadmap=next_defined,
            reason=(
                "LIVE_STATE SHA256 does not match expected canonical state."
            ),
        )

    if not state.current_milestone:
        return MilestoneHandoffPlan(
            allowed=False,
            target_file=EXPECTED_TARGET,
            live_state_sha256=live_sha,
            current_milestone=None,
            current_objective_status=state.current_objective_status,
            next_milestone=state.next_milestone,
            next_milestone_objective=state.next_milestone_objective,
            next_milestone_defined_in_roadmap=next_defined,
            reason="Current milestone is missing.",
        )

    if current_version is None:
        return MilestoneHandoffPlan(
            allowed=False,
            target_file=EXPECTED_TARGET,
            live_state_sha256=live_sha,
            current_milestone=state.current_milestone,
            current_objective_status=state.current_objective_status,
            next_milestone=state.next_milestone,
            next_milestone_objective=state.next_milestone_objective,
            next_milestone_defined_in_roadmap=next_defined,
            reason=(
                "Current milestone does not contain a valid version."
            ),
        )

    if (
        not state.current_objective_status
        or state.current_objective_status.strip().upper()
        != "COMPLETE"
    ):
        return MilestoneHandoffPlan(
            allowed=False,
            target_file=EXPECTED_TARGET,
            live_state_sha256=live_sha,
            current_milestone=state.current_milestone,
            current_objective_status=state.current_objective_status,
            next_milestone=state.next_milestone,
            next_milestone_objective=state.next_milestone_objective,
            next_milestone_defined_in_roadmap=next_defined,
            reason="Current objective is not COMPLETE.",
        )

    if not state.next_milestone:
        return MilestoneHandoffPlan(
            allowed=False,
            target_file=EXPECTED_TARGET,
            live_state_sha256=live_sha,
            current_milestone=state.current_milestone,
            current_objective_status=state.current_objective_status,
            next_milestone=None,
            next_milestone_objective=state.next_milestone_objective,
            next_milestone_defined_in_roadmap=False,
            reason="No next milestone is defined.",
        )

    if not state.next_milestone_objective:
        return MilestoneHandoffPlan(
            allowed=False,
            target_file=EXPECTED_TARGET,
            live_state_sha256=live_sha,
            current_milestone=state.current_milestone,
            current_objective_status=state.current_objective_status,
            next_milestone=state.next_milestone,
            next_milestone_objective=None,
            next_milestone_defined_in_roadmap=next_defined,
            reason="Next milestone objective is missing.",
        )

    if not next_defined:
        return MilestoneHandoffPlan(
            allowed=False,
            target_file=EXPECTED_TARGET,
            live_state_sha256=live_sha,
            current_milestone=state.current_milestone,
            current_objective_status=state.current_objective_status,
            next_milestone=state.next_milestone,
            next_milestone_objective=state.next_milestone_objective,
            next_milestone_defined_in_roadmap=False,
            reason=(
                "Next milestone is not explicitly defined "
                "as a ROADMAP milestone."
            ),
        )

    if expected_successor is None:
        return MilestoneHandoffPlan(
            allowed=False,
            target_file=EXPECTED_TARGET,
            live_state_sha256=live_sha,
            current_milestone=state.current_milestone,
            current_objective_status=state.current_objective_status,
            next_milestone=state.next_milestone,
            next_milestone_objective=state.next_milestone_objective,
            next_milestone_defined_in_roadmap=True,
            reason=(
                "ROADMAP does not define a deterministic successor "
                "for the current milestone."
            ),
        )

    if next_version != expected_successor:
        return MilestoneHandoffPlan(
            allowed=False,
            target_file=EXPECTED_TARGET,
            live_state_sha256=live_sha,
            current_milestone=state.current_milestone,
            current_objective_status=state.current_objective_status,
            next_milestone=state.next_milestone,
            next_milestone_objective=state.next_milestone_objective,
            next_milestone_defined_in_roadmap=True,
            reason=(
                "Declared next milestone is not the immediate "
                "ROADMAP successor of the current milestone."
            ),
        )

    return MilestoneHandoffPlan(
        allowed=True,
        target_file=EXPECTED_TARGET,
        live_state_sha256=live_sha,
        current_milestone=state.current_milestone,
        current_objective_status=state.current_objective_status,
        next_milestone=state.next_milestone,
        next_milestone_objective=state.next_milestone_objective,
        next_milestone_defined_in_roadmap=True,
        reason=(
            "Canonical handoff prerequisites are satisfied."
        ),
    )


if __name__ == "__main__":
    plan = build_handoff_plan()

    print("MILESTONE HANDOFF DRY RUN")
    print("=" * 72)
    print("Allowed:", plan.allowed)
    print("Target:", plan.target_file)
    print("Current milestone:", plan.current_milestone)
    print("Next milestone:", plan.next_milestone)
    print("Reason:", plan.reason)
