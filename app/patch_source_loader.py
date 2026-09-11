from __future__ import annotations

from pathlib import Path

from app.ai_patch_inspector import propose_inspection
from app.workspace_registry import get_workspace_profile


PROJECT_ROOT = Path(__file__).resolve().parent.parent

MAX_FILES = 5
MAX_CHARS_PER_FILE = 12000


def parse_paths(raw: str) -> list[str]:
    result: list[str] = []

    for line in raw.splitlines():
        path = line.strip()

        if not path:
            continue

        result.append(path)

    return result[:MAX_FILES]


def normalize_relative_path(path: str) -> str:
    normalized = path.replace("\\", "/")

    while normalized.startswith("./"):
        normalized = normalized[2:]

    return normalized


def goal_explicitly_names_path(
    goal: str,
    relative_path: str,
) -> bool:
    normalized_goal = goal.replace("\\", "/")
    normalized_path = normalize_relative_path(relative_path)

    goal_tokens = {
        token.strip(" \t\r\n,.;:!?()[]{}<>\"'`")
        for token in normalized_goal.split()
    }

    return normalized_path in goal_tokens


def safe_read_selected_files(
    goal: str,
    workspace_name: str = "world-os-dev-agent",
) -> str:
    workspace = get_workspace_profile(
        workspace_name
    )

    workspace_root = workspace.path.resolve()

    raw_paths = propose_inspection(
        goal,
        workspace.name,
    )

    selected = parse_paths(raw_paths)

    sections: list[str] = []

    for relative_path in selected:
        candidate = (
            workspace_root
            / relative_path
        ).resolve()

        try:
            candidate.relative_to(
                workspace_root
            )
        except ValueError:
            continue

        if candidate.suffix.lower() != ".py":
            continue

        if not candidate.exists() or not candidate.is_file():
            continue

        content = candidate.read_text(
            encoding="utf-8",
            errors="replace",
        )

        normalized_path = normalize_relative_path(
            str(
                candidate.relative_to(
                    workspace_root
                )
            )
        )

        is_explicit_target = (
            goal_explicitly_names_path(
                goal,
                normalized_path,
            )
        )

        if (
            not is_explicit_target
            and len(content) > MAX_CHARS_PER_FILE
        ):
            content = (
                content[:MAX_CHARS_PER_FILE]
                + "\n<file-truncated>"
            )

        sections.append(
            f"===== {relative_path} =====\n{content}"
        )

    return "\n\n".join(sections)