from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from app.ai_controller import decide_next_step
from app.ai_planner import create_plan, MODEL
from app.ai_reviewer import review_run
from app.output_sanitizer import sanitize_output
from app.safe_executor import execute_safe


DEFAULT_REPO = r"C:\Users\matej\Documents\world-os-research-engine"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"

MAX_ROUNDS = 3


def configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)

        if reconfigure is not None:
            reconfigure(
                encoding="utf-8",
                errors="replace",
            )


def parse_commands(raw_plan: str) -> list[str]:
    commands: list[str] = []

    for line in raw_plan.splitlines():
        command = line.strip()

        if not command:
            continue

        if command.lower() == "no_commands_required":
            continue

        if command.lower().startswith("set-location"):
            continue

        commands.append(command)

    return commands[:5]


def execute_round(
    goal: str,
    repo_path: str,
    round_number: int,
) -> tuple[str, str]:
    raw_plan = create_plan(goal)
    commands = parse_commands(raw_plan)

    lines: list[str] = [
        "=" * 70,
        f"ROUND {round_number}",
        "=" * 70,
        "",
        "GOAL:",
        goal,
        "",
        "AI PROPOSED COMMANDS:",
    ]

    if not commands:
        lines.append("<none>")

    for index, command in enumerate(commands, start=1):
        lines.append(f"{index}. {command}")

    for command in commands:
        execution = execute_safe(
            command=command,
            cwd=repo_path,
        )

        lines.extend(
            [
                "",
                "-" * 70,
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
            safe_stdout = sanitize_output(
                execution.result.stdout or "<empty>"
            )

            safe_stderr = sanitize_output(
                execution.result.stderr or "<empty>"
            )

            lines.extend(
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
            lines.extend(
                [
                    "",
                    "EXECUTION:",
                    "BLOCKED BEFORE POWERSHELL",
                ]
            )

    report = "\n".join(lines)

    review = review_run(
        goal=goal,
        execution_report=report,
    )

    return report, review


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WORLD OS DEV AGENT autonomous read-only loop"
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

    original_goal = args.goal
    current_goal = original_goal

    session_lines: list[str] = [
        "=" * 70,
        "WORLD OS DEV AGENT - AUTONOMOUS READ-ONLY SESSION",
        "=" * 70,
        "",
        "MODEL:",
        MODEL,
        "",
        "ORIGINAL GOAL:",
        original_goal,
        "",
        f"MAX ROUNDS: {MAX_ROUNDS}",
    ]

    for round_number in range(1, MAX_ROUNDS + 1):
        report, review = execute_round(
            goal=current_goal,
            repo_path=args.repo,
            round_number=round_number,
        )

        session_lines.extend(
            [
                "",
                report,
                "",
                "AI REVIEW:",
                review,
            ]
        )

        if round_number >= MAX_ROUNDS:
            session_lines.extend(
                [
                    "",
                    "CONTROLLER:",
                    "STOP - maximum round limit reached.",
                ]
            )
            break

        decision = decide_next_step(
            original_goal=original_goal,
            execution_report=report,
            review=review,
        )

        session_lines.extend(
            [
                "",
                "CONTROLLER:",
                decision,
            ]
        )

        if decision.strip() == "STOP":
            break

        prefix = "NEXT_GOAL:"

        if not decision.startswith(prefix):
            session_lines.extend(
                [
                    "",
                    "CONTROLLER SAFETY STOP:",
                    "Invalid controller response format.",
                ]
            )
            break

        next_goal = decision[len(prefix):].strip()

        if not next_goal:
            session_lines.extend(
                [
                    "",
                    "CONTROLLER SAFETY STOP:",
                    "Empty next goal.",
                ]
            )
            break

        current_goal = next_goal

    final_report = "\n".join(session_lines)

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"autonomous_readonly_{timestamp}.txt"

    log_path.write_text(
        final_report,
        encoding="utf-8",
    )

    configure_utf8_output()

    print(final_report)
    print()
    print("=" * 70)
    print("AUTONOMOUS SESSION LOG SAVED:")
    print(log_path)


if __name__ == "__main__":
    main()