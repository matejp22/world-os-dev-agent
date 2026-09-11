from __future__ import annotations

from pathlib import Path

from app.workspace_registry import get_workspace_profile


_ALLOWED_DIRECTORY_NAMES = frozenset(
    {
        "master_roadmaps",
        "project_roadmaps",
    }
)


def resolve_roadmap_data_target(
    workspace_name: str,
    target_file: str,
    *,
    must_exist: bool,
) -> Path:
    """Resolve an allowed roadmap JSON target without performing writes."""
    if not isinstance(workspace_name, str) or not workspace_name.strip():
        raise RuntimeError(
            "workspace_name must be a non-empty string."
        )

    workspace = get_workspace_profile(workspace_name)

    if workspace.name != "world-os-dev-agent":
        raise RuntimeError(
            "Roadmap data targets are only permitted in "
            "world-os-dev-agent."
        )

    if not isinstance(target_file, str) or not target_file.strip():
        raise RuntimeError(
            "target_file must be a non-empty string."
        )

    normalized = target_file.replace("\\", "/").strip()

    if not normalized:
        raise RuntimeError(
            "target_file must be a non-empty string."
        )

    candidate = Path(normalized)

    if candidate.is_absolute() or normalized.startswith("/"):
        raise RuntimeError(
            "Target path must be workspace-relative."
        )

    parts = tuple(normalized.split("/"))

    if not parts or any(not part for part in parts):
        raise RuntimeError(
            "Target path contains empty path components."
        )

    if any(part in {".", ".."} for part in parts):
        raise RuntimeError(
            "Target path may not contain traversal segments."
        )

    if len(parts) != 3:
        raise RuntimeError(
            "Target must be a direct child of an allowed roadmap directory."
        )

    if parts[0].casefold() != "context":
        raise RuntimeError(
            "Target must be inside context/."
        )

    directory_name = parts[1].casefold()

    if directory_name not in _ALLOWED_DIRECTORY_NAMES:
        raise RuntimeError(
            "Target directory is not an allowed roadmap directory."
        )

    filename = parts[2]

    if not filename.strip():
        raise RuntimeError(
            "Target filename must be non-empty."
        )

    if not filename.casefold().endswith(".json"):
        raise RuntimeError(
            "Target filename must end with .json."
        )

    workspace_root = workspace.path.resolve()
    context_root = (workspace_root / "context").resolve()
    allowed_parent = (
        context_root / directory_name
    ).resolve()
    target = (allowed_parent / filename).resolve()

    try:
        context_root.relative_to(workspace_root)
        allowed_parent.relative_to(workspace_root)
        target.relative_to(allowed_parent)
    except ValueError as exc:
        raise RuntimeError(
            "Roadmap target escapes the registered workspace scope."
        ) from exc

    if not allowed_parent.exists():
        raise RuntimeError(
            "Allowed roadmap directory does not exist."
        )

    if not allowed_parent.is_dir():
        raise RuntimeError(
            "Allowed roadmap path is not a directory."
        )

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

    if target.exists() and not target.is_file():
        raise RuntimeError(
            "Target path is not a regular file."
        )

    return target