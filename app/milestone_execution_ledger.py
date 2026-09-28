from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Literal


PROJECT_ROOT = Path(__file__).resolve().parent.parent

MILESTONE_EXECUTION_LEDGER_PATH = (
    PROJECT_ROOT
    / "context"
    / "RESEARCH_ENGINE_MILESTONE_EXECUTION_LEDGER.json"
)

ExecutionStepStatus = Literal[
    "PLANNED",
    "IN_PROGRESS",
    "COMPLETED",
    "SUPERSEDED",
]

_ALLOWED_STATUSES = frozenset(
    {
        "PLANNED",
        "IN_PROGRESS",
        "COMPLETED",
        "SUPERSEDED",
    }
)

_STEP_FIELDS = frozenset(
    {
        "step_id",
        "title",
        "status",
        "patch_ids",
        "target_files",
        "note",
    }
)

_LEDGER_FIELDS = frozenset(
    {
        "workspace_name",
        "milestone_id",
        "milestone_title",
        "steps",
    }
)


@dataclass(frozen=True)
class MilestoneExecutionStep:
    step_id: str
    title: str
    status: ExecutionStepStatus
    patch_ids: tuple[str, ...] = ()
    target_files: tuple[str, ...] = ()
    note: str | None = None


@dataclass(frozen=True)
class MilestoneExecutionLedger:
    workspace_name: str
    milestone_id: str
    milestone_title: str
    steps: tuple[MilestoneExecutionStep, ...]


def _require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")
    return value


def _require_string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name} must be a tuple.")
    for item in value:
        _require_non_empty_string(item, field_name)
    return value


def validate_milestone_execution_step(
    step: MilestoneExecutionStep,
) -> None:
    if not isinstance(step, MilestoneExecutionStep):
        raise TypeError("step must be a MilestoneExecutionStep.")

    _require_non_empty_string(step.step_id, "step_id")
    _require_non_empty_string(step.title, "title")

    if not isinstance(step.status, str):
        raise TypeError("status must be a string.")
    if step.status not in _ALLOWED_STATUSES:
        raise ValueError(f"Unsupported step status: {step.status!r}")

    _require_string_tuple(step.patch_ids, "patch_ids")
    _require_string_tuple(step.target_files, "target_files")

    if step.note is not None and not isinstance(step.note, str):
        raise TypeError("note must be a string or None.")


def validate_milestone_execution_ledger(
    ledger: MilestoneExecutionLedger,
) -> None:
    if not isinstance(ledger, MilestoneExecutionLedger):
        raise TypeError("ledger must be a MilestoneExecutionLedger.")

    if ledger.workspace_name != "world-os-research-engine":
        raise ValueError(
            "workspace_name must be world-os-research-engine."
        )

    _require_non_empty_string(ledger.milestone_id, "milestone_id")
    _require_non_empty_string(ledger.milestone_title, "milestone_title")

    if not isinstance(ledger.steps, tuple):
        raise TypeError("steps must be a tuple.")

    step_ids: set[str] = set()

    for step in ledger.steps:
        validate_milestone_execution_step(step)

        if step.step_id in step_ids:
            raise ValueError(f"Duplicate step_id: {step.step_id!r}")

        step_ids.add(step.step_id)


def milestone_execution_ledger_to_dict(
    ledger: MilestoneExecutionLedger,
) -> dict[str, object]:
    validate_milestone_execution_ledger(ledger)

    return {
        "milestone_id": ledger.milestone_id,
        "milestone_title": ledger.milestone_title,
        "steps": [
            {
                "note": step.note,
                "patch_ids": list(step.patch_ids),
                "status": step.status,
                "step_id": step.step_id,
                "target_files": list(step.target_files),
                "title": step.title,
            }
            for step in ledger.steps
        ],
        "workspace_name": ledger.workspace_name,
    }


def milestone_execution_ledger_from_dict(
    value: object,
) -> MilestoneExecutionLedger:
    if not isinstance(value, dict):
        raise TypeError("Ledger value must be a dict.")

    if set(value) != _LEDGER_FIELDS:
        raise ValueError("Ledger fields do not match schema.")

    workspace_name = value["workspace_name"]
    milestone_id = value["milestone_id"]
    milestone_title = value["milestone_title"]
    raw_steps = value["steps"]

    if not isinstance(workspace_name, str):
        raise TypeError("workspace_name must be a string.")
    if not isinstance(milestone_id, str):
        raise TypeError("milestone_id must be a string.")
    if not isinstance(milestone_title, str):
        raise TypeError("milestone_title must be a string.")
    if not isinstance(raw_steps, list):
        raise TypeError("steps must be a JSON list.")

    steps: list[MilestoneExecutionStep] = []

    for raw_step in raw_steps:
        if not isinstance(raw_step, dict):
            raise TypeError("Each step must be a dict.")

        if set(raw_step) != _STEP_FIELDS:
            raise ValueError("Step fields do not match schema.")

        patch_ids = raw_step["patch_ids"]
        target_files = raw_step["target_files"]

        if not isinstance(patch_ids, list):
            raise TypeError("patch_ids must be a JSON list.")
        if not isinstance(target_files, list):
            raise TypeError("target_files must be a JSON list.")

        if any(not isinstance(item, str) for item in patch_ids):
            raise TypeError("patch_ids must contain only strings.")
        if any(not isinstance(item, str) for item in target_files):
            raise TypeError("target_files must contain only strings.")

        step = MilestoneExecutionStep(
            step_id=raw_step["step_id"],
            title=raw_step["title"],
            status=raw_step["status"],
            patch_ids=tuple(patch_ids),
            target_files=tuple(target_files),
            note=raw_step["note"],
        )

        validate_milestone_execution_step(step)
        steps.append(step)

    ledger = MilestoneExecutionLedger(
        workspace_name=workspace_name,
        milestone_id=milestone_id,
        milestone_title=milestone_title,
        steps=tuple(steps),
    )

    validate_milestone_execution_ledger(ledger)
    return ledger


def load_milestone_execution_ledger() -> MilestoneExecutionLedger | None:
    path = Path(MILESTONE_EXECUTION_LEDGER_PATH)

    if not path.exists():
        return None

    if not path.is_file():
        raise RuntimeError(
            "Canonical milestone execution ledger is not a file."
        )

    try:
        raw = path.read_text(encoding="utf-8")
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Unable to load canonical milestone execution ledger."
        ) from exc

    if not isinstance(value, dict):
        raise ValueError("Canonical ledger JSON must contain an object.")

    return milestone_execution_ledger_from_dict(value)


def save_milestone_execution_ledger(
    ledger: MilestoneExecutionLedger,
) -> None:
    validate_milestone_execution_ledger(ledger)

    project_root = PROJECT_ROOT
    context_dir = project_root / "context"
    canonical_path = (
        context_dir / "RESEARCH_ENGINE_MILESTONE_EXECUTION_LEDGER.json"
    )
    expected_path = Path(MILESTONE_EXECUTION_LEDGER_PATH)

    if canonical_path != expected_path:
        raise RuntimeError("Ledger target is not the exact canonical path.")

    if not context_dir.exists():
        raise RuntimeError("Canonical context directory does not exist.")

    if not context_dir.is_dir():
        raise RuntimeError("Canonical context path is not a directory.")

    try:
        if context_dir.resolve(strict=True) != context_dir:
            raise RuntimeError(
                "Canonical context directory resolves to a different path."
            )
    except OSError as exc:
        raise RuntimeError(
            "Unable to verify canonical context directory."
        ) from exc

    if canonical_path.exists():
        if not canonical_path.is_file():
            raise RuntimeError("Canonical ledger target is not a regular file.")
        try:
            if canonical_path.resolve(strict=True) != canonical_path:
                raise RuntimeError(
                    "Canonical ledger target resolves to a different path."
                )
        except OSError as exc:
            raise RuntimeError(
                "Unable to verify canonical ledger target."
            ) from exc

    payload = (
        json.dumps(
            milestone_execution_ledger_to_dict(ledger),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    temporary_path: Path | None = None

    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=".research_engine_milestone_execution_ledger.",
            suffix=".tmp",
            dir=str(context_dir),
        )
        temporary_path = Path(temporary_name)

        with os.fdopen(
            file_descriptor,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary_path, canonical_path)
        temporary_path = None

    except OSError as exc:
        raise RuntimeError(
            "Unable to save canonical milestone execution ledger."
        ) from exc

    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass