from __future__ import annotations

import re


MAX_OUTPUT_CHARS = 12000


SENSITIVE_FILENAMES = (
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
)


SECRET_PATTERNS = (
    re.compile(
        r"(?i)\b(sk-(?:proj-)?[A-Za-z0-9_-]{16,})\b"
    ),
    re.compile(
        r"(?i)\b([A-Z0-9_]*(?:API_KEY|TOKEN|PASSWORD|SECRET|PRIVATE_KEY))"
        r"\s*=\s*([^\s]+)"
    ),
)


def sanitize_output(text: str) -> str:
    if not text:
        return text

    sanitized_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip().lower()

        if stripped in SENSITIVE_FILENAMES:
            sanitized_lines.append("<sensitive-file-hidden>")
            continue

        safe_line = line

        for pattern in SECRET_PATTERNS:
            if "api_key" in pattern.pattern.lower():
                safe_line = pattern.sub(
                    lambda match: f"{match.group(1)}=<redacted>",
                    safe_line,
                )
            else:
                safe_line = pattern.sub("<redacted-secret>", safe_line)

        sanitized_lines.append(safe_line)

    sanitized = "\n".join(sanitized_lines)

    if len(sanitized) > MAX_OUTPUT_CHARS:
        sanitized = (
            sanitized[:MAX_OUTPUT_CHARS]
            + "\n<output-truncated>"
        )

    return sanitized
