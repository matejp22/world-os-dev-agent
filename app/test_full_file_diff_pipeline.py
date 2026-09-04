from __future__ import annotations

import difflib
import subprocess
from pathlib import Path

from app.ai_file_candidate import generate_candidate


ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = (ROOT / "app").resolve()
TEMP_DIR = ROOT / "temp"


GOAL = (
    "Improve the Dev Agent patch workflow so that AI proposes "
    "complete file contents while Python generates unified diffs "
    "deterministically."
)


def extract_section(
    candidate: str,
    marker: str,
    next_marker: str | None = None,
) -> str:
    if marker not in candidate:
        raise RuntimeError(
            f"Missing marker: {marker}"
        )

    section = candidate.split(
        marker,
        1,
    )[1]

    if next_marker is not None:
        if next_marker not in section:
            raise RuntimeError(
                f"Missing marker: {next_marker}"
            )

        section = section.split(
            next_marker,
            1,
        )[0]

    return section.strip()


def parse_candidate(
    candidate: str,
) -> tuple[str, str]:
    target = extract_section(
        candidate,
        "TARGET_FILE:",
        "RATIONALE:",
    )

    new_content = extract_section(
        candidate,
        "NEW_FILE_CONTENT:",
    )

    target = target.replace(
        "\\",
        "/",
    )

    if not target.startswith("app/"):
        raise RuntimeError(
            "Target must be inside app/."
        )

    if not target.endswith(".py"):
        raise RuntimeError(
            "Target must be a Python file."
        )

    return target, new_content


def normalize_line_endings(
    text: str,
) -> str:
    return text.replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    )


candidate = generate_candidate(
    GOAL
)

target_file, new_content = parse_candidate(
    candidate
)

target_path = (
    ROOT / target_file
).resolve()

try:
    target_path.relative_to(
        APP_ROOT
    )
except ValueError as exc:
    raise RuntimeError(
        "Target escapes app directory."
    ) from exc

if not target_path.exists():
    raise RuntimeError(
        "Target file does not exist."
    )


old_content = target_path.read_text(
    encoding="utf-8",
)

old_has_bom = old_content.startswith(
    "\ufeff"
)

old_content = normalize_line_endings(
    old_content
)

new_content = normalize_line_endings(
    new_content
)

new_content = new_content.lstrip(
    "\ufeff"
)

if old_has_bom:
    new_content = "\ufeff" + new_content


if old_content == new_content:
    raise RuntimeError(
        "Candidate produced no file changes."
    )


old_lines = old_content.splitlines()
new_lines = new_content.splitlines()

diff_lines = difflib.unified_diff(
    old_lines,
    new_lines,
    fromfile=f"a/{target_file}",
    tofile=f"b/{target_file}",
    lineterm="",
)

diff = "\n".join(
    diff_lines
) + "\n"


TEMP_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

patch_path = (
    TEMP_DIR
    / "deterministic_candidate_bom_safe.patch"
)

patch_path.write_text(
    diff,
    encoding="utf-8",
)


print("=" * 70)
print("TARGET FILE")
print("=" * 70)
print(target_file)
print()

print("=" * 70)
print("SOURCE ENCODING")
print("=" * 70)
print("BOM PRESENT:")
print(old_has_bom)
print()

print("=" * 70)
print("DETERMINISTIC DIFF")
print("=" * 70)
print(diff)


check = subprocess.run(
    [
        "git",
        "apply",
        "--check",
        str(patch_path),
    ],
    cwd=ROOT,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)


print("=" * 70)
print("GIT APPLY CHECK")
print("=" * 70)
print("EXIT CODE:")
print(check.returncode)
print()

print("STDOUT:")
print(check.stdout.strip() or "<empty>")
print()

print("STDERR:")
print(check.stderr.strip() or "<empty>")
print()

print("PATCH FILE:")
print(patch_path)
print()

print("NO PATCH WAS APPLIED.")
