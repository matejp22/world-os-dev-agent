from __future__ import annotations

from openai import OpenAI


MODEL = "gpt-5.6-luna"

client = OpenAI()


REVIEW_PROMPT = """
You are the review layer of WORLD OS DEV AGENT.

You receive:
- a user development goal
- executed read-only commands
- their stdout/stderr
- policy decisions

Your job:
- summarize what was learned
- identify any obvious issue
- recommend exactly one next safe step
- do not invent facts
- do not propose destructive actions
- do not propose git push, git commit, git add, database writes, migrations,
  Remove-Item, DROP, DELETE, INSERT, UPDATE, or production changes
- keep the answer concise
- plain text only
"""


def review_run(goal: str, execution_report: str) -> str:
    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "none"},
        instructions=REVIEW_PROMPT,
        input=(
            f"USER GOAL:\n{goal}\n\n"
            f"EXECUTION REPORT:\n{execution_report}"
        ),
        max_output_tokens=250,
    )

    return response.output_text.strip()
