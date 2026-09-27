from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterator

import pytest

from app.data_file_record_factory import build_data_file_patch_record
from app.data_file_record_store import load_data_file_patch_record


FOCUSED_TARGET_MODULES = (
    "app.data_file_recovery_queue",
)

_CANDIDATE_ENVIRONMENT_VARIABLE = (
    "WORLD_OS_DATA_FILE_RECOVERY_QUEUE_CANDIDATE"
)
_INCLUDED_STATUSES = (
    "APPROVED",
    "APPLYING",
    "CREATED_VERIFIED",
    "REPLACED_VERIFIED",
    "APPLIED",
)
_EXCLUDED_STATUSES = (
    "DRAFT",
    "READY_FOR_HUMAN_REVIEW",
    "REJECTED",
    "ROLLED_BACK",
    "ROLLBACK_FAILED",
)


@pytest.fixture
def implementation_module() -> Iterator[ModuleType]:
    candidate_value = os.environ.get(_CANDIDATE_ENVIRONMENT_VARIABLE)

    if candidate_value is not None:
        candidate_path = Path(candidate_value).resolve()
        module_name = "_data_file_recovery_queue_candidate"
        spec = importlib.util.spec_from_file_location(
            module_name,
            candidate_path,
        )
        if spec is None or spec.loader is None:
            raise AssertionError("Could not load candidate module.")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
            yield module
        finally:
            sys.modules.pop(module_name, None)
        return

    target_name = "app.data_file_recovery_queue"
    previous_module = sys.modules.get(target_name)
    sys.modules.pop(target_name, None)

    try:
        try:
            module = importlib.import_module(target_name)
        except ModuleNotFoundError as exc:
            if exc.name != target_name:
                raise
            pytest.skip(
                "app.data_file_recovery_queue is not canonically installed yet."
            )
        yield module
    finally:
        sys.modules.pop(target_name, None)
        if previous_module is not None:
            sys.modules[target_name] = previous_module


def _write_record(
    queue_directory: Path,
    *,
    filename: str,
    status: str,
    index: int,
) -> Path:
    candidate_path = queue_directory / f"candidate-{index}.py"
    diff_path = queue_directory / f"diff-{index}.patch"
    candidate_path.write_bytes(f"candidate {index}\n".encode("utf-8"))
    diff_path.write_text(f"diff {index}\n", encoding="utf-8")

    record = build_data_file_patch_record(
        patch_id=f"patch-{index}",
        operation="CREATE",
        data_kind="PROJECT_ROADMAP",
        workspace_name="world-os-dev-agent",
        target_file="ROADMAP.md",
        original_sha256=None,
        candidate_bytes=candidate_path.read_bytes(),
        candidate_file=str(candidate_path),
        diff_file=str(diff_path),
        semantic_decision="ACCEPT",
        semantic_review="Valid focused test fixture.",
        status=status,
        created_at=f"2025-01-01T00:00:{index:02d}+00:00",
    )

    record_path = queue_directory / filename
    record_data = {
        "patch_id": record.patch_id,
        "format_version": record.format_version,
        "operation": record.operation,
        "data_kind": record.data_kind,
        "workspace_name": record.workspace_name,
        "target_file": record.target_file,
        "original_sha256": record.original_sha256,
        "candidate_sha256": record.candidate_sha256,
        "candidate_file": record.candidate_file,
        "diff_file": record.diff_file,
        "validation_passed": record.validation_passed,
        "semantic_decision": record.semantic_decision,
        "semantic_review": record.semantic_review,
        "status": record.status,
        "created_at": record.created_at,
    }
    record_path.write_text(
        json.dumps(record_data, indent=2),
        encoding="utf-8",
    )
    return record_path


def test_candidate_path_public_api_proof(
    implementation_module: ModuleType,
    tmp_path: Path,
) -> None:
    candidate_value = os.environ.get(_CANDIDATE_ENVIRONMENT_VARIABLE)
    if candidate_value is None:
        pytest.skip(
            "WORLD_OS_DATA_FILE_RECOVERY_QUEUE_CANDIDATE is not set."
        )

    candidate_path = Path(candidate_value)
    assert Path(implementation_module.__file__).resolve() == (
        candidate_path.resolve()
    )
    assert callable(
        implementation_module.discover_data_file_recovery_candidates
    )

    missing_directory = tmp_path / "missing-queue"
    result = (
        implementation_module.discover_data_file_recovery_candidates(
            queue_dir=missing_directory,
        )
    )
    assert result == ()


def test_missing_directory_returns_empty_tuple(
    implementation_module: ModuleType,
    tmp_path: Path,
) -> None:
    result = implementation_module.discover_data_file_recovery_candidates(
        queue_dir=tmp_path / "missing-queue",
    )
    assert result == ()


def test_queue_directory_file_raises_value_error(
    implementation_module: ModuleType,
    tmp_path: Path,
) -> None:
    queue_file = tmp_path / "queue-file"
    queue_file.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ValueError):
        implementation_module.discover_data_file_recovery_candidates(
            queue_dir=queue_file,
        )


def test_discovers_canonical_records_in_filename_order(
    implementation_module: ModuleType,
    tmp_path: Path,
) -> None:
    queue_directory = tmp_path / "queue"
    queue_directory.mkdir()

    statuses = _INCLUDED_STATUSES + _EXCLUDED_STATUSES
    filenames = [
        "030-record.json",
        "010-record.json",
        "090-record.json",
        "020-record.json",
        "080-record.json",
        "040-record.json",
        "070-record.json",
        "060-record.json",
        "050-record.json",
        "001-record.json",
    ]

    paths_by_status: dict[str, Path] = {}
    for index, (status, filename) in enumerate(
        zip(statuses, filenames, strict=True),
        start=1,
    ):
        paths_by_status[status] = _write_record(
            queue_directory,
            filename=filename,
            status=status,
            index=index,
        )

    result = implementation_module.discover_data_file_recovery_candidates(
        queue_dir=queue_directory,
    )

    assert type(result) is tuple

    expected_included_paths = sorted(
        (
            paths_by_status[status]
            for status in _INCLUDED_STATUSES
        ),
        key=lambda path: path.name,
    )
    expected_statuses = [
        next(
            status
            for status, path in paths_by_status.items()
            if path == queue_path
        )
        for queue_path in expected_included_paths
    ]
    assert [entry.record.status for entry in result] == expected_statuses
    assert [entry.queue_path for entry in result] == expected_included_paths

    for entry in result:
        loaded_record = load_data_file_patch_record(entry.queue_path)
        assert entry.record == loaded_record
        assert entry.candidate_path == Path(entry.record.candidate_file)


def test_skips_malformed_and_unsupported_json(
    implementation_module: ModuleType,
    tmp_path: Path,
) -> None:
    queue_directory = tmp_path / "queue"
    queue_directory.mkdir()

    valid_path = _write_record(
        queue_directory,
        filename="valid.json",
        status="APPROVED",
        index=1,
    )
    (queue_directory / "malformed.json").write_text(
        "{not valid json",
        encoding="utf-8",
    )
    (queue_directory / "unsupported.json").write_text(
        json.dumps({"format_version": "OTHER_FORMAT"}),
        encoding="utf-8",
    )

    result = implementation_module.discover_data_file_recovery_candidates(
        queue_dir=queue_directory,
    )

    assert len(result) == 1
    assert result[0].queue_path == valid_path


def test_discovers_direct_children_only(
    implementation_module: ModuleType,
    tmp_path: Path,
) -> None:
    queue_directory = tmp_path / "queue"
    nested_directory = queue_directory / "nested"
    queue_directory.mkdir()
    nested_directory.mkdir()

    direct_path = _write_record(
        queue_directory,
        filename="direct.json",
        status="APPROVED",
        index=1,
    )
    _write_record(
        nested_directory,
        filename="ignored.json",
        status="APPLIED",
        index=2,
    )

    result = implementation_module.discover_data_file_recovery_candidates(
        queue_dir=queue_directory,
    )

    assert [entry.queue_path for entry in result] == [direct_path]


def test_ignores_non_json_files(
    implementation_module: ModuleType,
    tmp_path: Path,
) -> None:
    queue_directory = tmp_path / "queue"
    queue_directory.mkdir()

    valid_path = _write_record(
        queue_directory,
        filename="valid.json",
        status="APPROVED",
        index=1,
    )
    (queue_directory / "notes.txt").write_text(
        "not a queue record",
        encoding="utf-8",
    )
    (queue_directory / "record.json.bak").write_text(
        "not a queue record",
        encoding="utf-8",
    )

    result = implementation_module.discover_data_file_recovery_candidates(
        queue_dir=queue_directory,
    )

    assert [entry.queue_path for entry in result] == [valid_path]


def test_discovery_is_read_only(
    implementation_module: ModuleType,
    tmp_path: Path,
) -> None:
    queue_directory = tmp_path / "queue"
    queue_directory.mkdir()

    _write_record(
        queue_directory,
        filename="b-record.json",
        status="APPROVED",
        index=1,
    )
    _write_record(
        queue_directory,
        filename="a-record.json",
        status="APPLIED",
        index=2,
    )
    (queue_directory / "notes.txt").write_bytes(b"fixed bytes")

    before = {
        path.name: path.read_bytes()
        for path in queue_directory.iterdir()
        if path.is_file()
    }

    implementation_module.discover_data_file_recovery_candidates(
        queue_dir=queue_directory,
    )

    after = {
        path.name: path.read_bytes()
        for path in queue_directory.iterdir()
        if path.is_file()
    }

    assert set(after) == set(before)
    assert after == before