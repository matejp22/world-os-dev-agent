from __future__ import annotations

from openai import OpenAI


MODEL = "gpt-5.6-luna"

client = OpenAI()


CONTROL_PROMPT = """
You are the control layer of WORLD OS DEV AGENT.

You receive:
- the original user goal
- the latest safe execution report
- the latest AI review

Decide whether another READ-ONLY investigation round is necessary.

Rules:
- Never request writes.
- Never request git add, commit, push.
- Never request database writes.
- Never request migrations.
- Never request destructive commands.
- Do not inspect secrets or .env files.
- Continue only if one additional read-only inspection would materially help.
- Avoid unnecessary API calls because cost matters.

Return EXACTLY one of these formats:

STOP

or

NEXT_GOAL: <one concise read-only investigation goal>
"""


def decide_next_step(
    original_goal: str,
    execution_report: str,
    review: str,
) -> str:
    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "none"},
        instructions=CONTROL_PROMPT,
        input=(
            f"ORIGINAL GOAL:\n{original_goal}\n\n"
            f"EXECUTION REPORT:\n{execution_report}\n\n"
            f"AI REVIEW:\n{review}"
        ),
        max_output_tokens=100,
    )

    return response.output_text.strip()
