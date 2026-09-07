from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.workspace_registry import (
    get_workspace_profile,
)


CIStatus = Literal[
    "PASS",
    "FAIL",
    "UNKNOWN",
    "NOT_CONFIGURED",
]

CIProvider = Literal[
    "GITHUB_ACTIONS",
    "UNKNOWN",
    "NONE",
]


@dataclass(frozen=True)
class CIConfiguration:
    workspace_name: str
    workspace_path: str
    provider: CIProvider
    configured: bool
    workflow_files: tuple[str, ...]
    inspected: bool
    reason: str


@dataclass(frozen=True)
class CIResult:
    source: str
    status: CIStatus
    provider: CIProvider
    external: bool
    observed: bool
    reason: str


@dataclass(frozen=True)
class CIAwarenessSnapshot:
    configuration: CIConfiguration
    external_result: CIResult
    inspected: bool
    reason: str


def inspect_ci_configuration(
    workspace_name: str,
    *,
    max_workflows: int = 50,
) -> CIConfiguration:
    if not isinstance(max_workflows, int):
        raise RuntimeError(
            "max_workflows must be an integer."
        )

    if max_workflows < 1 or max_workflows > 200:
        raise RuntimeError(
            "max_workflows must be between 1 and 200."
        )

    workspace = get_workspace_profile(
        workspace_name
    )

    github_dir = (
        workspace.path
        / ".github"
    )

    workflow_dir = (
        github_dir
        / "workflows"
    )

    if not github_dir.exists():
        return CIConfiguration(
            workspace_name=workspace.name,
            workspace_path=str(workspace.path),
            provider="NONE",
            configured=False,
            workflow_files=(),
            inspected=True,
            reason=(
                "No .github directory exists in the registered "
                "workspace. External CI is not configured."
            ),
        )

    if not workflow_dir.exists():
        return CIConfiguration(
            workspace_name=workspace.name,
            workspace_path=str(workspace.path),
            provider="NONE",
            configured=False,
            workflow_files=(),
            inspected=True,
            reason=(
                ".github exists but .github/workflows does not. "
                "GitHub Actions CI is not configured."
            ),
        )

    if not workflow_dir.is_dir():
        raise RuntimeError(
            ".github/workflows exists but is not a directory."
        )

    workflow_paths = tuple(
        sorted(
            (
                path
                for path in workflow_dir.iterdir()
                if path.is_file()
                and path.suffix.casefold() in {
                    ".yml",
                    ".yaml",
                }
            ),
            key=lambda path: path.name.casefold(),
        )
    )

    if len(workflow_paths) > max_workflows:
        raise RuntimeError(
            "Workflow count exceeds bounded max_workflows."
        )

    relative_workflows = tuple(
        path
        .relative_to(workspace.path)
        .as_posix()
        for path in workflow_paths
    )

    if not relative_workflows:
        return CIConfiguration(
            workspace_name=workspace.name,
            workspace_path=str(workspace.path),
            provider="NONE",
            configured=False,
            workflow_files=(),
            inspected=True,
            reason=(
                ".github/workflows exists but contains no YAML "
                "workflow files. External CI is not configured."
            ),
        )

    return CIConfiguration(
        workspace_name=workspace.name,
        workspace_path=str(workspace.path),
        provider="GITHUB_ACTIONS",
        configured=True,
        workflow_files=relative_workflows,
        inspected=True,
        reason=(
            "GitHub Actions workflow configuration detected "
            "read-only from .github/workflows."
        ),
    )


def derive_external_ci_result(
    configuration: CIConfiguration,
) -> CIResult:
    if not configuration.inspected:
        raise RuntimeError(
            "CI configuration must be inspected first."
        )

    if not configuration.configured:
        return CIResult(
            source="external_ci",
            status="NOT_CONFIGURED",
            provider=configuration.provider,
            external=True,
            observed=False,
            reason=(
                "No external CI configuration is present in "
                "the repository."
            ),
        )

    return CIResult(
        source="external_ci",
        status="UNKNOWN",
        provider=configuration.provider,
        external=True,
        observed=False,
        reason=(
            "External CI is configured, but no CI run result "
            "has been observed by the Dev Agent."
        ),
    )


def inspect_ci_awareness(
    workspace_name: str,
) -> CIAwarenessSnapshot:
    configuration = inspect_ci_configuration(
        workspace_name
    )

    external_result = derive_external_ci_result(
        configuration
    )

    return CIAwarenessSnapshot(
        configuration=configuration,
        external_result=external_result,
        inspected=True,
        reason=(
            "Deterministic read-only CI awareness snapshot. "
            "Repository configuration was inspected locally; "
            "no network request, workflow execution, CI action, "
            "Git action, or repository mutation was performed."
        ),
    )
