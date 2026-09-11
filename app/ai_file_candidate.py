from __future__ import annotations

from pathlib import Path

from openai import OpenAI

from app.context_loader import load_project_context
from app.patch_source_loader import safe_read_selected_files


MODEL = "gpt-5.6-luna"

client = OpenAI()


GENERATOR_PROMPT = """
You are the full-file candidate generation layer of WORLD OS DEV AGENT.

You receive:
- WORLD OS project context
- the active workspace name
- a development goal
- current contents of selected source files from that workspace

Your task is to propose one minimal code change.

IMPORTANT RULES:
- Do not execute anything.
- Do not modify files.
- Change exactly one Python file.
- Prefer an existing file from CURRENT SOURCE FILES when the goal can be
  satisfied safely by modifying that file.
- If the development goal clearly requires a new module that does not yet
  exist, you may instead propose exactly one new Python file.
- A proposed new file must be inside app/ of the ACTIVE WORKSPACE.
- Do not invent a second file, directory, migration, test file, database
  object, or other side effect.
- For a new file, use CURRENT SOURCE FILES only as read-only contracts and
  architectural references; do not modify those referenced files.
- Never select an unrelated existing file merely because the required new
  target is absent from CURRENT SOURCE FILES.
- Return the COMPLETE new contents of the target file.
- Do not return a diff.
- Do not use Markdown fences.
- Do not add git operations.
- Do not add database writes.
- Do not weaken safety rules.
- Prefer the smallest architecture change that advances
  human-approved local patch generation.

Return exactly:

TARGET_FILE: app/file.py

RATIONALE:
short explanation

NEW_FILE_CONTENT:
complete Python file contents
"""


def generate_candidate(
    goal: str,
    workspace_name: str = "world-os-dev-agent",
) -> str:
    context = load_project_context()

    sources = safe_read_selected_files(
        goal,
        workspace_name,
    )

    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "none"},
        instructions=GENERATOR_PROMPT,
        input=(
            "WORLD OS PROJECT CONTEXT:\n"
            f"{context}\n\n"
            "ACTIVE WORKSPACE:\n"
            f"{workspace_name}\n\n"
            "DEVELOPMENT GOAL:\n"
            f"{goal}\n\n"
            "CURRENT SOURCE FILES:\n"
            f"{sources}"
        ),
        max_output_tokens=6000,
    )

    return response.output_text.strip()


if __name__ == "__main__":
    goal = (
        "Improve the Dev Agent patch workflow so that AI proposes "
        "complete file contents while Python generates unified diffs "
        "deterministically."
    )

    print("=" * 70)
    print("FULL FILE CANDIDATE")
    print("=" * 70)
    print(generate_candidate(goal))
