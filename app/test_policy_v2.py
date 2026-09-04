from __future__ import annotations

from app.command_policy import evaluate_command


tests = [
    "git status --short",
    "git ls-files --others --exclude-standard",
    "Get-Content .\\scripts\\cleanup_port_core_v2_port_metrics_canary.py",
    "Get-Content .\\.env",
    "Get-Content .\\supabase\\.temp\\pooler-url",
    "Get-ChildItem -Recurse -File",
    "git push origin main",
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
