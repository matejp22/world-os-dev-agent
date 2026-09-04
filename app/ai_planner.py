from __future__ import annotations

from openai import OpenAI

from app.context_loader import load_project_context


MODEL = "gpt-5.6-luna"

client = OpenAI()


SYSTEM_PROMPT = """
You are the planning layer of WORLD OS DEV AGENT.

You receive:
1. WORLD OS project context
2. the user's development goal

IMPORTANT:
- Treat LIVE_STATE.md as the primary handoff for what is currently happening.
- Use PROJECT.md and CURRENT_STATE.md as background context.
- Use SAFETY_RULES.md, GIT_RULES.md and DB_RULES.md as hard constraints.
- Do not rediscover the repository if LIVE_STATE already answers the question.
- If the user asks what to do next, prefer the explicit next objective or
  architecture milestone from LIVE_STATE.
- Propose only the minimum read-only commands necessary to verify the next step.
- If no shell inspection is necessary, return exactly:
  NO_COMMANDS_REQUIRED

RULES:
- Do not execute anything.
- Never propose destructive commands.
- Never propose git push, git commit, git add, Remove-Item, repository writes,
  database writes, Supabase production writes, DROP, DELETE, INSERT, UPDATE,
  ALTER, or migrations.
- Never read .env or secret files.
- Never inspect Supabase temporary metadata.
- Never inspect .git internals.
- Do not propose Set-Location.
- Avoid broad filesystem crawls.
- Keep output small because API cost matters.
- Return only commands, one command per line.
- Do not use Markdown.
- Do not explain commands.
- Maximum 5 commands.
"""


def create_plan(goal: str) -> str:
    project_context = load_project_context()

    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "none"},
        instructions=SYSTEM_PROMPT,
        input=(
            "WORLD OS PROJECT CONTEXT:\n"
            f"{project_context}\n\n"
            "USER GOAL:\n"
            f"{goal}"
        ),
        max_output_tokens=160,
    )

    return response.output_text.strip()


if __name__ == "__main__":
    goal = "What should we work on next?"

    print("MODEL:")
    print(MODEL)
    print()
    print("GOAL:")
    print(goal)
    print()
    print("AI PROPOSED COMMANDS:")
    print(create_plan(goal))
