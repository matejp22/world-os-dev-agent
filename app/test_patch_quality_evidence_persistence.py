from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import app.patch_quality_evidence_persistence


_BOOTSTRAP_ENV = "WORLD_OS_PATCH_QUALITY_EVIDENCE_PERSISTENCE_CANDIDATE"
_CANONICAL_MODULE = "app.patch_quality_evidence_persistence"
_CANDIDATE_MODULE = "_world_os_patch_quality_evidence_persistence_candidate"
_PATCH_ID = "patch-quality-evidence-test"


def _load_persistence_module() -> ModuleType:
    try:
        return importlib.import_module(_CANONICAL_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name != _CANONICAL_MODULE:
            raise

    candidate_value = os.environ.get(_BOOTSTRAP_ENV)
    if candidate_value is None or not candidate_value.strip():
        raise RuntimeError(
            f"{_CANONICAL_MODULE} is unavailable and {_BOOTSTRAP_ENV} "
            "was not supplied."
        )

    candidate = Path(candidate_value).expanduser().resolve()
    if not candidate.exists():
        raise RuntimeError(f"Candidate does not exist: {candidate}")
    if not candidate.is_file():
        raise RuntimeError(f"Candidate is not a regular file: {candidate}")
    if candidate.suffix.lower() != ".py":
        raise RuntimeError("Candidate must be a Python file.")

    spec = importlib.util.spec_from_file_location(_CANDIDATE_MODULE, candidate)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to create candidate module specification.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    else:
        sys.modules.pop(spec.name, None)

    return module


@pytest.fixture
def persistence_module() -> ModuleType:
    return _load_persistence_module()


@pytest.fixture
def runner_module() -> ModuleType:
    return importlib.import_module("app.patch_quality_evidence_runner")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_result(
    runner_module: ModuleType,
    *,
    focused_executed: bool = True,
    focused_passed: bool = True,
    regression_executed: bool = True,
    regression_passed: bool = True,
    execution_supported: bool = True,
    workspace_name: str = "world-os-dev-agent",
    target_file: str = "app/example.py",
) -> object:
    return runner_module.PatchQualityExecutionResult(
        workspace_name=workspace_name,
        target_file=target_file,
        behavioral_source_change=True,
        focused_test_ids=("test_focus",),
        regression_test_ids=("test_regression",),
        focused_tests_executed=focused_executed,
        focused_tests_passed=focused_passed,
        regression_tests_executed=regression_executed,
        regression_tests_passed=regression_passed,
        execution_supported=execution_supported,
        reasons=("ok",),
    )


def _make_record(
    candidate: Path,
    candidate_sha256: str,
    *,
    status: str = "READY_FOR_HUMAN_REVIEW",
    quality_evidence: object = None,
) -> dict:
    return {
        "patch_id": _PATCH_ID,
        "status": status,
        "workspace_name": "world-os-dev-agent",
        "target_file": "app/example.py",
        "format_version": "FULL_FILE_V2",
        "candidate_file": str(candidate),
        "candidate_sha256": candidate_sha256,
        "quality_evidence": quality_evidence,
    }


def _install_mocks(
    monkeypatch: pytest.MonkeyPatch,
    persistence_module: ModuleType,
    records: list[dict],
    queue_path: Path,
) -> tuple[list[tuple[Path, dict]], list[int]]:
    loads: list[int] = []
    writes: list[tuple[Path, dict]] = []

    def fake_load_record(patch_id: str) -> tuple[Path, dict]:
        assert patch_id == _PATCH_ID
        index = len(loads)
        loads.append(index)
        return queue_path, records[min(index, len(records) - 1)]

    def fake_atomic_write_json(path: Path, payload: dict) -> None:
        writes.append((path, payload))

    monkeypatch.setattr(persistence_module, "load_record", fake_load_record)
    monkeypatch.setattr(
        persistence_module,
        "atomic_write_json",
        fake_atomic_write_json,
    )
    return writes, loads


def _candidate(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "candidate.py"
    path.write_text("value = 1\n", encoding="utf-8")
    return path, _sha256(path)


def test_success_persists_exact_payload_atomically(
    persistence_module: ModuleType,
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    candidate, digest = _candidate(tmp_path)
    evidence = {
        "focused_tests_executed": True,
        "focused_tests_passed": True,
        "regression_tests_executed": True,
        "regression_tests_passed": True,
    }
    first = _make_record(candidate, digest)
    second = _make_record(candidate, digest, quality_evidence=evidence)
    queue_path = tmp_path / "queue.json"
    writes, loads = _install_mocks(
        monkeypatch,
        persistence_module,
        [first, second],
        queue_path,
    )

    result = persistence_module.persist_patch_quality_evidence(
        patch_id=_PATCH_ID,
        result=_make_result(runner_module),
    )

    assert writes == [(queue_path, {**first, "quality_evidence": evidence})]
    assert result == (queue_path, second)
    assert loads == [0, 1]
    assert writes[0][1]["status"] == "READY_FOR_HUMAN_REVIEW"


@pytest.mark.parametrize("status", ["APPROVED", "APPLIED"])
def test_refuses_non_ready_lifecycle_without_write(
    persistence_module: ModuleType,
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    status: str,
) -> None:
    candidate, digest = _candidate(tmp_path)
    record = _make_record(candidate, digest, status=status)
    writes, _ = _install_mocks(
        monkeypatch,
        persistence_module,
        [record],
        tmp_path / "queue.json",
    )

    with pytest.raises(RuntimeError):
        persistence_module.persist_patch_quality_evidence(
            patch_id=_PATCH_ID,
            result=_make_result(runner_module),
        )

    assert writes == []


def test_refuses_existing_quality_evidence_without_overwrite(
    persistence_module: ModuleType,
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    candidate, digest = _candidate(tmp_path)
    existing = {
        "focused_tests_executed": False,
        "focused_tests_passed": False,
        "regression_tests_executed": False,
        "regression_tests_passed": False,
    }
    record = _make_record(candidate, digest, quality_evidence=existing)
    writes, _ = _install_mocks(
        monkeypatch,
        persistence_module,
        [record],
        tmp_path / "queue.json",
    )

    with pytest.raises(RuntimeError):
        persistence_module.persist_patch_quality_evidence(
            patch_id=_PATCH_ID,
            result=_make_result(runner_module),
        )

    assert writes == []
    assert record["quality_evidence"] == existing


@pytest.mark.parametrize(
    ("workspace_name", "target_file"),
    [
        ("other-workspace", "app/example.py"),
        ("world-os-dev-agent", "app/other.py"),
    ],
)
def test_refuses_result_identity_mismatch(
    persistence_module: ModuleType,
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    workspace_name: str,
    target_file: str,
) -> None:
    candidate, digest = _candidate(tmp_path)
    record = _make_record(candidate, digest)
    writes, _ = _install_mocks(
        monkeypatch,
        persistence_module,
        [record],
        tmp_path / "queue.json",
    )

    with pytest.raises(RuntimeError):
        persistence_module.persist_patch_quality_evidence(
            patch_id=_PATCH_ID,
            result=_make_result(
                runner_module,
                workspace_name=workspace_name,
                target_file=target_file,
            ),
        )

    assert writes == []


def test_refuses_untrusted_execution_result(
    persistence_module: ModuleType,
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    candidate, digest = _candidate(tmp_path)
    record = _make_record(candidate, digest)
    writes, _ = _install_mocks(
        monkeypatch,
        persistence_module,
        [record],
        tmp_path / "queue.json",
    )

    with pytest.raises(RuntimeError):
        persistence_module.persist_patch_quality_evidence(
            patch_id=_PATCH_ID,
            result=_make_result(
                runner_module,
                execution_supported=False,
            ),
        )

    assert writes == []


def test_refuses_candidate_sha_mismatch(
    persistence_module: ModuleType,
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    candidate, _ = _candidate(tmp_path)
    record = _make_record(candidate, "0" * 64)
    writes, _ = _install_mocks(
        monkeypatch,
        persistence_module,
        [record],
        tmp_path / "queue.json",
    )

    with pytest.raises(RuntimeError):
        persistence_module.persist_patch_quality_evidence(
            patch_id=_PATCH_ID,
            result=_make_result(runner_module),
        )

    assert writes == []


def test_failed_test_evidence_is_persistable_when_execution_is_supported(
    persistence_module: ModuleType,
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    candidate, digest = _candidate(tmp_path)
    evidence = {
        "focused_tests_executed": True,
        "focused_tests_passed": False,
        "regression_tests_executed": False,
        "regression_tests_passed": False,
    }
    first = _make_record(candidate, digest)
    second = _make_record(candidate, digest, quality_evidence=evidence)
    writes, _ = _install_mocks(
        monkeypatch,
        persistence_module,
        [first, second],
        tmp_path / "queue.json",
    )

    persistence_module.persist_patch_quality_evidence(
        patch_id=_PATCH_ID,
        result=_make_result(
            runner_module,
            focused_passed=False,
            regression_executed=False,
            regression_passed=False,
        ),
    )

    assert writes[0][1]["quality_evidence"] == evidence


def test_persisted_reload_must_match_exact_payload(
    persistence_module: ModuleType,
    runner_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    candidate, digest = _candidate(tmp_path)
    first = _make_record(candidate, digest)
    second = _make_record(
        candidate,
        digest,
        quality_evidence={
            "focused_tests_executed": True,
            "focused_tests_passed": False,
            "regression_tests_executed": True,
            "regression_tests_passed": True,
        },
    )
    writes, _ = _install_mocks(
        monkeypatch,
        persistence_module,
        [first, second],
        tmp_path / "queue.json",
    )

    with pytest.raises(RuntimeError):
        persistence_module.persist_patch_quality_evidence(
            patch_id=_PATCH_ID,
            result=_make_result(runner_module),
        )

    assert len(writes) == 1


@pytest.mark.parametrize("patch_id", ["", "   ", 123])
def test_invalid_patch_id_rejected_before_queue_access(
    persistence_module: ModuleType,
    patch_id: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loads: list[object] = []
    writes: list[object] = []

    monkeypatch.setattr(
        persistence_module,
        "load_record",
        lambda value: loads.append(value),
    )
    monkeypatch.setattr(
        persistence_module,
        "atomic_write_json",
        lambda path, payload: writes.append((path, payload)),
    )

    with pytest.raises((ValueError, TypeError)):
        persistence_module.persist_patch_quality_evidence(
            patch_id=patch_id,
            result=object(),
        )

    assert loads == []
    assert writes == []