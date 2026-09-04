from __future__ import annotations

from pathlib import Path

from app.ai_patch_inspector import propose_inspection


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


def safe_read_selected_files(goal: str) -> str:
    raw_paths = propose_inspection(goal)
    selected = parse_paths(raw_paths)

    sections: list[str] = []

    for relative_path in selected:
        candidate = (PROJECT_ROOT / relative_path).resolve()

        try:
            candidate.relative_to(PROJECT_ROOT)
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

        if len(content) > MAX_CHARS_PER_FILE:
            content = (
                content[:MAX_CHARS_PER_FILE]
                + "\n<file-truncated>"
            )

        sections.append(
            f"===== {relative_path} =====\n{content}"
        )

    return "\n\n".join(sections)
