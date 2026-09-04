from __future__ import annotations

from app.command_policy import evaluate_command


tests = [
    "git status --short",
    "git log -1 --oneline",
    "git diff --check",
    "Get-ChildItem -Recurse",
    "git push origin main",
    "Remove-Item .\\important.py",
    "supabase db push",
    "git commit -m test",
]


for command in tests:
    decision = evaluate_command(command)

    print("=" * 70)
    print("COMMAND:")
    print(command)
    print()
    print("ALLOWED:")
    print(decision.allowed)
    print()
    print("REASON:")
    print(decision.reason)
    print()
