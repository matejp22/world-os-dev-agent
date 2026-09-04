from __future__ import annotations

from app.safe_executor import execute_safe


REPO_PATH = r"C:\Users\matej\Documents\world-os-research-engine"


tests = [
    "git status --short",
    "git log -1 --oneline",
    "git push origin main",
    "Remove-Item .\\DO_NOT_DELETE.txt",
]


for command in tests:
    execution = execute_safe(
        command=command,
        cwd=REPO_PATH,
    )

    print("=" * 70)
    print("COMMAND:")
    print(command)
    print()
    print("POLICY ALLOWED:")
    print(execution.allowed)
    print()
    print("POLICY REASON:")
    print(execution.policy_reason)

    if execution.result is not None:
        print()
        print("EXIT CODE:")
        print(execution.result.exit_code)
        print()
        print("STDOUT:")
        print(execution.result.stdout or "<empty>")
        print()
        print("STDERR:")
        print(execution.result.stderr or "<empty>")

    else:
        print()
        print("EXECUTION:")
        print("BLOCKED BEFORE POWERSHELL")

    print()
