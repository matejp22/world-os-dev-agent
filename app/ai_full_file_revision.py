from __future__ import annotations

from openai import OpenAI

from app.context_loader import load_project_context


MODEL = "gpt-5.6-luna"

client = OpenAI()


REVISION_PROMPT = """
You are the full-file revision layer of WORLD OS DEV AGENT.

You receive:
- WORLD OS project context
- the development goal
- current target file content
- deterministic review diff
- semantic review feedback

Your task is to produce a revised COMPLETE version of exactly one existing Python file.

IMPORTANT RULES:
- Address the semantic review directly.
- Do not execute anything.
- Do not modify files.
- Change exactly one existing Python file.
- Do not return a diff.
- Return the COMPLETE file contents.
- Do not use Markdown fences.
- Do not weaken approval or safety boundaries.
- Require integrity metadata when appropriate.
- Preserve rollback behavior.
- Prefer deterministic and transactional behavior.
- Do not add git operations or database writes.

Return exactly:

TARGET_FILE: app/file.py

RATIONALE:
short explanation

NEW_FILE_CONTENT:
complete Python file contents
"""


def revise_candidate(
    goal: str,
    target_file: str,
    current_content: str,
    diff: str,
    semantic_review: str,
) -> str:
    context = load_project_context()

    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "none"},
        instructions=REVISION_PROMPT,
        input=(
            "WORLD OS PROJECT CONTEXT:\n"
            f"{context}\n\n"
            "DEVELOPMENT GOAL:\n"
            f"{goal}\n\n"
            "TARGET FILE:\n"
            f"{target_file}\n\n"
            "CURRENT FILE CONTENT:\n"
            f"{current_content}\n\n"
            "CURRENT DETERMINISTIC DIFF:\n"
            f"{diff}\n\n"
            "SEMANTIC REVIEW FEEDBACK:\n"
            f"{semantic_review}"
        ),
        max_output_tokens=6000,
    )

    return response.output_text.strip()
