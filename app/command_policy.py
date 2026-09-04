from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str


ALLOWED_PREFIXES = (
    "git status",
    "git log",
    "git branch",
    "git diff",
    "git show",
    "git ls-files",
    "get-location",
    "get-childitem",
    "get-content",
    "select-string",
    "test-path",
    "python -m py_compile",
    "python .\\",
    "& \".\\.venv\\scripts\\python.exe\"",
)


BLOCKED_TOKENS = (
    "git push",
    "git commit",
    "git add",
    "remove-item",
    "del ",
    "erase ",
    "rm ",
    "set-content",
    "add-content",
    "new-item",
    "move-item",
    "copy-item",
    "rename-item",
    "supabase db push",
    "drop table",
    "delete from",
    "truncate ",
    "insert into",
    "update ",
    "alter table",
)


SENSITIVE_PATTERNS = (
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "supabase/.temp",
    "supabase\\.temp",
    "supabase\\.temp\\",
    "pooler-url",
    "project-ref",
    "linked-project.json",
    "credential",
    "credentials",
    "private_key",
    "private-key",
)


def evaluate_command(command: str) -> PolicyDecision:
    normalized = " ".join(command.strip().lower().split())

    for pattern in SENSITIVE_PATTERNS:
        if pattern in normalized:
            return PolicyDecision(
                allowed=False,
                reason=f"Sensitive path or secret pattern blocked: {pattern}",
            )

    for token in BLOCKED_TOKENS:
        if token in normalized:
            return PolicyDecision(
                allowed=False,
                reason=f"Blocked token detected: {token}",
            )

    if "get-childitem" in normalized and "-recurse" in normalized:
        return PolicyDecision(
            allowed=False,
            reason="Broad recursive filesystem crawl blocked in V0.1.",
        )

    for prefix in ALLOWED_PREFIXES:
        if normalized.startswith(prefix):
            return PolicyDecision(
                allowed=True,
                reason=f"Allowed read-only/test command: {prefix}",
            )

    return PolicyDecision(
        allowed=False,
        reason="Command is not on the V0.1 allowlist.",
    )
