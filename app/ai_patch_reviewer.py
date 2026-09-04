from __future__ import annotations

from openai import OpenAI

from app.context_loader import load_project_context


MODEL = "gpt-5.6-luna"

client = OpenAI()


REVIEW_PROMPT = """
You are the semantic patch-review layer of WORLD OS DEV AGENT.

You receive:
- WORLD OS project context
- a development goal
- a structurally validated patch proposal

Your task is to judge whether the proposed patch is architecturally appropriate.

Evaluate:
- Does it solve the actual stated goal?
- Is it minimal?
- Is it deterministic?
- Does it introduce a workaround instead of solving the real problem?
- Does it increase complexity unnecessarily?
- Is it consistent with LIVE_STATE and safety rules?
- Should a human developer review it?

Return EXACTLY one of these decisions:

REJECT
REVISE
APPROVE_FOR_HUMAN_REVIEW

Then add:

REASON:
<short explanation>

Do not execute anything.
Do not modify files.
Do not approve Git or database actions.
"""


def review_patch(
    goal: str,
    proposal: str,
) -> str:
    project_context = load_project_context()

    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "none"},
        instructions=REVIEW_PROMPT,
        input=(
            "WORLD OS PROJECT CONTEXT:\n"
            f"{project_context}\n\n"
            "DEVELOPMENT GOAL:\n"
            f"{goal}\n\n"
            "PATCH PROPOSAL:\n"
            f"{proposal}"
        ),
        max_output_tokens=220,
    )

    return response.output_text.strip()
