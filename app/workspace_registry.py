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
    write_workflow_verified: bool = False


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
        write_workflow_verified=True,
    ),
    WorkspaceProfile(
        name="world-os-research-engine",
        path=Path(
            r"C:\Users\matej\Documents\world-os-research-engine"
        ),
        role="World OS research and structured data-ingestion engine",
        access_mode="HUMAN_APPROVED_PATCH_ONLY",
        write_workflow_verified=True,
    ),
    WorkspaceProfile(
        name="world-os-web",
        path=Path(
            r"C:\Users\matej\Documents\world-os-web"
        ),
        role="World OS web interface and visualization layer",
        access_mode="READ_ONLY",
        write_workflow_verified=False,
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


def require_verified_patch_workspace(
    workspace_name: str,
) -> WorkspaceProfile:
    workspace = get_workspace_profile(
        workspace_name
    )

    if workspace.access_mode != "HUMAN_APPROVED_PATCH_ONLY":
        raise RuntimeError(
            "Workspace is not configured for human-approved patches."
        )

    if not workspace.write_workflow_verified:
        raise RuntimeError(
            "Workspace-bound human-approved patch workflow is not "
            "implemented and verified."
        )

    return workspace


def resolve_workspace_python_target(
    workspace_name: str,
    target_file: str,
    *,
    must_exist: bool = True,
    allow_existing_test_script: bool = False,
) -> Path:
    """
    Resolve a safe workspace-relative Python source target.

    This function validates target scope only. It does not authorize a patch,
    approval, or write. Callers entering a write workflow must separately call
    require_verified_patch_workspace().
    """
    workspace = get_workspace_profile(
        workspace_name
    )

    if not isinstance(target_file, str):
        raise RuntimeError(
            "Target file must be a string."
        )

    normalized = target_file.replace(
        "\\",
        "/",
    ).strip()

    if not normalized:
        raise RuntimeError(
            "Target file is empty."
        )

    target_path = Path(normalized)

    if target_path.is_absolute():
        raise RuntimeError(
            "Target path must be workspace-relative."
        )

    parts = tuple(
        part
        for part in normalized.split("/")
        if part
    )

    if not parts:
        raise RuntimeError(
            "Target file is empty."
        )

    if any(part in {".", ".."} for part in parts):
        raise RuntimeError(
            "Target path may not contain traversal segments."
        )

    lowered_parts = tuple(
        part.casefold()
        for part in parts
    )
    filename = lowered_parts[-1]

    if any(
        part == ".git"
        or part.startswith(".env")
        or part in {
            "supabase",
            "migrations",
            ".temp",
            "database",
            "db",
        }
        for part in lowered_parts
    ):
        raise RuntimeError(
            "Sensitive, Git, database, or Supabase paths are not permitted."
        )

    if filename.endswith((
        ".env",
        ".env.local",
        ".env.development",
        ".env.test",
        ".env.production",
    )):
        raise RuntimeError(
            "Environment files are not permitted."
        )

    if any(
        part in {
            "git",
            "gitignore",
            "gitattributes",
            "gitmodules",
        }
        for part in lowered_parts
    ):
        raise RuntimeError(
            "Git control files are not permitted."
        )

    if (
        allow_existing_test_script
        and must_exist
        and len(parts) == 2
        and lowered_parts[0] == "scripts"
        and filename.startswith("test_")
        and filename.endswith(".py")
    ):
        workspace_root = workspace.path.resolve()
        scripts_root = (workspace_root / "scripts").resolve()
        target = (workspace_root / Path(*parts)).resolve()

        try:
            scripts_root.relative_to(workspace_root)
            target.relative_to(scripts_root)
        except ValueError as exc:
            raise RuntimeError(
                "Test script target escapes the registered workspace "
                "scripts directory."
            ) from exc

        if not target.exists():
            raise RuntimeError(
                "Target file does not exist."
            )

        if not target.is_file():
            raise RuntimeError(
                "Target path is not a regular file."
            )

        return target

    if not normalized.casefold().startswith("app/"):
        raise RuntimeError(
            "Target must be inside app/."
        )

    if not normalized.casefold().endswith(".py"):
        raise RuntimeError(
            "Target must be a Python file."
        )

    workspace_root = workspace.path.resolve()
    app_root = (workspace_root / "app").resolve()
    target = (workspace_root / Path(*parts)).resolve()

    try:
        app_root.relative_to(workspace_root)
        target.relative_to(app_root)
    except ValueError as exc:
        raise RuntimeError(
            "Target escapes the registered workspace app directory."
        ) from exc

    if must_exist:
        if not target.exists():
            raise RuntimeError(
                "Target file does not exist."
            )

        if not target.is_file():
            raise RuntimeError(
                "Target path is not a regular file."
            )

        return target

    if not target.parent.exists():
        raise RuntimeError(
            "Target parent directory does not exist."
        )

    if not target.parent.is_dir():
        raise RuntimeError(
            "Target parent path is not a directory."
        )

    return target


def _selection_for_profile(
    profile: WorkspaceProfile,
    requested_name: str,
) -> ActiveWorkspaceSelection:
    if profile.access_mode == "HUMAN_APPROVED_PATCH_ONLY":
        if not profile.write_workflow_verified:
            return ActiveWorkspaceSelection(
                workspace=profile,
                requested_name=requested_name,
                writable_via_dev_agent=False,
                reason=(
                    "Workspace-bound human-approved patch workflow is not "
                    "implemented and verified; access remains READ_ONLY."
                ),
            )

        return ActiveWorkspaceSelection(
            workspace=profile,
            requested_name=requested_name,
            writable_via_dev_agent=True,
            reason=(
                "Writes are permitted only through the verified "
                "HUMAN_APPROVED_PATCH_ONLY workflow, including explicit "
                "approval, integrity validation, backup, and rollback "
                "safeguards."
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