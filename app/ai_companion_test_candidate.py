from __future__ import annotations

from openai import OpenAI

from app.context_loader import load_project_context
from app.patch_source_loader import safe_read_selected_files


MODEL = "gpt-5.6-luna"

client = OpenAI()


COMPANION_TEST_PROMPT = """
You are the autonomous companion-test generation layer of
WORLD OS DEV AGENT.

You receive:
- WORLD OS project context
- active workspace
- original development goal
- source target path
- COMPLETE candidate source contents
- selected read-only source context

Your task is to create exactly one focused permanent pytest regression test
for the source candidate.

RULES:
- Do not modify source files.
- Do not execute anything.
- Return exactly one NEW Python test file.
- The target must be under tests/.
- Prefer a mirrored path:
    app/foo.py -> tests/test_foo.py
    app/research/foo.py -> tests/research/test_foo.py
- File name must start with test_.
- Exercise the real production module.
- Do not duplicate production implementation.
- Include:
    FOCUSED_TARGET_MODULES = ("app.module.path",)
  when the changed source is under app/.
- Test the requested behavioral change and important boundary/failure behavior.
- Use monkeypatch/tmp_path where isolation is needed.
- No Git operations.
- No database writes.
- No unrelated scope.
- No new product scope.

Return exactly:

TARGET_FILE: tests/path/test_file.py

RATIONALE:
short explanation

NEW_FILE_CONTENT:
complete Python test file contents
"""


def generate_companion_test_candidate(
    *,
    goal: str,
    workspace_name: str,
    source_target_file: str,
    source_candidate_content: str,
) -> str:
    context = load_project_context()

    inspection_goal = (
        goal
        + "\n\nInspect contracts relevant to source target: "
        + source_target_file
    )

    sources = safe_read_selected_files(
        inspection_goal,
        workspace_name,
    )

    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "none"},
        instructions=COMPANION_TEST_PROMPT,
        input=(
            "WORLD OS PROJECT CONTEXT:\n"
            f"{context}\n\n"
            "ACTIVE WORKSPACE:\n"
            f"{workspace_name}\n\n"
            "ORIGINAL DEVELOPMENT GOAL:\n"
            f"{goal}\n\n"
            "SOURCE TARGET FILE:\n"
            f"{source_target_file}\n\n"
            "SOURCE CANDIDATE CONTENT:\n"
            f"{source_candidate_content}\n\n"
            "READ-ONLY SOURCE CONTEXT:\n"
            f"{sources}"
        ),
        max_output_tokens=20000,
    )

    return response.output_text.strip()
