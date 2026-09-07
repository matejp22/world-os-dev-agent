from __future__ import annotations

import subprocess
from dataclasses import dataclass

from app.workspace_registry import get_workspace_profile


@dataclass(frozen=True)
class GitWorkspaceStatus:
    workspace_name: str
    workspace_path: str
    branch: str
    tracked_modified: tuple[str, ...]
    untracked: tuple[str, ...]
    staged: tuple[str, ...]
    conflicted: tuple[str, ...]
    clean: bool
    inspected: bool
    reason: str


@dataclass(frozen=True)
class GitActionPlan:
    workspace_name: str
    branch: str
    files_to_stage: tuple[str, ...]
    commit_message: str
    add_command: tuple[str, ...]
    commit_command: tuple[str, ...]
    push_command: tuple[str, ...]
    requires_human_approval: bool
    executable: bool
    blocked: bool
    reason: str


_CONFLICT_CODES = frozenset(
    {
        "DD",
        "AU",
        "UD",
        "UA",
        "DU",
        "AA",
        "UU",
    }
)


def _run_git(
    args: list[str],
    *,
    cwd: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )


def _parse_porcelain_v1(
    output: str,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    tracked_modified: set[str] = set()
    untracked: set[str] = set()
    staged: set[str] = set()
    conflicted: set[str] = set()

    for raw_line in output.splitlines():
        if not raw_line:
            continue

        if len(raw_line) < 3:
            raise RuntimeError(
                f"Unexpected git status porcelain line: {raw_line!r}"
            )

        code = raw_line[:2]
        path = raw_line[3:]

        if not path:
            raise RuntimeError(
                f"Missing path in git status porcelain line: {raw_line!r}"
            )

        if code == "??":
            untracked.add(path)
            continue

        if code in _CONFLICT_CODES:
            conflicted.add(path)
            continue

        index_status = code[0]
        worktree_status = code[1]

        if index_status != " ":
            staged.add(path)

        if worktree_status != " ":
            tracked_modified.add(path)

    return (
        tuple(sorted(tracked_modified)),
        tuple(sorted(untracked)),
        tuple(sorted(staged)),
        tuple(sorted(conflicted)),
    )


def inspect_git_workspace_status(
    name: str,
) -> GitWorkspaceStatus:
    workspace = get_workspace_profile(name)

    branch_result = _run_git(
        [
            "git",
            "branch",
            "--show-current",
        ],
        cwd=str(workspace.path),
    )

    if branch_result.returncode != 0:
        raise RuntimeError(
            "Git branch inspection failed: "
            + (
                branch_result.stderr.strip()
                or branch_result.stdout.strip()
                or "<no output>"
            )
        )

    status_result = _run_git(
        [
            "git",
            "status",
            "--porcelain=v1",
        ],
        cwd=str(workspace.path),
    )

    if status_result.returncode != 0:
        raise RuntimeError(
            "Git status inspection failed: "
            + (
                status_result.stderr.strip()
                or status_result.stdout.strip()
                or "<no output>"
            )
        )

    (
        tracked_modified,
        untracked,
        staged,
        conflicted,
    ) = _parse_porcelain_v1(
        status_result.stdout
    )

    clean = not (
        tracked_modified
        or untracked
        or staged
        or conflicted
    )

    return GitWorkspaceStatus(
        workspace_name=workspace.name,
        workspace_path=str(workspace.path),
        branch=branch_result.stdout.strip(),
        tracked_modified=tracked_modified,
        untracked=untracked,
        staged=staged,
        conflicted=conflicted,
        clean=clean,
        inspected=True,
        reason=(
            "Read-only Git inspection using branch --show-current "
            "and status --porcelain=v1."
        ),
    )


def plan_git_actions(
    status: GitWorkspaceStatus,
    files: tuple[str, ...],
    commit_message: str,
) -> GitActionPlan:
    if not status.inspected:
        raise RuntimeError(
            "Git action planning requires an inspected workspace status."
        )

    if status.conflicted:
        raise RuntimeError(
            "Git action planning is blocked by conflicted files: "
            + ", ".join(sorted(status.conflicted))
        )

    if not files:
        raise RuntimeError(
            "At least one file is required for Git action planning."
        )

    normalized_message = commit_message.strip()
    if not normalized_message:
        raise RuntimeError(
            "Commit message must be non-empty after stripping whitespace."
        )

    conflicted = set(status.conflicted)
    available = (
        set(status.tracked_modified)
        | set(status.untracked)
        | set(status.staged)
    )
    requested = set(files)

    if "." in requested:
        raise RuntimeError(
            "Broad file target '.' is not permitted."
        )

    invalid = sorted(requested - available)
    if invalid:
        raise RuntimeError(
            "Requested files are not present in the inspected Git status: "
            + ", ".join(invalid)
        )

    selected = tuple(
        sorted(
            requested - conflicted
        )
    )

    if not selected:
        raise RuntimeError(
            "No non-conflicted files remain after validation."
        )

    reason = (
        "File-scoped staging only; no git add .; add/commit/push require "
        "explicit human approval; this plan is non-executing."
    )

    return GitActionPlan(
        workspace_name=status.workspace_name,
        branch=status.branch,
        files_to_stage=selected,
        commit_message=normalized_message,
        add_command=(
            "git",
            "add",
            "--",
            *selected,
        ),
        commit_command=(
            "git",
            "commit",
            "-m",
            normalized_message,
        ),
        push_command=(
            "git",
            "push",
            "origin",
            status.branch,
        ),
        requires_human_approval=True,
        executable=False,
        blocked=False,
        reason=reason,
    )