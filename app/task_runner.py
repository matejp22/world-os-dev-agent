from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from app.safe_executor import execute_safe


DEFAULT_REPO = r"C:\Users\matej\Documents\world-os-research-engine"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"


def build_report(
    command: str,
    repo_path: str,
) -> str:
    execution = execute_safe(
        command=command,
        cwd=repo_path,
    )

    lines = [
        "=" * 70,
        "WORLD OS DEV AGENT",
        "=" * 70,
        "",
        "REPO:",
        repo_path,
        "",
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

    return "\n".join(lines)


def save_report(report: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"task_{timestamp}.txt"

    log_path.write_text(
        report,
        encoding="utf-8",
    )

    return log_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WORLD OS DEV AGENT command gateway"
    )

    parser.add_argument(
        "--command",
        required=True,
        help="PowerShell or CLI command to evaluate and execute",
    )

    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help="Working repository path",
    )

    args = parser.parse_args()

    report = build_report(
        command=args.command,
        repo_path=args.repo,
    )

    log_path = save_report(report)

    print(report)
    print()
    print("=" * 70)
    print("TASK LOG SAVED:")
    print(log_path)


if __name__ == "__main__":
    main()
