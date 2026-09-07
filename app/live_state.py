from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LIVE_STATE_PATH = PROJECT_ROOT / "context" / "LIVE_STATE.md"

NO_NEW_MILESTONE = "NO_NEW_MILESTONE"


@dataclass(frozen=True)
class LiveState:
    completed_milestones: tuple[str, ...]
    current_milestone: str | None
    next_milestone: str | None
    next_milestone_objective: str | None
    current_objective: str | None
    current_objective_status: str | None
    immediate_next_objective: str | None


def _extract_section(
    text: str,
    heading: str,
) -> str | None:
    pattern = re.compile(
        rf"^{re.escape(heading)}:[ \t]*$\n"
        rf"(.*?)(?=\n[A-Za-z0-9][^\n]*:[ \t]*$|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )

    match = pattern.search(text)

    if not match:
        return None

    value = match.group(1).strip()

    return value or None


def _extract_completed_milestones(
    text: str,
) -> tuple[str, ...]:
    lines = text.splitlines()
    completed: list[str] = []

    for index, line in enumerate(lines):
        match = re.fullmatch(
            r"(V\d+(?:\.\d+)*) STATUS:",
            line.strip(),
        )

        if not match:
            continue

        milestone = match.group(1)

        if index + 1 >= len(lines):
            continue

        status = lines[index + 1].strip()

        if status == "COMPLETE":
            completed.append(milestone)

    return tuple(completed)


def parse_live_state(
    text: str,
) -> LiveState:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    return LiveState(
        completed_milestones=_extract_completed_milestones(
            normalized
        ),
        current_milestone=_extract_section(
            normalized,
            "Current milestone",
        ),
        next_milestone=_extract_section(
            normalized,
            "Next milestone",
        ),
        next_milestone_objective=_extract_section(
            normalized,
            "Next milestone objective",
        ),
        current_objective=_extract_section(
            normalized,
            "Current objective",
        ),
        current_objective_status=_extract_section(
            normalized,
            "Current objective status",
        ),
        immediate_next_objective=_extract_section(
            normalized,
            "Immediate next objective",
        ),
    )


def load_live_state(
    path: Path = LIVE_STATE_PATH,
) -> LiveState:
    text = path.read_text(
        encoding="utf-8-sig",
    )

    return parse_live_state(text)


def current_milestone_version(
    state: LiveState,
) -> str | None:
    if not state.current_milestone:
        return None

    match = re.search(
        r"\b(V\d+(?:\.\d+)*)\b",
        state.current_milestone,
    )

    if not match:
        return None

    return match.group(1)


def planning_milestone(
    state: LiveState,
) -> tuple[str, str] | None:
    current_version = current_milestone_version(state)

    if current_version is None:
        return None

    if current_version not in state.completed_milestones:
        return None

    next_milestone = (
        state.next_milestone or ""
    ).strip()

    next_objective = (
        state.next_milestone_objective or ""
    ).strip()

    if not next_milestone or not next_objective:
        return None

    if (
        state.current_milestone
        and next_milestone.casefold()
        == state.current_milestone.strip().casefold()
    ):
        return None

    return (
        next_milestone,
        next_objective,
    )


def planning_objective(
    state: LiveState,
) -> str | None:
    current = (
        state.current_objective or ""
    ).strip()

    status = (
        state.current_objective_status or ""
    ).strip().upper()

    next_objective = (
        state.immediate_next_objective or ""
    ).strip()

    if current:
        if not status:
            return None

        if status == "COMPLETE":
            if not next_objective:
                return None

            if (
                next_objective.casefold()
                == current.casefold()
            ):
                return None

            return next_objective

        return current

    if next_objective:
        return next_objective

    return None


def has_active_milestone(
    state: LiveState,
) -> bool:
    version = current_milestone_version(state)

    if version is None:
        return False

    if version in state.completed_milestones:
        return False

    if planning_objective(state) is None:
        return False

    return True
