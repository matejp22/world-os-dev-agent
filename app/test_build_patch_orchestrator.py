from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import app.build_patch_orchestrator as orchestrator


FOCUSED_TARGET_MODULES = (
    "app.build_patch_orchestrator",
)


def _install_isolated_environment(
    monkeypatch,
    tmp_path: Path,
    patch_ids: list[str],
) -> Path:
    temp_dir = tmp_path / "temp"
    queue_dir = tmp_path / "pending_patches"
    workspace_dir = tmp_path / "workspace"

    temp_dir.mkdir()
    queue_dir.mkdir()
    workspace_dir.mkdir()

    target_path = workspace_dir / "example.py"
    target_path.write_text(
        "VALUE = 0\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        orchestrator,
        "TEMP_DIR",
        temp_dir,
    )
    monkeypatch.setattr(
        orchestrator,
        "QUEUE_DIR",
        queue_dir,
    )
    monkeypatch.setattr(
        orchestrator,
        "get_workspace_profile",
        lambda workspace_name: SimpleNamespace(
            name=workspace_name,
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "resolve_workspace_python_target",
        lambda *args, **kwargs: target_path,
    )

    ids = iter(patch_ids)

    monkeypatch.setattr(
        orchestrator,
        "uuid4",
        lambda: next(ids),
    )

    return target_path


def test_revise_creates_fresh_patch_and_propagates_revised_content(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _install_isolated_environment(
        monkeypatch,
        tmp_path,
        ["patch-1", "patch-2"],
    )

    monkeypatch.setattr(
        orchestrator,
        "generate_candidate",
        lambda goal, workspace_name: "RAW",
    )
    monkeypatch.setattr(
        orchestrator,
        "parse_candidate",
        lambda raw: (
            "example.py",
            "VALUE = 1\n",
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "compile_candidate",
        lambda candidate_file: (
            True,
            "",
        ),
    )

    reviewed_diffs: list[str] = []

    def review_candidate(
        *,
        goal: str,
        target_file: str,
        diff: str,
    ) -> str:
        reviewed_diffs.append(diff)

        if len(reviewed_diffs) == 1:
            return (
                "REVISE\n"
                "REASON: use VALUE = 2"
            )

        return (
            "APPROVE_FOR_HUMAN_REVIEW\n"
            "REASON: revised candidate is correct"
        )

    monkeypatch.setattr(
        orchestrator,
        "review_full_file_candidate",
        review_candidate,
    )
    monkeypatch.setattr(
        orchestrator,
        "revise_candidate",
        lambda **kwargs: "REVISION",
    )
    monkeypatch.setattr(
        orchestrator,
        "_parse_revised_content",
        lambda revised, target_file: (
            "VALUE = 2\n"
        ),
    )

    result = orchestrator.run_build_patch(
        "change the value",
        "world-os-dev-agent",
    )

    assert result.patch_id == "patch-2"
    assert result.status == "READY_FOR_HUMAN_REVIEW"
    assert result.semantic_decision == "APPROVE_FOR_HUMAN_REVIEW"
    assert result.revision_round == 1

    assert result.supersedes_patch_id == "patch-1"
    assert result.superseded_patch_ids == [
        "patch-1",
    ]

    assert len(reviewed_diffs) == 2
    assert "VALUE = 1" in reviewed_diffs[0]
    assert "VALUE = 2" in reviewed_diffs[1]

    first_record = json.loads(
        (
            orchestrator.QUEUE_DIR
            / "patch-1.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    second_record = json.loads(
        (
            orchestrator.QUEUE_DIR
            / "patch-2.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert first_record["status"] == "DRAFT"
    assert first_record["semantic_decision"] == "REVISE"
    assert first_record["supersedes_patch_id"] is None

    assert second_record["status"] == "READY_FOR_HUMAN_REVIEW"
    assert second_record["supersedes_patch_id"] == "patch-1"
    assert second_record["superseded_patch_ids"] == [
        "patch-1",
    ]

    assert (
        Path(second_record["candidate_file"])
        .read_text(encoding="utf-8")
        == "VALUE = 2\n"
    )


def test_compile_failure_repairs_without_semantic_reject(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _install_isolated_environment(
        monkeypatch,
        tmp_path,
        ["compile-1", "compile-2"],
    )

    monkeypatch.setattr(
        orchestrator,
        "generate_candidate",
        lambda goal, workspace_name: "RAW",
    )
    monkeypatch.setattr(
        orchestrator,
        "parse_candidate",
        lambda raw: (
            "example.py",
            "BROKEN =\n",
        ),
    )

    compile_calls = 0

    def compile_candidate(candidate_file: Path):
        nonlocal compile_calls
        compile_calls += 1

        if compile_calls == 1:
            return (
                False,
                "SyntaxError: invalid syntax",
            )

        return (
            True,
            "",
        )

    monkeypatch.setattr(
        orchestrator,
        "compile_candidate",
        compile_candidate,
    )
    monkeypatch.setattr(
        orchestrator,
        "revise_candidate",
        lambda **kwargs: "REVISION",
    )
    monkeypatch.setattr(
        orchestrator,
        "_parse_revised_content",
        lambda revised, target_file: (
            "BROKEN = 1\n"
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "review_full_file_candidate",
        lambda **kwargs: (
            "APPROVE_FOR_HUMAN_REVIEW\n"
            "REASON: compile repair is valid"
        ),
    )

    result = orchestrator.run_build_patch(
        "repair candidate",
        "world-os-dev-agent",
    )

    assert result.patch_id == "compile-2"
    assert result.status == "READY_FOR_HUMAN_REVIEW"
    assert result.semantic_decision == "APPROVE_FOR_HUMAN_REVIEW"
    assert result.compile_passed is True

    first_record = json.loads(
        (
            orchestrator.QUEUE_DIR
            / "compile-1.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert first_record["semantic_decision"] == "COMPILE_FAILED"
    assert first_record["status"] == "DRAFT"
    assert first_record["compile_passed"] is False

    assert first_record["semantic_decision"] != "REJECT"


def test_revision_limit_returns_actual_last_candidate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _install_isolated_environment(
        monkeypatch,
        tmp_path,
        ["limit-1", "limit-2"],
    )

    monkeypatch.setattr(
        orchestrator,
        "MAX_REVISIONS",
        1,
    )
    monkeypatch.setattr(
        orchestrator,
        "generate_candidate",
        lambda goal, workspace_name: "RAW",
    )
    monkeypatch.setattr(
        orchestrator,
        "parse_candidate",
        lambda raw: (
            "example.py",
            "VALUE = 1\n",
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "compile_candidate",
        lambda candidate_file: (
            True,
            "",
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "review_full_file_candidate",
        lambda **kwargs: (
            "REVISE\n"
            "REASON: revise again"
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "revise_candidate",
        lambda **kwargs: "REVISION",
    )
    monkeypatch.setattr(
        orchestrator,
        "_parse_revised_content",
        lambda revised, target_file: (
            "VALUE = 2\n"
        ),
    )

    result = orchestrator.run_build_patch(
        "force revision limit",
        "world-os-dev-agent",
    )

    assert result.patch_id == "limit-2"
    assert result.revision_round == 1
    assert result.status == "REVISION_LIMIT_REACHED"
    assert result.semantic_decision == "REVISE"

    assert result.supersedes_patch_id == "limit-1"
    assert result.superseded_patch_ids == [
        "limit-1",
    ]

    assert (
        Path(result.candidate_file)
        .read_text(encoding="utf-8")
        == "VALUE = 2\n"
    )

    final_record = json.loads(
        (
            orchestrator.QUEUE_DIR
            / "limit-2.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert final_record["patch_id"] == result.patch_id
    assert final_record["candidate_sha256"] == result.candidate_sha256
    assert final_record["candidate_file"] == result.candidate_file
    assert final_record["diff_file"] == result.diff_file
    assert final_record["revision_round"] == result.revision_round
    assert final_record["status"] == result.status
    assert final_record["superseded_patch_ids"] == [
        "limit-1",
    ]
