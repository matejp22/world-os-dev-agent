from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from app.ai_build_planner import plan_next_build
from app.build_patch_orchestrator import BuildPatchResult, run_build_patch
from app.ci_awareness import inspect_ci_awareness
from app.compile_checks import (
    execute_compile_checks,
    plan_compile_checks,
)
from app.dev_task_state import (
    execute_task_state_transition,
    load_resolved_task_state,
    plan_task_state_transition,
)
from app.git_workspace_status import inspect_git_workspace_status
from app.output_sanitizer import sanitize_output
from app.test_execution import (
    BLOCKED_TEST_IDS,
    execute_registered_tests,
)
from app.test_registry import (
    inspect_repository_test_registry,
    plan_test_selection,
)
from app.workspace_registry import (
    active_workspace_from_path,
    inspect_workspace_structure,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
NO_NEW_MILESTONE = "NO_NEW_MILESTONE"


def _extract_planned_objective(
    planner_output: str,
) -> str:
    clean = planner_output.strip()

    if clean == NO_NEW_MILESTONE:
        raise RuntimeError(
            "Build planner reported NO_NEW_MILESTONE."
        )

    match = re.fullmatch(
        r"NEXT_OBJECTIVE:\s*\n"
        r"(?P<objective>.+?)"
        r"\n\nWHY:\s*\n"
        r"(?P<why>.+)",
        clean,
        flags=re.DOTALL,
    )

    if match is None:
        raise RuntimeError(
            "Build planner output does not match the expected contract."
        )

    objective = match.group(
        "objective"
    ).strip()

    if not objective:
        raise RuntimeError(
            "Build planner returned an empty objective."
        )

    return objective


def _print_next_action_handoff(
    *,
    patch_result: BuildPatchResult,
) -> None:
    print("NEXT BOUNDED DEVELOPMENT ACTION")
    print("-" * 72)

    if patch_result.status == "READY_FOR_HUMAN_REVIEW":
        print(
            "Review the queued patch in the Developer Console. "
            "Human approval is required before apply."
        )
    elif patch_result.status == "REJECTED":
        print(
            "Inspect the semantic rejection and revise only through "
            "the bounded human-controlled workflow."
        )
    else:
        print(
            "Inspect the draft patch and validation result before any "
            "further action."
        )

    print(
        "No approval, apply, Git, database, or Supabase action "
        "was performed."
    )
    print()


def _build_canonical_bounded_goal(
    *,
    active_milestone: str,
    persistent_objective: str,
    selected_objective: str,
    developer_instruction: str,
    sanitized_investigation: str,
    validation_summary: str,
    rejected_objective: str | None = None,
    semantic_rejection_review: str | None = None,
) -> str:
    required_values = {
        "active milestone": active_milestone,
        "persistent objective": persistent_objective,
        "selected objective": selected_objective,
    }

    for label, value in required_values.items():
        if not value.strip():
            raise RuntimeError(
                f"Canonical bounded goal requires {label}."
            )

    parts = [
        "CANONICAL ACTIVE MILESTONE:",
        active_milestone.strip(),
        "",
        "CANONICAL PERSISTENT MILESTONE OBJECTIVE:",
        persistent_objective.strip(),
        "",
        "SELECTED BOUNDED OBJECTIVE:",
        selected_objective.strip(),
        "",
        "DEVELOPER INSTRUCTION:",
        developer_instruction.strip(),
    ]

    if rejected_objective is not None:
        parts.extend(
            [
                "",
                "PREVIOUSLY REJECTED OBJECTIVE:",
                rejected_objective.strip(),
            ]
        )

    if semantic_rejection_review is not None:
        parts.extend(
            [
                "",
                "SEMANTIC REJECTION REVIEW:",
                semantic_rejection_review.strip(),
            ]
        )

    parts.extend(
        [
            "",
            "SANITIZED READ-ONLY INVESTIGATION OUTPUT:",
            sanitized_investigation,
            "",
            validation_summary,
            "",
            "BOUNDARY:",
            (
                "Implement only the selected bounded objective inside the "
                "canonical active milestone and persistent objective. "
                "Do not reinterpret or escape those boundaries. "
                "No approval, apply, Git write, database write, Supabase "
                "write, or production write is authorized."
            ),
        ]
    )

    return "\n".join(parts)


def _run_bounded_build_cycle(
    *,
    cycle_label: str,
    planner_instruction: str,
    active_milestone: str,
    persistent_objective: str,
    developer_instruction: str,
    workspace_selection,
    rejected_objective: str | None = None,
    semantic_rejection_review: str | None = None,
) -> tuple[str, BuildPatchResult]:
    planner_output = plan_next_build(
        planner_instruction,
        active_milestone=active_milestone,
        active_objective=persistent_objective,
    )

    selected_objective = _extract_planned_objective(
        planner_output
    )

    print(f"{cycle_label} OBJECTIVE")
    print("-" * 72)
    print(selected_objective)
    print()

    print(f"{cycle_label} READ-ONLY INVESTIGATION")
    print("-" * 72)

    investigation_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.autonomous_runner",
            "--goal",
            selected_objective,
            "--repo",
            str(workspace_selection.workspace.path),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    investigation_output = "\n".join(
        part
        for part in (
            investigation_result.stdout,
            investigation_result.stderr,
        )
        if part
    )

    sanitized_investigation = sanitize_output(
        investigation_output
    )

    if sanitized_investigation:
        print(
            sanitized_investigation.rstrip()
        )

    print()

    if investigation_result.returncode != 0:
        raise RuntimeError(
            f"{cycle_label} investigation failed with "
            f"return code {investigation_result.returncode}."
        )

    validation_summary = (
        _run_v20_test_compile_ci_validation(
            workspace_selection
        )
    )

    bounded_goal = _build_canonical_bounded_goal(
        active_milestone=active_milestone,
        persistent_objective=persistent_objective,
        selected_objective=selected_objective,
        developer_instruction=developer_instruction,
        sanitized_investigation=sanitized_investigation,
        validation_summary=validation_summary,
        rejected_objective=rejected_objective,
        semantic_rejection_review=semantic_rejection_review,
    )

    print(f"{cycle_label} BUILD PATCH")
    print("-" * 72)

    patch_result = run_build_patch(
        bounded_goal,
        workspace_name=workspace_selection.workspace.name,
    )

    _validate_build_patch_result(
        patch_result
    )

    _print_patch_metadata(
        patch_result
    )

    _print_next_action_handoff(
        patch_result=patch_result,
    )

    return (
        selected_objective,
        patch_result,
    )


def configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)

        if reconfigure is not None:
            reconfigure(
                encoding="utf-8",
                errors="replace",
            )


def _validate_build_patch_result(
    result: BuildPatchResult,
) -> None:
    required_fields = (
        "patch_id",
        "goal",
        "target_file",
        "original_sha256",
        "candidate_sha256",
        "candidate_file",
        "diff_file",
        "compile_passed",
        "semantic_decision",
        "semantic_review",
        "revision_round",
        "status",
        "format_version",
    )

    for field in required_fields:
        if not hasattr(result, field):
            raise RuntimeError(
                f"Build patch result is missing field: {field}"
            )

    if result.format_version not in {
        "FULL_FILE_V2",
        "NEW_FILE_V2",
    }:
        raise RuntimeError(
            "Build patch result has unsupported format_version."
        )

    if not result.patch_id:
        raise RuntimeError(
            "Build patch result is missing patch_id."
        )

    if not result.target_file:
        raise RuntimeError(
            "Build patch result is missing target_file."
        )

    if (
        result.format_version == "FULL_FILE_V2"
        and not result.original_sha256
    ):
        raise RuntimeError(
            "FULL_FILE_V2 build patch result is missing original_sha256."
        )

    if (
        result.format_version == "NEW_FILE_V2"
        and result.original_sha256 is not None
    ):
        raise RuntimeError(
            "NEW_FILE_V2 build patch result must not have original_sha256."
        )

    if not result.candidate_sha256:
        raise RuntimeError(
            "Build patch result is missing candidate_sha256."
        )

    if result.status not in {
        "READY_FOR_HUMAN_REVIEW",
        "REJECTED",
        "DRAFT",
    }:
        raise RuntimeError(
            f"Build patch result has unknown status: {result.status}"
        )

    if (
        result.status == "READY_FOR_HUMAN_REVIEW"
        and not result.compile_passed
    ):
        raise RuntimeError(
            "Build patch candidate did not pass compilation."
        )


def _print_patch_metadata(
    patch_result: BuildPatchResult,
) -> None:
    print("PATCH METADATA")
    print("-" * 72)
    print(f"Patch ID: {patch_result.patch_id}")
    print(f"Target file: {patch_result.target_file}")
    print(f"Candidate file: {patch_result.candidate_file}")
    print(f"Diff file: {patch_result.diff_file}")
    print(f"Original SHA256: {patch_result.original_sha256}")
    print(f"Candidate SHA256: {patch_result.candidate_sha256}")
    print(f"Compile passed: {patch_result.compile_passed}")
    print(f"Semantic decision: {patch_result.semantic_decision}")
    print(f"Revision round: {patch_result.revision_round}")
    print(f"Format version: {patch_result.format_version}")
    print(f"Status: {patch_result.status}")
    print()


def _print_workspace_context(
    selection,
) -> None:
    workspace = selection.workspace

    print("ACTIVE WORKSPACE")
    print("-" * 72)
    print(f"Name: {workspace.name}")
    print(f"Path: {workspace.path}")
    print(f"Access mode: {workspace.access_mode}")
    print(
        "Writable via Dev Agent: "
        f"{selection.writable_via_dev_agent}"
    )
    print(f"Reason: {selection.reason}")
    print()

    try:
        structure = inspect_workspace_structure(
            workspace.name,
            max_entries=25,
        )
    except Exception as exc:
        print(
            f"WORKSPACE STRUCTURE INSPECTION FAILED: {exc}"
        )
        raise

    print("WORKSPACE STRUCTURE")
    print("-" * 72)
    print(f"Exists: {structure.exists}")
    print(f"Directory: {structure.is_directory}")
    print(f"Inspected: {structure.inspected}")
    print(
        "Top-level entries: "
        f"{', '.join(structure.top_level_entries) or '<none>'}"
    )
    print()

    if not structure.exists or not structure.is_directory:
        raise RuntimeError(
            "Active workspace structure is not a valid directory."
        )

    if not structure.inspected:
        raise RuntimeError(
            "Active workspace structure was not inspected."
        )


def _run_v20_test_compile_ci_validation(
    workspace_selection,
) -> str:
    workspace = workspace_selection.workspace

    git_status = inspect_git_workspace_status(
        workspace.name
    )

    changed_files = tuple(
        sorted(
            set(
                git_status.tracked_modified
                + git_status.untracked
                + git_status.staged
                + git_status.conflicted
            ),
            key=str.casefold,
        )
    )

    print("V2.0 TEST / COMPILE / CI VALIDATION")
    print("-" * 72)
    print(f"Changed files: {len(changed_files)}")

    if git_status.conflicted:
        raise RuntimeError(
            "Git workspace contains conflicted paths. "
            "V2.0 validation refuses to continue."
        )

    registry = inspect_repository_test_registry(
        workspace.name
    )

    print(
        f"Registered tests: {len(registry.tests)}"
    )

    if changed_files:
        selection = plan_test_selection(
            registry,
            changed_files,
        )

        print(
            "Focused tests: "
            + (
                ", ".join(selection.focused_test_ids)
                if selection.focused_test_ids
                else "<none>"
            )
        )

        print(
            f"Regression tests available: "
            f"{len(selection.regression_test_ids)}"
        )

        compile_plan = plan_compile_checks(
            workspace.name,
            registry,
            selection,
            changed_files,
        )

        compile_result = execute_compile_checks(
            compile_plan
        )

        print(
            f"Compile targets: "
            f"{len(compile_result.targets)}"
        )
        print(
            f"Compile result: "
            f"{'PASS' if compile_result.passed else 'FAIL'}"
        )

        if not compile_result.passed:
            failures = tuple(
                result
                for result in compile_result.targets
                if not result.passed
            )

            for failure in failures:
                print(
                    f"Compile failure: "
                    f"{failure.target} | "
                    f"{failure.error_type}: "
                    f"{failure.error_message}"
                )

            raise RuntimeError(
                "V2.0 safe compile checks failed."
            )

        blocked_focused_test_ids = tuple(
            test_id
            for test_id in selection.focused_test_ids
            if test_id in BLOCKED_TEST_IDS
        )

        executable_focused_test_ids = tuple(
            test_id
            for test_id in selection.focused_test_ids
            if test_id not in BLOCKED_TEST_IDS
        )

        print(
            "Executable focused tests: "
            + (
                ", ".join(executable_focused_test_ids)
                if executable_focused_test_ids
                else "<none>"
            )
        )

        print(
            "Blocked focused tests: "
            + (
                ", ".join(blocked_focused_test_ids)
                if blocked_focused_test_ids
                else "<none>"
            )
        )

        if executable_focused_test_ids:
            test_execution_result = execute_registered_tests(
                registry,
                executable_focused_test_ids,
                timeout_seconds=60,
            )

            print(
                "Focused test execution: "
                f"{'PASS' if test_execution_result.passed else 'FAIL'}"
            )

            for test_result in test_execution_result.results:
                print(
                    f"Focused test: {test_result.test_id} | "
                    f"{'PASS' if test_result.passed else 'FAIL'} | "
                    f"returncode={test_result.returncode}"
                )

            if not test_execution_result.passed:
                failed_test_ids = tuple(
                    test_result.test_id
                    for test_result in test_execution_result.results
                    if not test_result.passed
                )

                raise RuntimeError(
                    "V2.0 focused registered tests failed: "
                    + ", ".join(failed_test_ids)
                )

        else:
            test_execution_result = None

            print(
                "Focused test execution: NOT_REQUIRED"
            )

    else:
        selection = None
        compile_result = None
        test_execution_result = None
        blocked_focused_test_ids = ()
        executable_focused_test_ids = ()

        print("Focused tests: <none>")
        print("Regression tests available: 0")
        print("Compile targets: 0")
        print("Compile result: NOT_REQUIRED")
        print("Executable focused tests: <none>")
        print("Blocked focused tests: <none>")
        print("Focused test execution: NOT_REQUIRED")

    ci_snapshot = inspect_ci_awareness(
        workspace.name
    )

    print(
        f"External CI provider: "
        f"{ci_snapshot.configuration.provider}"
    )
    print(
        f"External CI configured: "
        f"{ci_snapshot.configuration.configured}"
    )
    print(
        f"External CI status: "
        f"{ci_snapshot.external_result.status}"
    )
    print(
        "Focused registered-test execution: ENABLED"
    )
    print(
        "Git / CI mutation: NO"
    )
    print()

    focused_text = (
        ", ".join(selection.focused_test_ids)
        if selection is not None
        and selection.focused_test_ids
        else "<none>"
    )

    compile_status = (
        "PASS"
        if compile_result is not None
        and compile_result.passed
        else "NOT_REQUIRED"
    )

    test_execution_status = (
        "PASS"
        if test_execution_result is not None
        and test_execution_result.passed
        else "NOT_REQUIRED"
    )

    blocked_focused_text = (
        ", ".join(blocked_focused_test_ids)
        if blocked_focused_test_ids
        else "<none>"
    )

    return (
        "V2.0 deterministic validation summary:\n"
        f"Changed files: {len(changed_files)}\n"
        f"Registered tests: {len(registry.tests)}\n"
        f"Focused tests: {focused_text}\n"
        f"Compile status: {compile_status}\n"
        f"Focused test execution: {test_execution_status}\n"
        f"Blocked focused tests: {blocked_focused_text}\n"
        f"External CI provider: "
        f"{ci_snapshot.configuration.provider}\n"
        f"External CI status: "
        f"{ci_snapshot.external_result.status}\n"
        "Focused registered-test execution: ENABLED\n"
        "Git / CI mutation: NO"
    )


def run_continue_milestone(
    developer_instruction: str,
    target_repository: str | Path = PROJECT_ROOT,
) -> int:
    configure_utf8_output()

    try:
        workspace_selection = active_workspace_from_path(
            target_repository
        )
    except Exception as exc:
        print(
            f"ACTIVE WORKSPACE RESOLUTION FAILED: {exc}"
        )
        return 1

    print("=" * 72)
    print("WORLD OS DEV AGENT - CONTINUE CURRENT MILESTONE")
    print("=" * 72)
    print()

    print("DEVELOPER INSTRUCTION:")
    print(developer_instruction)
    print()

    print("TARGET REPOSITORY:")
    print(workspace_selection.workspace.path)
    print()

    try:
        _print_workspace_context(
            workspace_selection
        )
    except Exception:
        print(
            "Progression stopped safely. No task-state resolution, "
            "investigation, patch generation, approval, or apply action "
            "was performed."
        )
        return 1

    resolution = load_resolved_task_state(
        workspace_selection.workspace.name
    )
    state = resolution.state

    print("TASK STATE RESOLUTION")
    print("-" * 72)
    print(f"Decision: {resolution.decision}")
    print(f"Status: {state.status}")
    print(f"Milestone: {state.milestone}")
    print(f"Objective: {state.objective}")
    print(f"Previous milestone: {state.previous_milestone}")
    print()

    try:
        transition_plan = plan_task_state_transition(
            resolution
        )

        print("TASK STATE TRANSITION")
        print("-" * 72)
        print(f"Action: {transition_plan.action}")
        print(f"Decision: {transition_plan.decision}")
        print(f"Reason: {transition_plan.reason}")
        print()

        if transition_plan.action == "BLOCK":
            print(
                "TASK STATE TRANSITION BLOCKED: progression stopped safely. "
                "No persistence, investigation, patch generation, approval, "
                "or apply action was performed."
            )
            return 1

        execution_result = execute_task_state_transition(
            transition_plan,
            workspace_name=workspace_selection.workspace.name,
        )

        if transition_plan.action == "PERSIST":
            if not execution_result.persisted:
                raise RuntimeError(
                    "Task-state transition expected persistence, "
                    "but persisted is False."
                )
        elif transition_plan.action == "NO_WRITE":
            if execution_result.persisted:
                raise RuntimeError(
                    "Task-state transition expected no write, "
                    "but persisted is True."
                )
        else:
            raise RuntimeError(
                f"Unsupported task-state transition action: "
                f"{transition_plan.action}"
            )

    except Exception as exc:
        print(
            f"TASK STATE TRANSITION FAILED: {exc}"
        )
        print(
            "Progression stopped safely. No investigation, patch generation, "
            "approval, apply action, or further task-state mutation was "
            "performed."
        )
        return 1

    if state.status == "NO_NEW_MILESTONE":
        print("MILESTONE STATUS")
        print("-" * 72)
        print(NO_NEW_MILESTONE)
        print(
            "No new milestone is defined in resolved task state. "
            "No investigation, patch generation, approval, "
            "or apply action was performed."
        )
        return 0

    if state.status not in {"ACTIVE", "HANDOFF_READY"}:
        print(
            f"TASK STATE INVALID: unsupported runtime status {state.status!r}."
        )
        return 1

    if not state.milestone or not state.objective:
        print(
            "TASK STATE INVALID: active task state requires "
            "a non-empty milestone and objective."
        )
        return 1

    persistent_objective = state.objective
    active_milestone = state.milestone

    initial_planner_instruction = (
        "Select exactly one small bounded development objective inside "
        "the canonical active milestone and persistent milestone objective.\n\n"
        "ACTIVE MILESTONE:\n"
        f"{active_milestone}\n\n"
        "PERSISTENT MILESTONE OBJECTIVE:\n"
        f"{persistent_objective}\n\n"
        "DEVELOPER INSTRUCTION:\n"
        f"{developer_instruction}\n\n"
        "The Developer instruction may narrow the work but cannot replace "
        "the persistent objective or leave the active milestone."
    )

    try:
        objective, patch_result = _run_bounded_build_cycle(
            cycle_label="INITIAL",
            planner_instruction=initial_planner_instruction,
            active_milestone=active_milestone,
            persistent_objective=persistent_objective,
            developer_instruction=developer_instruction,
            workspace_selection=workspace_selection,
        )
    except Exception as exc:
        print(
            f"INITIAL BOUNDED BUILD CYCLE FAILED: {exc}"
        )
        print(
            "Progression stopped safely. No approval, apply, Git write, "
            "database write, Supabase write, or production write was performed."
        )
        return 1

    if patch_result.status == "READY_FOR_HUMAN_REVIEW":
        print(
            "Patch is ready for explicit human review. "
            "No approval or apply action was performed."
        )
        return 0

    if patch_result.status == "REJECTED":
        print(
            "Patch was rejected by the build orchestrator. "
            "Starting one bounded self-steering recovery attempt."
        )
        print()

        recovery_instruction = (
            "Select exactly one corrected or smaller bounded development "
            "objective after semantic REJECT. Stay inside the same canonical "
            "active milestone and persistent objective.\n\n"
            "ACTIVE MILESTONE:\n"
            f"{active_milestone}\n\n"
            "PERSISTENT MILESTONE OBJECTIVE:\n"
            f"{persistent_objective}\n\n"
            "DEVELOPER INSTRUCTION:\n"
            f"{developer_instruction}\n\n"
            "REJECTED OBJECTIVE:\n"
            f"{objective}\n\n"
            "SEMANTIC REJECTION REVIEW:\n"
            f"{patch_result.semantic_review}\n\n"
            "Address the semantic rejection directly. Return one bounded "
            "objective only."
        )

        try:
            recovery_objective, recovery_patch_result = (
                _run_bounded_build_cycle(
                    cycle_label="SELF-STEERING REJECT RECOVERY",
                    planner_instruction=recovery_instruction,
                    active_milestone=active_milestone,
                    persistent_objective=persistent_objective,
                    developer_instruction=developer_instruction,
                    workspace_selection=workspace_selection,
                    rejected_objective=objective,
                    semantic_rejection_review=patch_result.semantic_review,
                )
            )
        except Exception as exc:
            print(
                f"SELF-STEERING REJECT RECOVERY FAILED: {exc}"
            )
            print(
                "Progression stopped safely. No approval, apply, Git write, "
                "database write, Supabase write, or production write "
                "was performed."
            )
            return 1

        if (
            recovery_objective.strip().casefold()
            == objective.strip().casefold()
        ):
            print(
                "SELF-STEERING REJECT RECOVERY FAILED: "
                "planner returned the same rejected objective."
            )
            print(
                "Progression stopped safely. No approval or apply action "
                "was performed."
            )
            return 1

        if (
            recovery_patch_result.status
            == "READY_FOR_HUMAN_REVIEW"
        ):
            print(
                "Self-steering recovery produced a patch ready for explicit "
                "human review. No approval or apply action was performed."
            )
            return 0

        print(
            "SELF-STEERING REJECT RECOVERY FAILED: "
            "the single recovery cycle did not produce a "
            "READY_FOR_HUMAN_REVIEW patch."
        )
        print(
            "Progression stopped safely. No approval, apply, Git write, "
            "database write, Supabase write, or production write was performed."
        )
        return 1

    print(
        "Patch remains in DRAFT status. "
        "No approval or apply action was performed."
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo",
        default=str(PROJECT_ROOT),
    )
    args = parser.parse_args()

    instruction = (
        "Continue building the current World OS milestone."
    )

    raise SystemExit(
        run_continue_milestone(
            instruction,
            target_repository=args.repo,
        )
    )