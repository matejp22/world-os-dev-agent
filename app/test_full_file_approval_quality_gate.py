from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import app.full_file_approval as full_file_approval
from app.patch_quality_evidence_runner import PatchQualityExecutionResult


_PATCH_ID = "quality-gate-test"
_CONFIRMATION = full_file_approval.CONFIRM_PHRASE
_PASS_QUALITY_EVIDENCE = {
    "focused_tests_executed": True,
    "focused_tests_passed": True,
    "regression_tests_executed": True,
    "regression_tests_passed": True,
}


def _write_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    include_quality_evidence: bool = True,
) -> Path:
    queue_dir = (tmp_path / "pending_patches").resolve()
    queue_dir.mkdir()

    target_file = (tmp_path / "target.py").resolve()
    target_file.write_text("VALUE = 1\n", encoding="utf-8")

    candidate_file = (tmp_path / "candidate.py").resolve()
    candidate_file.write_text("VALUE = 2\n", encoding="utf-8")

    diff_file = (tmp_path / "candidate.diff").resolve()
    diff_file.write_text(
        "--- target.py\n+++ candidate.py\n@@\n-VALUE = 1\n+VALUE = 2\n",
        encoding="utf-8",
    )

    record: dict[str, Any] = {
        "patch_id": _PATCH_ID,
        "format_version": "FULL_FILE_V2",
        "status": "READY_FOR_HUMAN_REVIEW",
        "compile_passed": True,
        "semantic_review": {
            "decision": "APPROVE",
            "safe_for_human_approval": True,
        },
        "workspace_name": "world-os-dev-agent",
        "target_file": str(target_file),
        "original_sha256": full_file_approval.sha256_file(target_file),
        "candidate_sha256": full_file_approval.sha256_file(candidate_file),
        "candidate_file": str(candidate_file),
        "diff_file": str(diff_file),
    }

    if include_quality_evidence:
        record["quality_evidence"] = dict(_PASS_QUALITY_EVIDENCE)

    queue_file = queue_dir / f"{_PATCH_ID}.json"
    queue_file.write_text(
        json.dumps(record, sort_keys=True),
        encoding="utf-8",
    )

    monkeypatch.setattr(full_file_approval, "QUEUE_DIR", queue_dir)
    monkeypatch.setattr(
        full_file_approval,
        "resolve_workspace_python_target",
        lambda workspace_name, target_file, **kwargs: Path(target_file).resolve(),
    )

    return queue_file


def _quality_result(
    *,
    verdict: str,
    safe_for_human_approval: bool,
) -> SimpleNamespace:
    return SimpleNamespace(
        verdict=verdict,
        safe_for_human_approval=safe_for_human_approval,
    )


def _install_quality_result(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: object,
    calls: list[dict[str, object]],
) -> None:
    def evaluate_patch_record_quality(
        record: object,
        **kwargs: object,
    ) -> object:
        calls.append({"record": record, **kwargs})
        return result

    monkeypatch.setattr(
        full_file_approval,
        "evaluate_patch_record_quality",
        evaluate_patch_record_quality,
        raising=False,
    )


def _assert_quality_call(
    calls: list[dict[str, object]],
) -> None:
    assert len(calls) == 1
    captured_record = calls[0].get("record")
    assert isinstance(captured_record, dict)
    assert captured_record.get("patch_id") == _PATCH_ID


def _read_record(queue_file: Path) -> dict[str, Any]:
    record = json.loads(queue_file.read_text(encoding="utf-8"))
    assert isinstance(record, dict)
    return record


def _read_status(queue_file: Path) -> str:
    return str(_read_record(queue_file)["status"])


def _execution_result(
    *,
    workspace_name: str,
    target_file: str,
    focused_tests_executed: bool = True,
    focused_tests_passed: bool = True,
    regression_tests_executed: bool = True,
    regression_tests_passed: bool = True,
) -> PatchQualityExecutionResult:
    return PatchQualityExecutionResult(
        workspace_name=workspace_name,
        target_file=target_file,
        behavioral_source_change=True,
        focused_test_ids=("focused-test",),
        regression_test_ids=("regression-test",),
        focused_tests_executed=focused_tests_executed,
        focused_tests_passed=focused_tests_passed,
        regression_tests_executed=regression_tests_executed,
        regression_tests_passed=regression_tests_passed,
        execution_supported=True,
        reasons=(),
    )


def test_revise_quality_verdict_blocks_approval(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queue_file = _write_record(monkeypatch, tmp_path)
    calls: list[dict[str, object]] = []
    _install_quality_result(
        monkeypatch,
        result=(
            object(),
            _quality_result(
                verdict="REVISE",
                safe_for_human_approval=False,
            ),
        ),
        calls=calls,
    )

    with pytest.raises(RuntimeError):
        full_file_approval.approve_record(_PATCH_ID, _CONFIRMATION)

    assert _read_status(queue_file) == "READY_FOR_HUMAN_REVIEW"
    _assert_quality_call(calls)


def test_block_quality_verdict_blocks_approval(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queue_file = _write_record(monkeypatch, tmp_path)
    calls: list[dict[str, object]] = []
    _install_quality_result(
        monkeypatch,
        result=(
            object(),
            _quality_result(
                verdict="BLOCK",
                safe_for_human_approval=False,
            ),
        ),
        calls=calls,
    )

    with pytest.raises(RuntimeError):
        full_file_approval.approve_record(_PATCH_ID, _CONFIRMATION)

    assert _read_status(queue_file) == "READY_FOR_HUMAN_REVIEW"
    _assert_quality_call(calls)


def test_pass_quality_verdict_allows_approval(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queue_file = _write_record(monkeypatch, tmp_path)
    calls: list[dict[str, object]] = []
    _install_quality_result(
        monkeypatch,
        result=(
            object(),
            _quality_result(
                verdict="PASS",
                safe_for_human_approval=True,
            ),
        ),
        calls=calls,
    )

    _, data = full_file_approval.approve_record(_PATCH_ID, _CONFIRMATION)

    assert data["status"] == "APPROVED"
    assert _read_status(queue_file) == "APPROVED"
    _assert_quality_call(calls)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("original_sha256", "0" * 64),
        ("candidate_sha256", "0" * 64),
        ("candidate_file", "missing-candidate.py"),
        ("diff_file", "missing-candidate.diff"),
    ],
)
def test_pass_quality_verdict_does_not_bypass_integrity_checks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    queue_file = _write_record(monkeypatch, tmp_path)
    calls: list[dict[str, object]] = []
    _install_quality_result(
        monkeypatch,
        result=(
            object(),
            _quality_result(
                verdict="PASS",
                safe_for_human_approval=True,
            ),
        ),
        calls=calls,
    )

    record = _read_record(queue_file)
    record[field] = value
    queue_file.write_text(
        json.dumps(record, sort_keys=True),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError):
        full_file_approval.approve_record(_PATCH_ID, _CONFIRMATION)

    assert _read_status(queue_file) == "READY_FOR_HUMAN_REVIEW"
    _assert_quality_call(calls)


def test_malformed_quality_evaluation_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queue_file = _write_record(monkeypatch, tmp_path)
    calls: list[dict[str, object]] = []
    _install_quality_result(
        monkeypatch,
        result={"unexpected": "shape"},
        calls=calls,
    )

    with pytest.raises(RuntimeError):
        full_file_approval.approve_record(_PATCH_ID, _CONFIRMATION)

    assert _read_status(queue_file) == "READY_FOR_HUMAN_REVIEW"
    _assert_quality_call(calls)


def test_failed_quality_evaluation_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queue_file = _write_record(monkeypatch, tmp_path)

    calls: list[dict[str, object]] = []

    def fail_quality_evaluation(
        record: object,
        **kwargs: object,
    ) -> object:
        calls.append({"record": record, **kwargs})
        raise RuntimeError("quality evaluation failed")

    monkeypatch.setattr(
        full_file_approval,
        "evaluate_patch_record_quality",
        fail_quality_evaluation,
        raising=False,
    )

    with pytest.raises(RuntimeError):
        full_file_approval.approve_record(_PATCH_ID, _CONFIRMATION)

    assert _read_status(queue_file) == "READY_FOR_HUMAN_REVIEW"
    _assert_quality_call(calls)


def test_missing_quality_evidence_runs_and_persists_before_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queue_file = _write_record(
        monkeypatch,
        tmp_path,
        include_quality_evidence=False,
    )
    record = _read_record(queue_file)
    workspace_name = record["workspace_name"]
    target_file = record["target_file"]
    candidate_file = record["candidate_file"]

    runner_calls: list[dict[str, object]] = []
    persistence_calls: list[dict[str, object]] = []
    gate_calls: list[dict[str, object]] = []

    result = _execution_result(
        workspace_name=workspace_name,
        target_file=target_file,
    )

    def run_patch_quality_evidence(
        *,
        workspace_name: str,
        target_file: str,
        candidate_target_file: str,
        candidate_file: object,
    ) -> PatchQualityExecutionResult:
        runner_calls.append(
            {
                "workspace_name": workspace_name,
                "target_file": target_file,
                "candidate_target_file": candidate_target_file,
                "candidate_file": candidate_file,
            }
        )
        return result

    def persist_patch_quality_evidence(
        *,
        patch_id: str,
        result: PatchQualityExecutionResult,
    ) -> tuple[Path, dict[str, Any]]:
        persistence_calls.append(
            {
                "patch_id": patch_id,
                "result": result,
            }
        )
        updated_record = _read_record(queue_file)
        updated_record["quality_evidence"] = dict(_PASS_QUALITY_EVIDENCE)
        queue_file.write_text(
            json.dumps(updated_record, sort_keys=True),
            encoding="utf-8",
        )
        return queue_file, updated_record

    def evaluate_patch_record_quality(
        record: object,
        **kwargs: object,
    ) -> object:
        assert isinstance(record, dict)
        gate_calls.append({"record": record, **kwargs})
        assert record.get("quality_evidence") == _PASS_QUALITY_EVIDENCE
        return (
            object(),
            _quality_result(
                verdict="PASS",
                safe_for_human_approval=True,
            ),
        )

    monkeypatch.setattr(
        full_file_approval,
        "run_patch_quality_evidence",
        run_patch_quality_evidence,
        raising=False,
    )
    monkeypatch.setattr(
        full_file_approval,
        "persist_patch_quality_evidence",
        persist_patch_quality_evidence,
        raising=False,
    )
    monkeypatch.setattr(
        full_file_approval,
        "evaluate_patch_record_quality",
        evaluate_patch_record_quality,
        raising=False,
    )

    _, approved_record = full_file_approval.approve_record(
        _PATCH_ID,
        _CONFIRMATION,
    )

    assert len(runner_calls) == 1
    assert runner_calls[0] == {
        "workspace_name": workspace_name,
        "target_file": target_file,
        "candidate_target_file": target_file,
        "candidate_file": candidate_file,
    }
    assert len(persistence_calls) == 1
    assert persistence_calls[0]["patch_id"] == _PATCH_ID
    assert persistence_calls[0]["result"] is result
    assert len(gate_calls) == 1
    assert approved_record["status"] == "APPROVED"
    assert _read_status(queue_file) == "APPROVED"


def test_existing_quality_evidence_skips_runner_and_persistence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queue_file = _write_record(monkeypatch, tmp_path)
    calls: list[dict[str, object]] = []

    def unexpected_runner(**kwargs: object) -> object:
        pytest.fail("quality evidence runner must not be called")

    def unexpected_persistence(**kwargs: object) -> object:
        pytest.fail("quality evidence persistence must not be called")

    monkeypatch.setattr(
        full_file_approval,
        "run_patch_quality_evidence",
        unexpected_runner,
        raising=False,
    )
    monkeypatch.setattr(
        full_file_approval,
        "persist_patch_quality_evidence",
        unexpected_persistence,
        raising=False,
    )
    _install_quality_result(
        monkeypatch,
        result=(
            object(),
            _quality_result(
                verdict="PASS",
                safe_for_human_approval=True,
            ),
        ),
        calls=calls,
    )

    _, data = full_file_approval.approve_record(_PATCH_ID, _CONFIRMATION)

    assert data["status"] == "APPROVED"
    assert _read_status(queue_file) == "APPROVED"
    _assert_quality_call(calls)


def test_runner_failure_blocks_approval_without_persistence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queue_file = _write_record(
        monkeypatch,
        tmp_path,
        include_quality_evidence=False,
    )

    def fail_runner(**kwargs: object) -> object:
        raise RuntimeError("runner failed")

    def unexpected_persistence(**kwargs: object) -> object:
        pytest.fail("persistence must not be called")

    monkeypatch.setattr(
        full_file_approval,
        "run_patch_quality_evidence",
        fail_runner,
        raising=False,
    )
    monkeypatch.setattr(
        full_file_approval,
        "persist_patch_quality_evidence",
        unexpected_persistence,
        raising=False,
    )

    with pytest.raises(RuntimeError):
        full_file_approval.approve_record(_PATCH_ID, _CONFIRMATION)

    assert _read_status(queue_file) == "READY_FOR_HUMAN_REVIEW"


def test_persistence_failure_blocks_approval(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queue_file = _write_record(
        monkeypatch,
        tmp_path,
        include_quality_evidence=False,
    )
    record = _read_record(queue_file)

    result = _execution_result(
        workspace_name=record["workspace_name"],
        target_file=record["target_file"],
    )
    quality_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        full_file_approval,
        "run_patch_quality_evidence",
        lambda **kwargs: result,
        raising=False,
    )

    def fail_persistence(**kwargs: object) -> object:
        raise RuntimeError("persistence failed")

    monkeypatch.setattr(
        full_file_approval,
        "persist_patch_quality_evidence",
        fail_persistence,
        raising=False,
    )
    _install_quality_result(
        monkeypatch,
        result=(
            object(),
            _quality_result(
                verdict="PASS",
                safe_for_human_approval=True,
            ),
        ),
        calls=quality_calls,
    )

    with pytest.raises(RuntimeError):
        full_file_approval.approve_record(_PATCH_ID, _CONFIRMATION)

    assert quality_calls == []
    assert _read_status(queue_file) == "READY_FOR_HUMAN_REVIEW"


def test_failed_test_evidence_is_persisted_then_gate_blocks_approval(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queue_file = _write_record(
        monkeypatch,
        tmp_path,
        include_quality_evidence=False,
    )
    record = _read_record(queue_file)
    failed_evidence = {
        "focused_tests_executed": True,
        "focused_tests_passed": False,
        "regression_tests_executed": False,
        "regression_tests_passed": False,
    }
    result = _execution_result(
        workspace_name=record["workspace_name"],
        target_file=record["target_file"],
        focused_tests_executed=True,
        focused_tests_passed=False,
        regression_tests_executed=False,
        regression_tests_passed=False,
    )
    quality_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        full_file_approval,
        "run_patch_quality_evidence",
        lambda **kwargs: result,
        raising=False,
    )

    def persist_failed_evidence(
        *,
        patch_id: str,
        result: PatchQualityExecutionResult,
    ) -> tuple[Path, dict[str, Any]]:
        updated_record = _read_record(queue_file)
        updated_record["quality_evidence"] = dict(failed_evidence)
        queue_file.write_text(
            json.dumps(updated_record, sort_keys=True),
            encoding="utf-8",
        )
        return queue_file, updated_record

    monkeypatch.setattr(
        full_file_approval,
        "persist_patch_quality_evidence",
        persist_failed_evidence,
        raising=False,
    )

    def evaluate_failed_evidence(
        record: object,
        **kwargs: object,
    ) -> object:
        assert isinstance(record, dict)
        quality_calls.append({"record": record, **kwargs})
        assert record.get("quality_evidence") == failed_evidence
        return (
            object(),
            _quality_result(
                verdict="REVISE",
                safe_for_human_approval=False,
            ),
        )

    monkeypatch.setattr(
        full_file_approval,
        "evaluate_patch_record_quality",
        evaluate_failed_evidence,
        raising=False,
    )

    with pytest.raises(RuntimeError):
        full_file_approval.approve_record(_PATCH_ID, _CONFIRMATION)

    assert _read_record(queue_file)["quality_evidence"] == failed_evidence
    assert _read_status(queue_file) == "READY_FOR_HUMAN_REVIEW"
    assert len(quality_calls) == 1


def test_wrong_confirmation_does_not_run_quality_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queue_file = _write_record(
        monkeypatch,
        tmp_path,
        include_quality_evidence=False,
    )

    def unexpected_runner(**kwargs: object) -> object:
        pytest.fail("quality evidence runner must not be called")

    def unexpected_persistence(**kwargs: object) -> object:
        pytest.fail("quality evidence persistence must not be called")

    monkeypatch.setattr(
        full_file_approval,
        "run_patch_quality_evidence",
        unexpected_runner,
        raising=False,
    )
    monkeypatch.setattr(
        full_file_approval,
        "persist_patch_quality_evidence",
        unexpected_persistence,
        raising=False,
    )

    with pytest.raises(RuntimeError):
        full_file_approval.approve_record(
            _PATCH_ID,
            "WRONG CONFIRMATION",
        )

    assert _read_status(queue_file) == "READY_FOR_HUMAN_REVIEW"


def test_non_ready_lifecycle_does_not_run_quality_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    queue_file = _write_record(
        monkeypatch,
        tmp_path,
        include_quality_evidence=False,
    )
    record = _read_record(queue_file)
    record["status"] = "APPROVED"
    queue_file.write_text(
        json.dumps(record, sort_keys=True),
        encoding="utf-8",
    )

    def unexpected_runner(**kwargs: object) -> object:
        pytest.fail("quality evidence runner must not be called")

    def unexpected_persistence(**kwargs: object) -> object:
        pytest.fail("quality evidence persistence must not be called")

    monkeypatch.setattr(
        full_file_approval,
        "run_patch_quality_evidence",
        unexpected_runner,
        raising=False,
    )
    monkeypatch.setattr(
        full_file_approval,
        "persist_patch_quality_evidence",
        unexpected_persistence,
        raising=False,
    )

    with pytest.raises(RuntimeError):
        full_file_approval.approve_record(_PATCH_ID, _CONFIRMATION)

    assert _read_status(queue_file) == "APPROVED"