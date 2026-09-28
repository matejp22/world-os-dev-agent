from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from typing import Any

from app.milestone_execution_ledger import (
    MilestoneExecutionLedger,
    MilestoneExecutionStep,
    validate_milestone_execution_ledger,
)


_SUPPORTED_WORKSPACE = "world-os-research-engine"
_ALLOWED_STEP_FIELDS = frozenset(
    {
        "title",
        "status",
        "patch_ids",
        "target_files",
        "note",
    }
)
_MIN_SEAMS = 2
_MAX_SEAMS = 8


def _require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")
    return value.strip()


def _slugify_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.casefold()).strip("-")

    if not slug:
        raise ValueError("Step title must produce a non-empty ASCII slug.")

    return slug


def _parse_planning_response(response: object) -> list[dict[str, Any]]:
    if not isinstance(response, str):
        raise TypeError("planning_callable must return a JSON string.")

    try:
        payload = json.loads(response)
    except json.JSONDecodeError as exc:
        raise ValueError("AI response must be strict JSON.") from exc

    if not isinstance(payload, list):
        raise ValueError("AI response must be a JSON list.")

    if not _MIN_SEAMS <= len(payload) <= _MAX_SEAMS:
        raise ValueError("AI response must contain between 2 and 8 seams.")

    parsed: list[dict[str, Any]] = []

    for raw_step in payload:
        if not isinstance(raw_step, dict):
            raise ValueError("Each seam must be a JSON object.")

        if set(raw_step) != _ALLOWED_STEP_FIELDS:
            raise ValueError(
                "Each seam must match the required schema without extra fields."
            )

        title = _require_non_empty_string(raw_step["title"], "title")

        if raw_step["status"] != "PLANNED":
            raise ValueError("Every generated seam must have status PLANNED.")

        if raw_step["patch_ids"] != []:
            raise ValueError("Every generated seam must have empty patch_ids.")

        target_files = raw_step["target_files"]
        if not isinstance(target_files, list) or not target_files:
            raise ValueError("target_files must be a non-empty JSON list.")

        if any(
            not isinstance(target, str) or not target.strip()
            for target in target_files
        ):
            raise ValueError("target_files must contain non-empty strings.")

        note = raw_step["note"]
        if note is not None and not isinstance(note, str):
            raise TypeError("note must be a string or null.")

        parsed.append(
            {
                "title": title,
                "target_files": tuple(target.strip() for target in target_files),
                "note": note,
            }
        )

    return parsed


def _validate_final_closure(seams: list[dict[str, Any]]) -> None:
    final = seams[-1]
    title = final["title"].casefold()
    note = (final["note"] or "").casefold()
    combined = f"{title} {note}"

    readiness_terms = (
        "production readiness",
        "production-ready",
        "production ready",
        "readiness verification",
    )
    closure_terms = (
        "closure",
        "closeout",
        "completion",
        "complete",
        "verification",
        "verify",
    )
    scope_rejection_terms = (
        "no new product scope",
        "reject new product scope",
        "without new product scope",
        "out of scope",
    )

    if not any(term in combined for term in readiness_terms):
        raise ValueError(
            "Final seam must explicitly represent production readiness."
        )

    if not any(term in combined for term in closure_terms):
        raise ValueError(
            "Final seam must explicitly represent milestone closure."
        )

    if not any(term in combined for term in scope_rejection_terms):
        raise ValueError(
            "Final seam must explicitly reject new product scope."
        )


def _default_planning_callable(prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI()
    response = client.responses.create(
        model="gpt-5.6-luna",
        reasoning={"effort": "none"},
        instructions=(
            "Return only strict JSON. Return a JSON list of 2 to 8 seam "
            "objects. Each object must contain exactly these fields: title, "
            "status, patch_ids, target_files, note. Do not include step_id. "
            "Use status PLANNED and an empty patch_ids list. target_files "
            "must be explicit. The final seam must explicitly state "
            "production readiness verification and closure, and reject new "
            "product scope."
        ),
        input=prompt,
        max_output_tokens=1200,
    )
    return response.output_text


def plan_milestone_seams(
    *,
    workspace_name: str,
    milestone_id: str,
    milestone_title: str,
    milestone_objective: str,
    relevant_context: str,
    planning_callable: Callable[[str], str] | None = None,
) -> MilestoneExecutionLedger:
    if workspace_name != _SUPPORTED_WORKSPACE:
        raise ValueError(
            "Only world-os-research-engine is supported."
        )

    milestone_id = _require_non_empty_string(
        milestone_id,
        "milestone_id",
    )
    milestone_title = _require_non_empty_string(
        milestone_title,
        "milestone_title",
    )
    milestone_objective = _require_non_empty_string(
        milestone_objective,
        "milestone_objective",
    )
    relevant_context = _require_non_empty_string(
        relevant_context,
        "relevant_context",
    )

    prompt = (
        "WORKSPACE:\n"
        f"{workspace_name}\n\n"
        "MILESTONE ID:\n"
        f"{milestone_id}\n\n"
        "MILESTONE TITLE:\n"
        f"{milestone_title}\n\n"
        "MILESTONE OBJECTIVE:\n"
        f"{milestone_objective}\n\n"
        "RELEVANT CONTEXT:\n"
        f"{relevant_context}\n"
    )

    planner = planning_callable or _default_planning_callable
    seams = _parse_planning_response(planner(prompt))
    _validate_final_closure(seams)

    steps = tuple(
        MilestoneExecutionStep(
            step_id=f"S{index}-{_slugify_title(seam['title'])}",
            title=seam["title"],
            status="PLANNED",
            patch_ids=(),
            target_files=seam["target_files"],
            note=seam["note"],
        )
        for index, seam in enumerate(seams, start=1)
    )

    ledger = MilestoneExecutionLedger(
        workspace_name=workspace_name,
        milestone_id=milestone_id,
        milestone_title=milestone_title,
        steps=steps,
    )

    validate_milestone_execution_ledger(ledger)
    return ledger