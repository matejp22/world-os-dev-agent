from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import app.build_patch_orchestrator as orchestrator


FOCUSED_TARGET_MODULES = (
    "app.build_patch_orchestrator",
    "app.ai_full_file_revision",
)


def _result(
    *,
    patch_id: str,
    candidate_sha256: str,
    decision: str,
    review: str,
    status: str,
):
    return SimpleNamespace(
        patch_id=patch_id,
        candidate_sha256=candidate_sha256,
        semantic_decision=decision,
        semantic_review=review,
        status=status,
    )


def test_autonomous_loop_repairs_until_green(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = [
        SimpleNamespace(
            result=_result(
                patch_id="p1",
                candidate_sha256="sha1",
                decision="COMPILE_FAILED",
                review="syntax error",
                status="DRAFT",
            ),
            candidate_text="broken",
            diff="diff1",
        ),
        SimpleNamespace(
            result=_result(
                patch_id="p2",
                candidate_sha256="sha2",
                decision="REVISE",
                review="REVISE\nneeds behavior fix",
                status="DRAFT",
            ),
            candidate_text="better",
            diff="diff2",
        ),
        SimpleNamespace(
            result=_result(
                patch_id="p3",
                candidate_sha256="sha3",
                decision="APPROVE_FOR_HUMAN_REVIEW",
                review="approved",
                status="READY_FOR_HUMAN_REVIEW",
            ),
            candidate_text="green",
            diff="diff3",
        ),
    ]

    monkeypatch.setattr(
        orchestrator,
        "_build_candidate_attempt",
        lambda **_kwargs: attempts.pop(0),
    )

    revisions = []

    def fake_revise_candidate(**kwargs):
        revisions.append(kwargs)
        return (
            "TARGET_FILE: app/example.py\n\n"
            "RATIONALE:\nrepair\n\n"
            "NEW_FILE_CONTENT:\nrepaired = True\n"
        )

    monkeypatch.setattr(
        orchestrator,
        "revise_candidate",
        fake_revise_candidate,
    )

    result = orchestrator._run_autonomous_candidate_revision_loop(
        clean_goal="repair until green",
        canonical_workspace_name="world-os-dev-agent",
        target_file="app/example.py",
        target_path=tmp_path / "example.py",
        target_exists=True,
        format_version="FULL_FILE_V2",
        initial_content="broken",
    )

    assert result.status == "READY_FOR_HUMAN_REVIEW"
    assert result.patch_id == "p3"
    assert len(revisions) == 2


def test_companion_patch_uses_autonomous_revision_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    test_target = workspace / "tests" / "test_example.py"
    test_target.parent.mkdir(parents=True)

    monkeypatch.setattr(
        orchestrator,
        "get_workspace_profile",
        lambda _: SimpleNamespace(
            name="world-os-research-engine",
            path=workspace,
        ),
    )

    monkeypatch.setattr(
        orchestrator,
        "generate_companion_test_candidate",
        lambda **_kwargs: (
            "TARGET_FILE: tests/test_example.py\n\n"
            "RATIONALE:\nfocused test\n\n"
            "NEW_FILE_CONTENT:\ndef test_example():\n"
            "    assert True\n"
        ),
    )

    monkeypatch.setattr(
        orchestrator,
        "resolve_workspace_python_target",
        lambda *_args, **_kwargs: test_target,
    )

    captured = {}

    def fake_loop(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            patch_id="green-test",
            status="READY_FOR_HUMAN_REVIEW",
        )

    monkeypatch.setattr(
        orchestrator,
        "_run_autonomous_candidate_revision_loop",
        fake_loop,
    )

    result = orchestrator._build_companion_test_patch(
        goal="implement example",
        workspace_name="world-os-research-engine",
        source_target_file="app/research/example.py",
        source_candidate_content="VALUE = 2\n",
        source_patch_id="source-patch",
    )

    assert result.status == "READY_FOR_HUMAN_REVIEW"
    assert captured["format_version"] == "NEW_FILE_V2"
    assert captured["initial_lineage"] == ["source-patch"]
    assert captured["initial_previous_patch_id"] == "source-patch"
    assert captured["allow_companion_generation"] is False


def test_autonomous_loop_stops_only_on_proven_stagnation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def same_attempt(**_kwargs):
        return SimpleNamespace(
            result=_result(
                patch_id="stagnant",
                candidate_sha256="same-sha",
                decision="REVISE",
                review="REVISE\nidentical failure",
                status="DRAFT",
            ),
            candidate_text="same content",
            diff="same diff",
        )

    monkeypatch.setattr(
        orchestrator,
        "_build_candidate_attempt",
        same_attempt,
    )

    monkeypatch.setattr(
        orchestrator,
        "revise_candidate",
        lambda **_kwargs: (
            "TARGET_FILE: app/example.py\n\n"
            "RATIONALE:\nretry\n\n"
            "NEW_FILE_CONTENT:\nsame content\n"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="AUTONOMOUS_HARD_BLOCKER",
    ):
        orchestrator._run_autonomous_candidate_revision_loop(
            clean_goal="repair",
            canonical_workspace_name="world-os-dev-agent",
            target_file="app/example.py",
            target_path=tmp_path / "example.py",
            target_exists=True,
            format_version="FULL_FILE_V2",
            initial_content="same content",
        )
