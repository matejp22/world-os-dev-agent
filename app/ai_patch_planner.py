from __future__ import annotations

from openai import OpenAI

from app.context_loader import load_project_context
from app.patch_source_loader import safe_read_selected_files


MODEL = "gpt-5.6-luna"

client = OpenAI()


PATCH_PROMPT = """
You are the patch-planning layer of WORLD OS DEV AGENT.

You receive:
- WORLD OS project context
- a development goal
- exact current contents of selected Dev Agent source files

Your task is to propose the smallest safe code change that advances
human-approved local code patch generation.

IMPORTANT:
- Do NOT execute anything.
- Do NOT modify files.
- Do NOT invent current file contents.
- Use only files shown in CURRENT SOURCE FILES.
- Prefer a minimal architecture change.
- Do not propose repository writes, git add, git commit, git push,
  database writes, migrations, or production changes.

Return exactly this structure:

TARGET_FILE: relative/path/to/file

RATIONALE:
short explanation

PROPOSED_PATCH:
unified diff text
"""


def propose_patch(goal: str) -> str:
    project_context = load_project_context()
    source_files = safe_read_selected_files(goal)

    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "none"},
        instructions=PATCH_PROMPT,
        input=(
            "WORLD OS PROJECT CONTEXT:\n"
            f"{project_context}\n\n"
            "DEVELOPMENT GOAL:\n"
            f"{goal}\n\n"
            "CURRENT SOURCE FILES:\n"
            f"{source_files}"
        ),
        max_output_tokens=900,
    )

    return response.output_text.strip()


if __name__ == "__main__":
    goal = (
        "Prepare the next Dev Agent architecture change for "
        "human-approved local code patch generation."
    )

    print("MODEL:")
    print(MODEL)
    print()
    print("GOAL:")
    print(goal)
    print()
    print("PATCH PROPOSAL:")
    print(propose_patch(goal))
