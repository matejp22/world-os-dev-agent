from __future__ import annotations

from pathlib import Path

from openai import OpenAI

from app.context_loader import load_project_context
from app.workspace_registry import get_workspace_profile


MODEL = "gpt-5.6-luna"

client = OpenAI()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


INSPECT_PROMPT = """
You are the inspection-planning layer of WORLD OS DEV AGENT.

You receive:
- WORLD OS project context
- a development goal
- the active workspace name
- an exact list of existing source files inside that workspace

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


def existing_app_files(
    workspace_name: str = "world-os-dev-agent",
) -> list[str]:
    workspace = get_workspace_profile(
        workspace_name
    )

    workspace_root = workspace.path.resolve()
    app_dir = workspace_root / "app"

    if not app_dir.exists() or not app_dir.is_dir():
        raise RuntimeError(
            f"Workspace app directory does not exist: {app_dir}"
        )

    if workspace.name == "world-os-dev-agent":
        paths = app_dir.glob("*.py")
    else:
        paths = app_dir.rglob("*.py")

    files = [
        str(path.relative_to(workspace_root)).replace("\\", "/")
        for path in paths
        if path.is_file()
        and path.name != "__init__.py"
    ]

    scripts_dir = workspace_root / "scripts"

    if scripts_dir.exists() and scripts_dir.is_dir():
        files.extend(
            str(path.relative_to(workspace_root)).replace("\\", "/")
            for path in scripts_dir.glob("test_*.py")
            if path.is_file()
        )

    return sorted(files)


def propose_inspection(
    goal: str,
    workspace_name: str = "world-os-dev-agent",
) -> str:
    project_context = load_project_context()

    workspace = get_workspace_profile(
        workspace_name
    )

    files = existing_app_files(
        workspace.name
    )

    response = client.responses.create(
        model=MODEL,
        reasoning={"effort": "none"},
        instructions=INSPECT_PROMPT,
        input=(
            "WORLD OS PROJECT CONTEXT:\n"
            f"{project_context}\n\n"
            "ACTIVE WORKSPACE:\n"
            f"{workspace.name}\n\n"
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