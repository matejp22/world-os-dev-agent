from __future__ import annotations

from openai import OpenAI

from app.context_loader import load_project_context


MODEL = "gpt-5.6-luna"

client = OpenAI()


REPAIR_PROMPT = """
You are the patch-repair layer of WORLD OS DEV AGENT.

You receive:
- WORLD OS project context
- the original patch proposal
- the exact git apply --check error

Your task is to repair ONLY the unified diff syntax or context so that
the patch can pass git apply --check.

Rules:
- Do not change the intended architecture unless necessary.
- Do not add new files.
- Do not target multiple files.
- Do not execute anything.
- Do not modify files.
- Do not propose git add, commit, push, database writes, or migrations.
- Return the full proposal again in this exact structure:

TARGET_FILE: relative/path

RATIONALE:
short explanation

PROPOSED_PATCH:
unified diff text

Do not wrap the diff in Markdown fences.
"""


def repair_patch(
    proposal: str,
    error_text: str,
) -> str:
    context = load_project_context()

    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "none"},
        instructions=REPAIR_PROMPT,
        input=(
            "WORLD OS PROJECT CONTEXT:\n"
            f"{context}\n\n"
            "ORIGINAL PATCH PROPOSAL:\n"
            f"{proposal}\n\n"
            "GIT APPLY CHECK ERROR:\n"
            f"{error_text}"
        ),
        max_output_tokens=900,
    )

    return response.output_text.strip()
