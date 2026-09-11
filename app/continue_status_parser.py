from __future__ import annotations

import re
from dataclasses import dataclass


VALID_STATUSES = {
    "READY_FOR_HUMAN_REVIEW",
    "DRAFT",
    "REJECTED",
}

VALID_TRANSITION_ACTIONS = {
    "PERSIST",
    "NO_WRITE",
    "BLOCK",
}

VALID_TRANSITION_DECISIONS = {
    "INITIALIZE_FROM_LIVE_STATE",
    "RESUME_PERSISTED",
    "ADVANCE_FROM_LIVE_STATE",
    "RECONCILE_AFTER_HANDOFF",
    "COMPLETE_TO_NO_NEW_MILESTONE",
    "CONFLICT",
}

VALID_CONTINUE_ACTIONS = {
    "CONTINUE_SAFELY",
    "REVIEW_PATCH",
    "REVISE_PATCH",
    "NO_ACTION",
}

AUTHORIZED_NEXT_OBJECTIVE_DECISIONS = {
    "RESUME_PERSISTED",
    "ADVANCE_FROM_LIVE_STATE",
    "RECONCILE_AFTER_HANDOFF",
}

MAX_NEXT_OBJECTIVE_LENGTH = 500


@dataclass(frozen=True)
class ContinueMilestoneStatus:
    objective: str | None
    phase: str | None
    patch_id: str | None
    target_file: str | None
    semantic_decision: str | None
    semantic_review: str | None
    status: str | None
    transition_action: str | None
    transition_decision: str | None
    transition_reason: str | None
    next_objective: str | None = None
    next_action: str | None = None


def _normalize(text: str) -> str:
    return (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


def _is_separator(line: str) -> bool:
    return bool(
        re.fullmatch(
            r"-+",
            line.strip(),
        )
    )


def _is_section_heading(
    lines: list[str],
    index: int,
) -> bool:
    if index + 1 >= len(lines):
        return False

    heading = lines[index].strip()

    if not heading:
        return False

    return _is_separator(
        lines[index + 1]
    )


def _extract_section(
    text: str,
    label: str,
) -> str | None:
    lines = text.splitlines()

    for index, line in enumerate(lines):
        if line.strip() != label:
            continue

        if not _is_section_heading(
            lines,
            index,
        ):
            continue

        content_start = index + 2
        content_end = len(lines)

        for current_index in range(
            content_start,
            len(lines),
        ):
            if _is_section_heading(
                lines,
                current_index,
            ):
                content_end = current_index
                break

        value = "\n".join(
            lines[
                content_start:
                content_end
            ]
        ).strip()

        return value or None

    return None


def _extract_field(
    text: str,
    label: str,
    *,
    last: bool = False,
) -> str | None:
    matches = re.findall(
        rf"^{re.escape(label)}:\s*(.+)$",
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )

    if not matches:
        return None

    value = (
        matches[-1]
        if last
        else matches[0]
    ).strip()

    return value or None


def _extract_transition_field(
    text: str,
    label: str,
) -> str | None:
    section = _extract_section(
        text,
        "TASK STATE TRANSITION",
    )

    if section is None:
        return None

    return _extract_field(
        section,
        label,
    )


def _has_section(
    text: str,
    label: str,
) -> bool:
    lines = text.splitlines()

    for index, line in enumerate(lines):
        if (
            line.strip() == label
            and _is_section_heading(
                lines,
                index,
            )
        ):
            return True

    return False


def _detect_phase(
    text: str,
) -> str | None:
    explicit = (
        _extract_field(
            text,
            "Current phase",
            last=True,
        )
        or _extract_field(
            text,
            "Phase",
            last=True,
        )
    )

    if explicit:
        return explicit

    phase_map = (
        (
            "PATCH METADATA",
            "PATCH REVIEW",
        ),
        (
            "BUILD PATCH",
            "BUILD PATCH",
        ),
        (
            "READ-ONLY INVESTIGATION",
            "READ-ONLY INVESTIGATION",
        ),
        (
            "BUILD PLANNER",
            "BUILD PLANNER",
        ),
    )

    for heading, phase in phase_map:
        if _has_section(
            text,
            heading,
        ):
            return phase

    return None


def _normalize_status(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip().upper()

    if normalized in VALID_STATUSES:
        return normalized

    return None


def _normalize_transition_action(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip().upper()

    if normalized in VALID_TRANSITION_ACTIONS:
        return normalized

    return None


def _normalize_transition_decision(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip().upper()

    if normalized in VALID_TRANSITION_DECISIONS:
        return normalized

    return None


def _normalize_continue_action(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip().upper()

    if normalized in VALID_CONTINUE_ACTIONS:
        return normalized

    return None


def _validate_next_objective(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip()

    if not normalized:
        return None

    lines = [
        line.strip()
        for line in normalized.splitlines()
        if line.strip()
    ]

    if len(lines) != 1:
        return None

    objective = lines[0]

    if len(objective) > MAX_NEXT_OBJECTIVE_LENGTH:
        return None

    return objective


def _derive_next_action(
    *,
    explicit_action: str | None,
    status: str | None,
    phase: str | None,
    transition_decision: str | None,
    next_objective: str | None,
) -> str | None:
    normalized = _normalize_continue_action(
        explicit_action
    )

    if normalized is not None:
        return normalized

    if status == "READY_FOR_HUMAN_REVIEW":
        return "REVIEW_PATCH"

    if status == "REJECTED":
        return "REVISE_PATCH"

    if transition_decision == "CONFLICT":
        return "NO_ACTION"

    if (
        next_objective is not None
        and transition_decision
        in AUTHORIZED_NEXT_OBJECTIVE_DECISIONS
    ):
        return "CONTINUE_SAFELY"

    if phase in {
        "READ-ONLY INVESTIGATION",
        "BUILD PLANNER",
        "BUILD PATCH",
        "PATCH REVIEW",
    }:
        return "CONTINUE_SAFELY"

    return None


def parse_continue_milestone_output(
    text: str,
) -> ContinueMilestoneStatus:
    normalized = _normalize(text)

    phase = _detect_phase(
        normalized
    )

    status = _normalize_status(
        _extract_field(
            normalized,
            "Status",
            last=True,
        )
    )

    transition_decision = _normalize_transition_decision(
        _extract_transition_field(
            normalized,
            "Decision",
        )
    )

    next_objective = _validate_next_objective(
        _extract_section(
            normalized,
            "NEXT OBJECTIVE",
        )
    )

    return ContinueMilestoneStatus(
        objective=_extract_section(
            normalized,
            "SELECTED OBJECTIVE",
        ),
        phase=phase,
        patch_id=_extract_field(
            normalized,
            "Patch ID",
            last=True,
        ),
        target_file=_extract_field(
            normalized,
            "Target file",
            last=True,
        ),
        semantic_decision=_extract_field(
            normalized,
            "Semantic decision",
            last=True,
        ),
        semantic_review=_extract_section(
            normalized,
            "SEMANTIC REVIEW",
        ),
        status=status,
        transition_action=_normalize_transition_action(
            _extract_transition_field(
                normalized,
                "Action",
            )
        ),
        transition_decision=transition_decision,
        transition_reason=_extract_transition_field(
            normalized,
            "Reason",
        ),
        next_objective=next_objective,
        next_action=_derive_next_action(
            explicit_action=_extract_field(
                normalized,
                "Next action",
                last=True,
            ),
            status=status,
            phase=phase,
            transition_decision=transition_decision,
            next_objective=next_objective,
        ),
    )