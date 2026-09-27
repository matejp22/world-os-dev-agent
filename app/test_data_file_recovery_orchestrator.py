from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterator

import pytest

from app.data_file_partial_state_recovery import DataFileRecoveryResult
from app.data_file_record_factory import build_data_file_patch_record
from app.data_file_recovery_queue import DataFileRecoveryQueueEntry
from app.data_file_types import DataFilePatchRecord


FOCUSED_TARGET_MODULES = (
    "app.data_file_recovery_orchestrator",
)

_CANDIDATE_ENVIRONMENT_VARIABLE = (
    "WORLD_OS_DATA_FILE_RECOVERY_ORCHESTRATOR_CANDIDATE"
)
_TARGET_MODULE = "app.data_file_recovery_orchestrator"


@pytest.fixture
def implementation_module() -> Iterator[ModuleType]:
    target_name = _TARGET_MODULE
    previous_module = sys.modules.get(target_name)
    sys.modules.pop(target_name, None)

    candidate_value = os.environ.get(_CANDIDATE_ENVIRONMENT_VARIABLE)

    try:
        if candidate_value is not None:
            candidate_path = Path(candidate_value).resolve()

            if not candidate_path.is_file():
                raise AssertionError(
                    "Candidate path must resolve to a file."
                )

            spec = importlib.util.spec_from_file_location(
                target_name,
                candidate_path,
            )
            if spec is None or spec.loader is None:
                raise AssertionError("Could not load candidate module.")

            module = importlib.util.module_from_spec(spec)
            sys.modules[target_name] = module
            spec.loader.exec_module(module)
            yield module
            return

        try:
            module = importlib.import_module(target_name)
        except ModuleNotFoundError as exc:
            if exc.name == target_name:
                pytest.skip(
                    f"{target_name} is not canonically installed yet."
                )
            raise

        yield module
    finally:
        sys.modules.pop(target_name, None)
        if previous_module is not None:
            sys.modules[target_name] = previous_module


def _record(index: int) -> DataFilePatchRecord:
    return build_data_file_patch_record(
        patch_id=f"patch-{index}",
        operation="CREATE",
        data_kind="PROJECT_ROADMAP",
        workspace_name="world-os-dev-agent",
        target_file="ROADMAP.md",
        original_sha256=None,
        candidate_bytes=f"candidate-{index}".encode("utf-8"),
        candidate_file=f"candidate-{index}.py",
        diff_file=f"diff-{index}.patch",
        semantic_decision="APPROVE_FOR_HUMAN_REVIEW",
        semantic_review="Focused orchestrator fixture.",
        status="APPROVED",
        created_at=f"2025-01-01T00:00:{index:02d}+00:00",
    )


def _entry(tmp_path: Path, index: int) -> DataFileRecoveryQueueEntry:
    queue_path = tmp_path / f"queue-{index}.json"
    queue_path.write_bytes(f"queue-{index}".encode("utf-8"))

    return DataFileRecoveryQueueEntry(
        queue_path=queue_path,
        record=_record(index),
        candidate_path=tmp_path / f"candidate-{index}.py",
    )


def _result(index: int) -> DataFileRecoveryResult:
    return DataFileRecoveryResult(
        patch_id=f"patch-{index}",
        operation="CREATE",
        initial_status="APPROVED",
        final_status="APPLIED",
        recovery_status="RECOVERED_TO_APPLIED",
        target_file="ROADMAP.md",
        candidate_sha256="a" * 64,
        observed_target_sha256="b" * 64,
        reason=f"Recovered {index}.",
    )


def test_candidate_public_api_proof(
    implementation_module: ModuleType,
) -> None:
    candidate_value = os.environ.get(_CANDIDATE_ENVIRONMENT_VARIABLE)
    if candidate_value is None:
        pytest.skip(
            f"{_CANDIDATE_ENVIRONMENT_VARIABLE} is not set."
        )

    assert Path(implementation_module.__file__).resolve() == (
        Path(candidate_value).resolve()
    )
    assert callable(
        implementation_module.run_data_file_recovery_cycle
    )


def test_empty_discovery(
    implementation_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    recovery_calls: list[object] = []

    monkeypatch.setattr(
        implementation_module,
        "discover_data_file_recovery_candidates",
        lambda *, queue_dir: (),
    )
    monkeypatch.setattr(
        implementation_module,
        "recover_data_file_partial_state",
        lambda **kwargs: recovery_calls.append(kwargs),
    )

    result = implementation_module.run_data_file_recovery_cycle(
        queue_dir=tmp_path,
    )

    assert recovery_calls == []
    assert result == ()
    assert type(result) is tuple


def test_exact_forwarding_and_order(
    implementation_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first = _entry(tmp_path, 1)
    second = _entry(tmp_path, 2)
    entries = (first, second)
    discovery_calls: list[Path] = []
    recovery_calls: list[dict[str, object]] = []
    recovery_results = (_result(1), _result(2))

    def fake_discovery(
        *,
        queue_dir: Path,
    ) -> tuple[DataFileRecoveryQueueEntry, ...]:
        discovery_calls.append(queue_dir)
        return entries

    def fake_recovery(**kwargs: object) -> DataFileRecoveryResult:
        recovery_calls.append(kwargs)
        return recovery_results[len(recovery_calls) - 1]

    monkeypatch.setattr(
        implementation_module,
        "discover_data_file_recovery_candidates",
        fake_discovery,
    )
    monkeypatch.setattr(
        implementation_module,
        "recover_data_file_partial_state",
        fake_recovery,
    )

    result = implementation_module.run_data_file_recovery_cycle(
        queue_dir=tmp_path,
    )

    assert discovery_calls == [tmp_path]
    assert len(recovery_calls) == 2

    assert recovery_calls[0] == {
        "queue_path": first.queue_path,
        "expected_current_bytes": b"queue-1",
        "record": first.record,
        "candidate_path": first.candidate_path,
    }
    assert recovery_calls[1] == {
        "queue_path": second.queue_path,
        "expected_current_bytes": b"queue-2",
        "record": second.record,
        "candidate_path": second.candidate_path,
    }
    assert result == recovery_results
    assert type(result) is tuple


def test_per_entry_just_in_time_snapshot(
    implementation_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first = _entry(tmp_path, 1)
    second = _entry(tmp_path, 2)
    recovery_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        implementation_module,
        "discover_data_file_recovery_candidates",
        lambda *, queue_dir: (first, second),
    )

    def fake_recovery(**kwargs: object) -> DataFileRecoveryResult:
        recovery_calls.append(kwargs)

        if len(recovery_calls) == 1:
            second.queue_path.write_bytes(b"changed-before-second-call")

        return _result(len(recovery_calls))

    monkeypatch.setattr(
        implementation_module,
        "recover_data_file_partial_state",
        fake_recovery,
    )

    result = implementation_module.run_data_file_recovery_cycle(
        queue_dir=tmp_path,
    )

    assert result == (_result(1), _result(2))
    assert recovery_calls[0]["expected_current_bytes"] == b"queue-1"
    assert recovery_calls[1]["expected_current_bytes"] == (
        b"changed-before-second-call"
    )


def test_recovery_error_propagates_without_retry(
    implementation_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first = _entry(tmp_path, 1)
    second = _entry(tmp_path, 2)
    sentinel = RuntimeError("sentinel recovery failure")
    recovery_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        implementation_module,
        "discover_data_file_recovery_candidates",
        lambda *, queue_dir: (first, second),
    )

    def fake_recovery(**kwargs: object) -> DataFileRecoveryResult:
        recovery_calls.append(kwargs)
        raise sentinel

    monkeypatch.setattr(
        implementation_module,
        "recover_data_file_partial_state",
        fake_recovery,
    )

    with pytest.raises(RuntimeError) as exc_info:
        implementation_module.run_data_file_recovery_cycle(
            queue_dir=tmp_path,
        )

    assert exc_info.value is sentinel
    assert len(recovery_calls) == 1


def test_discovery_error_propagates(
    implementation_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sentinel = ValueError("sentinel discovery failure")
    recovery_calls: list[object] = []

    def fake_discovery(
        *,
        queue_dir: Path,
    ) -> tuple[DataFileRecoveryQueueEntry, ...]:
        raise sentinel

    monkeypatch.setattr(
        implementation_module,
        "discover_data_file_recovery_candidates",
        fake_discovery,
    )
    monkeypatch.setattr(
        implementation_module,
        "recover_data_file_partial_state",
        lambda **kwargs: recovery_calls.append(kwargs),
    )

    with pytest.raises(ValueError) as exc_info:
        implementation_module.run_data_file_recovery_cycle(
            queue_dir=tmp_path,
        )

    assert exc_info.value is sentinel
    assert recovery_calls == []