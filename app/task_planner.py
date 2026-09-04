from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlannedTask:
    goal: str
    commands: list[str]
    explanation: str


def plan_task(goal: str) -> PlannedTask:
    normalized = " ".join(goal.strip().lower().split())

    if (
        "current state" in normalized
        or "repo status" in normalized
        or "repository status" in normalized
        or "check repo" in normalized
    ):
        return PlannedTask(
            goal=goal,
            commands=[
                "git status --short",
                "git branch --show-current",
                "git log -1 --oneline",
                "git diff --check",
            ],
            explanation=(
                "Read-only repository health check: working tree, branch, "
                "latest commit, and diff validation."
            ),
        )

    if "recent commits" in normalized or "git history" in normalized:
        return PlannedTask(
            goal=goal,
            commands=[
                "git log -5 --oneline",
            ],
            explanation="Read-only inspection of the five most recent commits.",
        )

    return PlannedTask(
        goal=goal,
        commands=[],
        explanation=(
            "No deterministic V0.1 plan exists for this goal. "
            "No command will be executed."
        ),
    )
