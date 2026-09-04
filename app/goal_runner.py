from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from app.safe_executor import execute_safe
from app.task_planner import plan_task


DEFAULT_REPO = r"C:\Users\matej\Documents\world-os-research-engine"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WORLD OS DEV AGENT goal runner"
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

    plan = plan_task(args.goal)

    lines: list[str] = [
        "=" * 70,
        "WORLD OS DEV AGENT",
        "=" * 70,
        "",
        "USER GOAL:",
        plan.goal,
        "",
        "PLANNER:",
        plan.explanation,
        "",
        "PROPOSED COMMANDS:",
    ]

    if not plan.commands:
        lines.append("<none>")
    else:
        for index, command in enumerate(plan.commands, start=1):
            lines.append(f"{index}. {command}")

    for command in plan.commands:
        execution = execute_safe(
            command=command,
            cwd=args.repo,
        )

        lines.extend(
            [
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
        )

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

    report = "\n".join(lines)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"goal_{timestamp}.txt"
    log_path.write_text(report, encoding="utf-8")

    print(report)
    print()
    print("=" * 70)
    print("GOAL LOG SAVED:")
    print(log_path)


if __name__ == "__main__":
    main()
