from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


WorkspaceAccessMode = Literal[
    "HUMAN_APPROVED_PATCH_ONLY",
    "READ_ONLY",
]


@dataclass(frozen=True)
class WorkspaceProfile:
    name: str
    path: Path
    role: str
    access_mode: WorkspaceAccessMode


@dataclass(frozen=True)
class ActiveWorkspaceSelection:
    workspace: WorkspaceProfile
    requested_name: str
    writable_via_dev_agent: bool
    reason: str


@dataclass(frozen=True)
class WorkspaceStructureSnapshot:
    workspace: WorkspaceProfile
    exists: bool
    is_directory: bool
    top_level_entries: tuple[str, ...]
    inspected: bool
    reason: str


WORKSPACE_PROFILES: tuple[WorkspaceProfile, ...] = (
    WorkspaceProfile(
        name="world-os-dev-agent",
        path=Path(
            r"C:\Users\matej\Documents\world-os-dev-agent"
        ),
        role="World OS development control plane",
        access_mode="HUMAN_APPROVED_PATCH_ONLY",
    ),
    WorkspaceProfile(
        name="world-os-research-engine",
        path=Path(
            r"C:\Users\matej\Documents\world-os-research-engine"
        ),
        role="World OS research and structured data-ingestion engine",
        access_mode="READ_ONLY",
    ),
    WorkspaceProfile(
        name="world-os-web",
        path=Path(
            r"C:\Users\matej\Documents\world-os-web"
        ),
        role="World OS web interface and visualization layer",
        access_mode="READ_ONLY",
    ),
)


def registered_workspace_names() -> tuple[str, ...]:
    return tuple(
        profile.name
        for profile in WORKSPACE_PROFILES
    )


def get_workspace_profile(
    name: str,
) -> WorkspaceProfile:
    normalized = name.strip().casefold()

    if not normalized:
        raise RuntimeError(
            "Workspace name is empty."
        )

    for profile in WORKSPACE_PROFILES:
        if profile.name.casefold() == normalized:
            return profile

    raise RuntimeError(
        f"Unknown workspace: {name!r}"
    )


def _selection_for_profile(
    profile: WorkspaceProfile,
    requested_name: str,
) -> ActiveWorkspaceSelection:
    if profile.access_mode == "HUMAN_APPROVED_PATCH_ONLY":
        return ActiveWorkspaceSelection(
            workspace=profile,
            requested_name=requested_name,
            writable_via_dev_agent=True,
            reason=(
                "Writes are permitted only through the existing "
                "HUMAN_APPROVED_PATCH_ONLY workflow."
            ),
        )

    return ActiveWorkspaceSelection(
        workspace=profile,
        requested_name=requested_name,
        writable_via_dev_agent=False,
        reason=(
            "Workspace access is READ_ONLY; Dev Agent writes are not "
            "permitted."
        ),
    )


def select_active_workspace(
    name: str,
) -> ActiveWorkspaceSelection:
    profile = get_workspace_profile(name)

    return _selection_for_profile(
        profile,
        name,
    )


def inspect_workspace_structure(
    name: str,
    *,
    max_entries: int = 50,
) -> WorkspaceStructureSnapshot:
    if not 1 <= max_entries <= 200:
        raise RuntimeError(
            "max_entries must be between 1 and 200 inclusive."
        )

    selection = select_active_workspace(name)
    workspace = selection.workspace
    path = workspace.path

    if not path.exists():
        return WorkspaceStructureSnapshot(
            workspace=workspace,
            exists=False,
            is_directory=False,
            top_level_entries=(),
            inspected=False,
            reason="Registered workspace path does not exist.",
        )

    if not path.is_dir():
        raise RuntimeError(
            f"Registered workspace path is not a directory: {path}"
        )

    try:
        entries = tuple(
            sorted(
                entry.name
                for entry in path.iterdir()
            )[:max_entries]
        )
    except OSError as exc:
        raise RuntimeError(
            f"Unable to inspect registered workspace directory: {path}"
        ) from exc

    return WorkspaceStructureSnapshot(
        workspace=workspace,
        exists=True,
        is_directory=True,
        top_level_entries=entries,
        inspected=True,
        reason="Top-level workspace structure inspected.",
    )


def _normalize_workspace_path(
    path: str | Path,
) -> str:
    raw = str(
        Path(path)
    )

    normalized = raw.replace(
        "/",
        "\\",
    ).rstrip(
        "\\"
    )

    return normalized.casefold()


def workspace_for_path(
    path: str | Path,
) -> WorkspaceProfile:
    candidate = _normalize_workspace_path(
        path
    )

    for profile in WORKSPACE_PROFILES:
        if candidate == _normalize_workspace_path(
            profile.path
        ):
            return profile

    raise RuntimeError(
        f"Path is not a registered workspace: {path}"
    )


def active_workspace_from_path(
    path: str | Path,
) -> ActiveWorkspaceSelection:
    profile = workspace_for_path(path)

    return _selection_for_profile(
        profile,
        profile.name,
    )


def active_dev_workspace() -> WorkspaceProfile:
    return get_workspace_profile(
        "world-os-dev-agent"
    )