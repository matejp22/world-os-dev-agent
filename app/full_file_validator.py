from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.ai_file_candidate import generate_candidate
from app.deterministic_diff import build_unified_diff


ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = (ROOT / "app").resolve()
TEMP_DIR = ROOT / "temp"


GOAL = (
    "Improve the Dev Agent patch workflow so that AI proposes "
    "complete file contents while Python generates review diffs "
    "deterministically and applies approved full-file candidates safely."
)


@dataclass
class CandidateValidation:
    target_file: str
    original_sha256: str
    candidate_sha256: str
    temp_file: Path
    diff_file: Path
    compile_passed: bool


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
    target_file = extract_section(
        candidate,
        "TARGET_FILE:",
        "RATIONALE:",
    ).replace("\\", "/")

    new_content = extract_section(
        candidate,
        "NEW_FILE_CONTENT:",
    )

    if not target_file:
        raise RuntimeError(
            "Target file is empty."
        )

    target_path = Path(target_file)

    if target_path.is_absolute():
        raise RuntimeError(
            "Target must be workspace-relative."
        )

    parts = tuple(
        part
        for part in target_file.split("/")
        if part
    )

    if not parts or any(
        part in {".", ".."}
        for part in parts
    ):
        raise RuntimeError(
            "Target path may not contain traversal segments."
        )

    if not target_file.endswith(".py"):
        raise RuntimeError(
            "Target must be a Python file."
        )

    is_app_target = target_file.startswith(
        "app/"
    )

    is_existing_test_script = (
        len(parts) == 2
        and parts[0] == "scripts"
        and parts[1].startswith("test_")
        and parts[1].endswith(".py")
    )

    if not is_app_target and not is_existing_test_script:
        raise RuntimeError(
            "Target must be inside app/ or a top-level "
            "scripts/test_*.py file."
        )

    return target_file, new_content


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(
        data
    ).hexdigest()


def detect_newline(raw: bytes) -> str:
    if b"\r\n" in raw:
        return "\r\n"

    return "\n"


def prepare_candidate() -> CandidateValidation:
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
            ROOT
        )
    except ValueError as exc:
        raise RuntimeError(
            "Target escapes workspace."
        ) from exc

    is_app_target = target_file.startswith(
        "app/"
    )

    is_existing_test_script = (
        target_file.startswith("scripts/test_")
        and target_file.endswith(".py")
        and target_file.count("/") == 1
    )

    if is_app_target:
        try:
            target_path.relative_to(
                APP_ROOT
            )
        except ValueError as exc:
            raise RuntimeError(
                "Target escapes app directory."
            ) from exc
    elif not is_existing_test_script:
        raise RuntimeError(
            "Target is outside the permitted FULL_FILE_V2 scope."
        )

    if not target_path.exists():
        raise RuntimeError(
            "Target file does not exist."
        )

    if not target_path.is_file():
        raise RuntimeError(
            "Target path is not a regular file."
        )

    original_bytes = target_path.read_bytes()

    original_sha256 = sha256_bytes(
        original_bytes
    )

    has_bom = original_bytes.startswith(
        b"\xef\xbb\xbf"
    )

    newline = detect_newline(
        original_bytes
    )

    old_text = original_bytes.decode(
        "utf-8-sig"
    )

    clean_new_content = new_content.lstrip(
        "\ufeff"
    )

    clean_new_content = (
        clean_new_content
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    clean_new_content = clean_new_content.replace(
        "\n",
        newline,
    )

    candidate_bytes = clean_new_content.encode(
        "utf-8"
    )

    if has_bom:
        candidate_bytes = (
            b"\xef\xbb\xbf"
            + candidate_bytes
        )

    candidate_sha256 = sha256_bytes(
        candidate_bytes
    )

    if candidate_sha256 == original_sha256:
        raise RuntimeError(
            "Candidate contains no changes."
        )

    TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_file = (
        TEMP_DIR
        / "validated_candidate.py"
    )

    temp_file.write_bytes(
        candidate_bytes
    )

    compile_result = subprocess.run(
        [
            "python",
            "-m",
            "py_compile",
            str(temp_file),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    compile_passed = (
        compile_result.returncode == 0
    )

    if not compile_passed:
        raise RuntimeError(
            "Candidate py_compile failed:\n"
            + (
                compile_result.stderr
                or compile_result.stdout
            )
        )

    candidate_text_for_diff = candidate_bytes.decode(
        "utf-8-sig"
    )

    diff = build_unified_diff(
        target_file=target_file,
        old_content=old_text,
        new_content=candidate_text_for_diff,
    )

    diff_file = (
        TEMP_DIR
        / "validated_candidate.diff"
    )

    diff_file.write_text(
        diff,
        encoding="utf-8",
    )

    return CandidateValidation(
        target_file=target_file,
        original_sha256=original_sha256,
        candidate_sha256=candidate_sha256,
        temp_file=temp_file,
        diff_file=diff_file,
        compile_passed=compile_passed,
    )


if __name__ == "__main__":
    result = prepare_candidate()

    print("=" * 70)
    print("WORLD OS DEV AGENT - FULL FILE VALIDATION")
    print("=" * 70)
    print()

    print("TARGET FILE:")
    print(result.target_file)
    print()

    print("ORIGINAL SHA256:")
    print(result.original_sha256)
    print()

    print("CANDIDATE SHA256:")
    print(result.candidate_sha256)
    print()

    print("PY_COMPILE:")
    print(
        "PASS"
        if result.compile_passed
        else "FAIL"
    )
    print()

    print("TEMP CANDIDATE:")
    print(result.temp_file)
    print()

    print("REVIEW DIFF:")
    print(result.diff_file)
    print()

    print("ORIGINAL FILE MODIFIED:")
    print("False")