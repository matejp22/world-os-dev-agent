from __future__ import annotations

import difflib


def build_unified_diff(
    target_file: str,
    old_content: str,
    new_content: str,
) -> str:
    normalized_target = target_file.replace("\\", "/")

    old_lines = old_content.splitlines(
        keepends=True
    )

    new_lines = new_content.splitlines(
        keepends=True
    )

    diff_lines = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{normalized_target}",
        tofile=f"b/{normalized_target}",
        lineterm="",
    )

    return "\n".join(diff_lines)
