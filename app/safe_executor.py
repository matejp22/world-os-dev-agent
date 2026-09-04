from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.command_policy import evaluate_command
from app.powershell_executor import CommandResult, run_powershell


@dataclass
class SafeExecutionResult:
    allowed: bool
    policy_reason: str
    result: CommandResult | None


def execute_safe(
    command: str,
    cwd: str | Path | None = None,
) -> SafeExecutionResult:
    decision = evaluate_command(command)

    if not decision.allowed:
        return SafeExecutionResult(
            allowed=False,
            policy_reason=decision.reason,
            result=None,
        )

    result = run_powershell(
        command=command,
        cwd=cwd,
    )

    return SafeExecutionResult(
        allowed=True,
        policy_reason=decision.reason,
        result=result,
    )
