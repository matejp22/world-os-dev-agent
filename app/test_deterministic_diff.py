from __future__ import annotations

from app.deterministic_diff import build_unified_diff


OLD = """from __future__ import annotations

VALUE = 1

def example() -> int:
    return VALUE
"""

NEW = """from __future__ import annotations

VALUE = 2

def example() -> int:
    return VALUE
"""


diff = build_unified_diff(
    target_file="app/example.py",
    old_content=OLD,
    new_content=NEW,
)

print("=" * 70)
print("DETERMINISTIC DIFF")
print("=" * 70)
print(diff)
