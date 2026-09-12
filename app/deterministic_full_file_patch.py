from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from uuid import uuid4

from app.ai_full_file_reviewer import review_full_file_candidate
from app.build_patch_orchestrator import (
    BuildPatchResult,
    QUEUE_DIR,
    TEMP_DIR,
    compile_candidate,
    normalize_candidate,
    semantic_decision,
    status_for_decision,
)
from app.deterministic_diff import build_unified_diff
from app.full_file_validator import sha256_bytes
from app.workspace_registry import (
    get_workspace_profile,
    require_verified_patch_workspace,
    resolve_workspace_python_target,
)


def build_deterministic_full_file_patch(
    *,
    workspace_name: str,
    target_file: str,
    goal: str,
    new_content: str,
) -> BuildPatchResult:
    if not isinstance(workspace_name, str):
        raise ValueError("workspace_name must be a string.")
    if not workspace_name.strip():
        raise ValueError("workspace_name must not be empty.")

    if not isinstance(target_file, str):
        raise ValueError("target_file must be a string.")
    if not target_file.strip():
        raise ValueError("target_file must not be empty.")

    if not isinstance(goal, str):
        raise ValueError("goal must be a string.")
    if not goal.strip():
        raise ValueError("goal must not be empty.")

    if not isinstance(new_content, str):
        raise ValueError("new_content must be a string.")
    if not new_content:
        raise ValueError("new_content must not be empty.")

    workspace = get_workspace_profile(workspace_name)
    require_verified_patch_workspace(workspace.name)

    target_path = resolve_workspace_python_target(
        workspace.name,
        target_file,
        must_exist=True,
        allow_existing_test_script=True,
    )

    canonical_target_file = target_path.relative_to(
        workspace.path.resolve()
    ).as_posix()
    clean_goal = goal.strip()

    original_bytes, candidate_bytes = normalize_candidate(
        target_path=target_path,
        new_content=new_content,
    )

    original_sha256 = sha256_bytes(original_bytes)
    candidate_sha256 = sha256_bytes(candidate_bytes)

    if candidate_sha256 == original_sha256:
        raise RuntimeError("Candidate contains no changes.")

    diff = build_unified_diff(
        target_file=canonical_target_file,
        old_content=original_bytes.decode("utf-8-sig"),
        new_content=candidate_bytes.decode("utf-8-sig"),
    )

    patch_id = str(uuid4())

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    candidate_file = TEMP_DIR / f"{patch_id}.candidate.py"
    diff_file = TEMP_DIR / f"{patch_id}.diff"
    queue_file = QUEUE_DIR / f"{patch_id}.json"

    artifact_paths = (
        candidate_file,
        diff_file,
        queue_file,
    )

    if any(path.exists() for path in artifact_paths):
        raise RuntimeError("One or more patch artifact paths already exist.")

    candidate_file.write_bytes(candidate_bytes)
    diff_file.write_text(diff, encoding="utf-8")

    compile_result = compile_candidate(candidate_file)
    if (
        not isinstance(compile_result, tuple)
        or len(compile_result) != 2
        or not isinstance(compile_result[0], bool)
    ):
        raise RuntimeError("Unexpected compile_candidate result.")

    compile_passed, compile_output = compile_result

    if not compile_passed:
        raise RuntimeError(
            "Candidate py_compile failed:\n"
            + str(compile_output)
        )

    semantic_review = review_full_file_candidate(
        goal=clean_goal,
        target_file=canonical_target_file,
        diff=diff,
    )

    decision = semantic_decision(semantic_review)
    status = status_for_decision(decision)

    result = BuildPatchResult(
        patch_id=patch_id,
        goal=clean_goal,
        workspace_name=workspace.name,
        target_file=canonical_target_file,
        original_sha256=original_sha256,
        candidate_sha256=candidate_sha256,
        candidate_file=str(candidate_file),
        diff_file=str(diff_file),
        compile_passed=True,
        semantic_decision=decision,
        semantic_review=semantic_review,
        revision_round=0,
        status=status,
        format_version="FULL_FILE_V2",
    )

    queue_payload = asdict(result)
    queue_payload["created_at"] = datetime.now(
        timezone.utc
    ).isoformat()

    if queue_file.exists():
        raise RuntimeError("Queue artifact already exists.")

    queue_file.write_text(
        json.dumps(
            queue_payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return result