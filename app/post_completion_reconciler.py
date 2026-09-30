from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from app.git_workspace_status import inspect_git_workspace_status
from app.milestone_execution_ledger import (
    MilestoneExecutionLedger,
    load_milestone_execution_ledger,
    save_milestone_execution_ledger,
)
from app.roadmap_store import (
    load_project_roadmap,
    save_project_roadmap,
)
from app.workspace_registry import get_workspace_profile


PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = PROJECT_ROOT / "pending_patches"


@dataclass(frozen=True)
class PostCompletionReconciliation:
    changed: bool
    completed_step_id: str | None
    next_step_id: str | None
    milestone_completed: bool
    reason: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_patch_record(patch_id: str) -> dict[str, object]:
    path = QUEUE_DIR / f"{patch_id}.json"

    if not path.is_file():
        raise RuntimeError(
            f"Ledger patch record does not exist: {patch_id}"
        )

    value = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(value, dict):
        raise RuntimeError(
            f"Patch record must contain an object: {patch_id}"
        )

    return value


def record_patch_for_active_step(
    patch_id: str,
) -> bool:
    if not isinstance(patch_id, str) or not patch_id.strip():
        raise RuntimeError("patch_id must be a non-empty string.")

    ledger = load_milestone_execution_ledger()

    if ledger is None:
        return False

    in_progress = [
        step
        for step in ledger.steps
        if step.status == "IN_PROGRESS"
    ]

    if len(in_progress) > 1:
        raise RuntimeError(
            "Canonical ledger contains multiple IN_PROGRESS steps."
        )

    if in_progress:
        active = in_progress[0]
    else:
        active = next(
            (
                step
                for step in ledger.steps
                if step.status == "PLANNED"
            ),
            None,
        )

    if active is None:
        return False

    if patch_id in active.patch_ids:
        return False

    updated_steps = tuple(
        replace(
            step,
            status=(
                "IN_PROGRESS"
                if step.step_id == active.step_id
                else step.status
            ),
            patch_ids=(
                step.patch_ids + (patch_id,)
                if step.step_id == active.step_id
                else step.patch_ids
            ),
        )
        for step in ledger.steps
    )

    save_milestone_execution_ledger(
        replace(
            ledger,
            steps=updated_steps,
        )
    )

    return True


def _patch_is_committed_and_verified(
    *,
    workspace_name: str,
    patch_id: str,
    dirty_paths: frozenset[str],
) -> bool:
    record = _load_patch_record(patch_id)

    if record.get("status") != "APPLIED":
        return False

    post_apply = record.get("post_apply")
    if (
        not isinstance(post_apply, dict)
        or post_apply.get("validated") is not True
    ):
        return False

    candidate_sha = record.get("candidate_sha256")
    applied_sha = record.get("applied_sha256")
    target_file = record.get("target_file")

    if (
        not isinstance(candidate_sha, str)
        or not isinstance(applied_sha, str)
        or candidate_sha != applied_sha
        or not isinstance(target_file, str)
        or not target_file
    ):
        return False

    normalized_target = target_file.replace("\\", "/")

    if normalized_target in dirty_paths:
        return False

    workspace = get_workspace_profile(workspace_name)
    target = workspace.path / normalized_target

    if not target.is_file():
        return False

    return _sha256(target) == candidate_sha


def reconcile_completed_execution_step(
    workspace_name: str,
) -> PostCompletionReconciliation:
    ledger = load_milestone_execution_ledger()

    if ledger is None:
        return PostCompletionReconciliation(
            changed=False,
            completed_step_id=None,
            next_step_id=None,
            milestone_completed=False,
            reason="Canonical execution ledger is absent.",
        )

    in_progress = [
        step
        for step in ledger.steps
        if step.status == "IN_PROGRESS"
    ]

    if len(in_progress) != 1:
        return PostCompletionReconciliation(
            changed=False,
            completed_step_id=None,
            next_step_id=None,
            milestone_completed=False,
            reason="Exactly one IN_PROGRESS ledger step is required.",
        )

    current = in_progress[0]

    if not current.patch_ids:
        return PostCompletionReconciliation(
            changed=False,
            completed_step_id=None,
            next_step_id=None,
            milestone_completed=False,
            reason="Active ledger step has no recorded patches.",
        )

    git_status = inspect_git_workspace_status(
        workspace_name
    )

    dirty_paths = frozenset(
        path.replace("\\", "/")
        for path in (
            tuple(git_status.tracked_modified)
            + tuple(git_status.untracked)
            + tuple(git_status.staged)
            + tuple(git_status.conflicted)
        )
    )

    for patch_id in current.patch_ids:
        if not _patch_is_committed_and_verified(
            workspace_name=workspace_name,
            patch_id=patch_id,
            dirty_paths=dirty_paths,
        ):
            return PostCompletionReconciliation(
                changed=False,
                completed_step_id=None,
                next_step_id=None,
                milestone_completed=False,
                reason=(
                    "Active step does not yet have fully applied, "
                    "verified, clean Git checkpoint evidence."
                ),
            )

    next_step = next(
        (
            step
            for step in ledger.steps
            if step.status == "PLANNED"
        ),
        None,
    )

    updated_steps = tuple(
        replace(
            step,
            status=(
                "COMPLETED"
                if step.step_id == current.step_id
                else (
                    "IN_PROGRESS"
                    if (
                        next_step is not None
                        and step.step_id == next_step.step_id
                    )
                    else step.status
                )
            ),
        )
        for step in ledger.steps
    )

    updated_ledger = replace(
        ledger,
        steps=updated_steps,
    )

    save_milestone_execution_ledger(
        updated_ledger
    )

    milestone_completed = all(
        step.status in {
            "COMPLETED",
            "SUPERSEDED",
        }
        for step in updated_ledger.steps
    )

    if milestone_completed:
        roadmap = load_project_roadmap(
            workspace_name
        )

        matching = [
            node
            for node in roadmap.nodes
            if node.node_id == ledger.milestone_id
        ]

        if len(matching) != 1:
            raise RuntimeError(
                "Canonical roadmap milestone does not resolve uniquely."
            )

        completed_at = datetime.now(
            timezone.utc
        ).isoformat()

        final_patch_id = current.patch_ids[-1]

        current_index = next(
            index
            for index, node in enumerate(roadmap.nodes)
            if node.node_id == ledger.milestone_id
        )

        next_milestone = next(
            (
                node
                for node in roadmap.nodes[current_index + 1 :]
                if node.kind == "MILESTONE"
            ),
            None,
        )

        activate_next_milestone_id = None

        if (
            next_milestone is not None
            and next_milestone.status == "NOT_STARTED"
            and next_milestone.verification_status == "PENDING"
            and next_milestone.patch_id is None
            and next_milestone.completed_at is None
        ):
            dependencies_ready = all(
                any(
                    dependency.node_id == dependency_id
                    and dependency.kind == "MILESTONE"
                    and dependency.status == "COMPLETED"
                    and dependency.verification_status == "PASSED"
                    for dependency in roadmap.nodes
                )
                for dependency_id in next_milestone.dependencies
            )

            if dependencies_ready:
                activate_next_milestone_id = (
                    next_milestone.node_id
                )

        updated_nodes = tuple(
            replace(
                node,
                status="COMPLETED",
                verification_status="PASSED",
                patch_id=final_patch_id,
                completed_at=completed_at,
            )
            if node.node_id == ledger.milestone_id
            else (
                replace(
                    node,
                    status="IN_PROGRESS",
                )
                if (
                    activate_next_milestone_id is not None
                    and node.node_id
                    == activate_next_milestone_id
                )
                else node
            )
            for node in roadmap.nodes
        )

        save_project_roadmap(
            replace(
                roadmap,
                nodes=updated_nodes,
            )
        )

    return PostCompletionReconciliation(
        changed=True,
        completed_step_id=current.step_id,
        next_step_id=(
            next_step.step_id
            if next_step is not None
            else None
        ),
        milestone_completed=milestone_completed,
        reason=(
            "Verified committed patch evidence reconciled "
            "canonical execution state."
        ),
    )
