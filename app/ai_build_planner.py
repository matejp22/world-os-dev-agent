from __future__ import annotations

from openai import OpenAI

from app.context_loader import load_project_context
from app.live_state import (
    NO_NEW_MILESTONE,
    has_active_milestone,
    load_live_state,
    planning_objective,
    planning_milestone,
)


MODEL = "gpt-5.6-luna"

client = OpenAI()


BUILD_PROMPT = """
You are the build-planning layer of WORLD OS DEV AGENT.

You receive:
- WORLD OS project context
- LIVE_STATE
- a high-level developer instruction

Your task is to determine the single best next development objective.

Rules:
- Treat LIVE_STATE.md as the primary handoff.
- The deterministic planner gate has already validated the active milestone.
- Work only inside the supplied active milestone and immediate objective.
- Never select work from a completed milestone.
- Do not rediscover completed work.
- Do not propose multiple milestones.
- Choose one small, concrete next objective.
- Prefer work that advances the explicit current architecture milestone.
- Respect all safety, Git and database rules.
- Do not execute anything.
- Do not propose git add, commit, push, database writes or production changes.
- Keep the objective small enough for one code-review cycle.

Return exactly:

NEXT_OBJECTIVE:
<one concrete development objective>

WHY:
<short explanation>
"""


def plan_next_build(user_instruction: str) -> str:
    state = load_live_state()

    milestone = state.current_milestone
    objective = None

    if has_active_milestone(state):
        objective = planning_objective(state)
    else:
        next_plan = planning_milestone(state)

        if next_plan is not None:
            milestone, objective = next_plan

    if not milestone or objective is None:
        return NO_NEW_MILESTONE

    context = load_project_context()

    active_state = (
        "ACTIVE MILESTONE:\n"
        f"{milestone}\n\n"
        "IMMEDIATE NEXT OBJECTIVE:\n"
        f"{objective}"
    )

    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "none"},
        instructions=BUILD_PROMPT,
        input=(
            "WORLD OS PROJECT CONTEXT:\n"
            f"{context}\n\n"
            f"{active_state}\n\n"
            "DEVELOPER INSTRUCTION:\n"
            f"{user_instruction}"
        ),
        max_output_tokens=220,
    )

    result = response.output_text.strip()

    if not result.startswith("NEXT_OBJECTIVE:"):
        raise RuntimeError(
            "Build planner returned an invalid output contract."
        )

    if "\nWHY:" not in result:
        raise RuntimeError(
            "Build planner output is missing WHY."
        )

    return result


if __name__ == "__main__":
    instruction = "Continue building the current World OS milestone."

    print("=" * 70)
    print("WORLD OS DEV AGENT - BUILD PLANNER")
    print("=" * 70)
    print()
    print(plan_next_build(instruction))
