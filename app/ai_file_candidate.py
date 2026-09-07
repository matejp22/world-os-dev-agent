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
- a development goal
- current contents of selected local Dev Agent source files

Your task is to propose one minimal code change.

IMPORTANT RULES:
- Do not execute anything.
- Do not modify files.
- Change exactly one existing Python file.
- Use only a file present in CURRENT SOURCE FILES.
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


def generate_candidate(goal: str) -> str:
    context = load_project_context()
    sources = safe_read_selected_files(goal)

    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "none"},
        instructions=GENERATOR_PROMPT,
        input=(
            "WORLD OS PROJECT CONTEXT:\n"
            f"{context}\n\n"
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
