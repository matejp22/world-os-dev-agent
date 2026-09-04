from __future__ import annotations

from app.output_sanitizer import sanitize_output


tests = [
    ".env",
    ".env.example",
    "OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz123456",
    "PASSWORD=my-secret-password",
    "TOKEN=abc123xyz",
    "normal harmless output",
]


for raw in tests:
    print("=" * 70)
    print("RAW:")
    print(raw)
    print()
    print("SANITIZED:")
    print(sanitize_output(raw))
    print()
