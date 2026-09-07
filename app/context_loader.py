from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTEXT_DIR = PROJECT_ROOT / "context"


CONTEXT_FILES = (
    "PROJECT_CHARTER.md",
    "AGENT_PROMPT.md",
    "LIVE_STATE.md",
    "CURRENT_STATE.md",
    "PROJECT.md",
    "RESEARCH_ENGINE_STATE.md",
    "WEB_STATE.md",
    "SAFETY_RULES.md",
    "GIT_RULES.md",
    "DB_RULES.md",
    "ROADMAP.md",
)


def load_project_context() -> str:
    sections: list[str] = []

    for filename in CONTEXT_FILES:
        path = CONTEXT_DIR / filename

        if not path.exists():
            continue

        content = path.read_text(
            encoding="utf-8",
        ).strip()

        sections.append(
            f"===== {filename} =====\n{content}"
        )

    return "\n\n".join(sections)
