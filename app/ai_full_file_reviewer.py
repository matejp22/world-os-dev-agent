from __future__ import annotations

from openai import OpenAI

from app.context_loader import load_project_context


MODEL = "gpt-5.6-luna"

client = OpenAI()


REVIEW_PROMPT = """
You are the full-file semantic review layer of WORLD OS DEV AGENT.

You receive:
- WORLD OS project context
- development goal
- target file
- a deterministic diff between the current file and an AI candidate

Evaluate whether the proposed source-code change:
- solves the actual stated goal
- is minimal
- preserves safety boundaries
- avoids unnecessary complexity
- does not introduce a workaround for an unrelated issue
- is suitable for human review

Return EXACTLY one of:

REJECT
REVISE
APPROVE_FOR_HUMAN_REVIEW

Then:

REASON:
short explanation

Do not execute anything.
Do not modify files.
Do not approve Git operations or database operations.
"""


def review_full_file_candidate(
    goal: str,
    target_file: str,
    diff: str,
) -> str:
    context = load_project_context()

    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "none"},
        instructions=REVIEW_PROMPT,
        input=(
            "WORLD OS PROJECT CONTEXT:\n"
            f"{context}\n\n"
            "DEVELOPMENT GOAL:\n"
            f"{goal}\n\n"
            "TARGET FILE:\n"
            f"{target_file}\n\n"
            "DETERMINISTIC DIFF:\n"
            f"{diff}"
        ),
        max_output_tokens=220,
    )

    return response.output_text.strip()
