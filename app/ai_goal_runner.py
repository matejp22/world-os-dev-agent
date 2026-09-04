from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from app.ai_planner import create_plan, MODEL
from app.ai_reviewer import review_run
from app.output_sanitizer import sanitize_output
from app.safe_executor import execute_safe


DEFAULT_REPO = r"C:\Users\matej\Documents\world-os-research-engine"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"


def parse_commands(raw_plan: str) -> list[str]:
    commands: list[str] = []

    for line in raw_plan.splitlines():
        command = line.strip()

        if not command:
            continue

        if command.lower().startswith("set-location"):
            continue

        commands.append(command)

    return commands[:5]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WORLD OS DEV AGENT AI goal runner"
    )

    parser.add_argument(
        "--goal",
        required=True,
        help="High-level development goal",
    )

    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help="Working repository path",
    )

    args = parser.parse_args()

    raw_plan = create_plan(args.goal)
    commands = parse_commands(raw_plan)

    raw_lines: list[str] = [
        "=" * 70,
        "WORLD OS DEV AGENT - AI RUN",
        "=" * 70,
        "",
        "MODEL:",
        MODEL,
        "",
        "USER GOAL:",
        args.goal,
        "",
        "AI PROPOSED COMMANDS:",
    ]

    safe_lines: list[str] = list(raw_lines)

    if not commands:
        raw_lines.append("<none>")
        safe_lines.append("<none>")

    for index, command in enumerate(commands, start=1):
        raw_lines.append(f"{index}. {command}")
        safe_lines.append(f"{index}. {command}")

    for command in commands:
        execution = execute_safe(
            command=command,
            cwd=args.repo,
        )

        common = [
            "",
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

        raw_lines.extend(common)
        safe_lines.extend(common)

        if execution.result is not None:
            raw_stdout = execution.result.stdout or "<empty>"
            raw_stderr = execution.result.stderr or "<empty>"

            safe_stdout = sanitize_output(raw_stdout)
            safe_stderr = sanitize_output(raw_stderr)

            raw_lines.extend(
                [
                    "",
                    "EXIT CODE:",
                    str(execution.result.exit_code),
                    "",
                    "STDOUT:",
                    raw_stdout,
                    "",
                    "STDERR:",
                    raw_stderr,
                ]
            )

            safe_lines.extend(
                [
                    "",
                    "EXIT CODE:",
                    str(execution.result.exit_code),
                    "",
                    "STDOUT:",
                    safe_stdout,
                    "",
                    "STDERR:",
                    safe_stderr,
                ]
            )
        else:
            blocked = [
                "",
                "EXECUTION:",
                "BLOCKED BEFORE POWERSHELL",
            ]

            raw_lines.extend(blocked)
            safe_lines.extend(blocked)

    raw_report = "\n".join(raw_lines)
    safe_report = "\n".join(safe_lines)

    review = review_run(
        goal=args.goal,
        execution_report=safe_report,
    )

    final_safe_report = (
        safe_report
        + "\n\n"
        + "=" * 70
        + "\nAI REVIEW:\n"
        + review
    )

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    raw_log_path = LOG_DIR / f"raw_run_{timestamp}.txt"
    safe_log_path = LOG_DIR / f"safe_reviewed_run_{timestamp}.txt"

    raw_log_path.write_text(
        raw_report,
        encoding="utf-8",
    )

    safe_log_path.write_text(
        final_safe_report,
        encoding="utf-8",
    )

    print(final_safe_report)
    print()
    print("=" * 70)
    print("SAFE REVIEWED LOG SAVED:")
    print(safe_log_path)


if __name__ == "__main__":
    main()
