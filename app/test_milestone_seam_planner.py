from __future__ import annotations

import json

import pytest

from app.milestone_seam_planner import plan_milestone_seams


FOCUSED_TARGET_MODULES = (
    "app.milestone_seam_planner",
)


def _valid_response() -> str:
    return json.dumps(
        [
            {
                "title": "Inspect Relevant Source Boundaries",
                "status": "PLANNED",
                "patch_ids": [],
                "target_files": [
                    "app/research/example.py",
                ],
                "note": (
                    "Inspect only the bounded relevant source behavior "
                    "required by this milestone."
                ),
            },
            {
                "title": "Production Readiness Closure",
                "status": "PLANNED",
                "patch_ids": [],
                "target_files": [
                    "app/research/example.py",
                ],
                "note": (
                    "Run production readiness milestone verification "
                    "and closure with no new product scope."
                ),
            },
        ]
    )


def _plan(response: str):
    return plan_milestone_seams(
        workspace_name="world-os-research-engine",
        milestone_id="milestone-example",
        milestone_title="Example Milestone",
        milestone_objective="Complete one bounded example milestone.",
        relevant_context="Only app/research/example.py is relevant.",
        planning_callable=lambda _prompt: response,
    )


def test_generates_deterministic_step_ids_from_titles() -> None:
    first = _plan(_valid_response())
    second = _plan(_valid_response())

    assert tuple(step.step_id for step in first.steps) == (
        "S1-inspect-relevant-source-boundaries",
        "S2-production-readiness-closure",
    )

    assert tuple(step.step_id for step in second.steps) == (
        "S1-inspect-relevant-source-boundaries",
        "S2-production-readiness-closure",
    )

    assert all(step.status == "PLANNED" for step in first.steps)
    assert all(step.patch_ids == () for step in first.steps)


def test_rejects_ai_supplied_step_id() -> None:
    payload = json.loads(_valid_response())
    payload[0]["step_id"] = "S1-model-controlled-id"

    with pytest.raises(
        ValueError,
        match="required schema",
    ):
        _plan(json.dumps(payload))


def test_rejects_wrong_workspace() -> None:
    with pytest.raises(
        ValueError,
        match="Only world-os-research-engine is supported",
    ):
        plan_milestone_seams(
            workspace_name="world-os-dev-agent",
            milestone_id="milestone-example",
            milestone_title="Example Milestone",
            milestone_objective="Bounded objective.",
            relevant_context="Bounded context.",
            planning_callable=lambda _prompt: _valid_response(),
        )
