from __future__ import annotations

from pathlib import Path

from openai import OpenAI

from app.context_loader import load_project_context


MODEL = "gpt-5.6-luna"

client = OpenAI()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "app"


INSPECT_PROMPT = """
You are the inspection-planning layer of WORLD OS DEV AGENT.

You receive:
- WORLD OS project context
- a development goal
- an exact list of existing local Dev Agent source files

Your task is to select the minimum set of EXISTING files that must be inspected
before a safe patch can be proposed.

RULES:
- Do not invent file paths.
- Choose only from the supplied EXISTING FILES list.
- Do not execute anything.
- Do not modify anything.
- Prefer files directly related to patch planning, execution, approval,
  safety policy, or context.
- Return only relative paths.
- One path per line.
- Maximum 5 files.
"""


def existing_app_files() -> list[str]:
    return sorted(
        str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        for path in APP_DIR.glob("*.py")
        if path.name != "__init__.py"
    )


def propose_inspection(goal: str) -> str:
    project_context = load_project_context()
    files = existing_app_files()

    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "none"},
        instructions=INSPECT_PROMPT,
        input=(
            "WORLD OS PROJECT CONTEXT:\n"
            f"{project_context}\n\n"
            "DEVELOPMENT GOAL:\n"
            f"{goal}\n\n"
            "EXISTING FILES:\n"
            + "\n".join(files)
        ),
        max_output_tokens=150,
    )

    return response.output_text.strip()


if __name__ == "__main__":
    goal = (
        "Prepare the next Dev Agent architecture change for "
        "human-approved local code patch generation."
    )

    print("FILES TO INSPECT:")
    print(propose_inspection(goal))
