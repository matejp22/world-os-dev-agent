from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.safe_executor import execute_safe


REPO_PATH = r"C:\Users\matej\Documents\world-os-research-engine"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"


COMMANDS = [
    "git status --short",
    "git log -1 --oneline",
    "git branch --show-current",
    "git diff --check",
]


def build_report() -> str:
    sections: list[str] = []

    for command in COMMANDS:
        execution = execute_safe(
            command=command,
            cwd=REPO_PATH,
        )

        lines = [
            "=" * 70,
            "COMMAND:",
            command,
            "",
            "POLICY ALLOWED:",
            str(execution.allowed),
            "",
            "POLICY REASON:",
            execution.policy_reason,
        ]

        if execution.result is not None:
            lines.extend(
                [
                    "",
                    "EXIT CODE:",
                    str(execution.result.exit_code),
                    "",
                    "STDOUT:",
                    execution.result.stdout or "<empty>",
                    "",
                    "STDERR:",
                    execution.result.stderr or "<empty>",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "EXECUTION:",
                    "BLOCKED BEFORE POWERSHELL",
                ]
            )

        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def save_report(report: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"safe_repo_check_{timestamp}.txt"

    log_path.write_text(report, encoding="utf-8")

    return log_path


def main() -> None:
    report = build_report()
    log_path = save_report(report)

    print(report)
    print()
    print("=" * 70)
    print("SAFE LOG SAVED:")
    print(log_path)


if __name__ == "__main__":
    main()
