from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import streamlit as st

from app.continue_status_parser import (
    parse_continue_milestone_output,
)

from app.dev_task_state import (
    load_resolved_task_state,
)
from app.git_workspace_status import (
    inspect_git_workspace_status,
    plan_git_actions,
)
from app.live_state_handoff_apply import (
    CONFIRMATION_PHRASE,
    apply_live_state_handoff,
)
from app.milestone_handoff import (
    build_handoff_plan,
)
from app.roadmap_panel import (
    render_world_os_roadmap_panel,
)
from app.workspace_registry import (
    ActiveWorkspaceSelection,
    inspect_workspace_structure,
    registered_workspace_names,
    select_active_workspace,
)


ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
QUEUE_DIR = ROOT / "pending_patches"
LIVE_STATE_PATH = ROOT / "context" / "LIVE_STATE.md"
ROADMAP_PATH = ROOT / "context" / "ROADMAP.md"


def resolve_console_version() -> str:
    try:
        resolution = load_resolved_task_state()
    except Exception:
        return "UNKNOWN"

    milestone = resolution.state.milestone or ""

    match = re.search(
        r"\bV\d+(?:\.\d+)+\b",
        milestone,
    )

    if match is None:
        return "UNKNOWN"

    return match.group(0)


DEFAULT_GOAL = (
    "Check the current state of world-os-research-engine "
    "and recommend the next safe development step."
)


def extract_reviews(text: str) -> list[str]:
    matches = re.findall(
        r"AI REVIEW:\s*(.*?)(?=\nCONTROLLER:|\n={20,}|\Z)",
        text,
        flags=re.DOTALL,
    )

    return [
        match.strip()
        for match in matches
        if match.strip()
    ]


def extract_policy_lines(text: str) -> list[str]:
    lines = text.splitlines()
    results: list[str] = []

    current_command = None

    for index, line in enumerate(lines):
        if line.strip() == "COMMAND:" and index + 1 < len(lines):
            current_command = lines[index + 1].strip()

        if line.strip() == "POLICY ALLOWED:" and index + 1 < len(lines):
            allowed = lines[index + 1].strip()

            if current_command:
                symbol = "PASS" if allowed == "True" else "BLOCKED"
                results.append(
                    f"{symbol}: {current_command}"
                )

    return results


def recent_session_logs(
    limit: int = 10,
) -> list[Path]:
    if not LOG_DIR.exists():
        return []

    logs = sorted(
        LOG_DIR.glob("autonomous_readonly_*.txt"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    return logs[:limit]


def load_patch_records() -> list[tuple[Path, dict]]:
    if not QUEUE_DIR.exists():
        return []

    records: list[tuple[Path, dict]] = []

    for path in QUEUE_DIR.glob("*.json"):
        try:
            data = json.loads(
                path.read_text(
                    encoding="utf-8",
                )
            )
            records.append(
                (path, data)
            )
        except Exception:
            continue

    records.sort(
        key=lambda item: item[0].stat().st_mtime,
        reverse=True,
    )

    return records


def save_patch_record(
    path: Path,
    data: dict,
) -> None:
    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def apply_full_file_patch(
    patch_id: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "app.full_file_apply_v2",
            "--patch-id",
            patch_id,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def apply_patch_by_format(
    patch_id: str,
    format_version: str,
) -> subprocess.CompletedProcess[str]:
    if format_version == "FULL_FILE_V2":
        return apply_full_file_patch(
            patch_id
        )

    if format_version == "NEW_FILE_V2":
        return apply_full_file_patch(
            patch_id
        )

    return subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout="",
        stderr=(
            f"Unsupported patch format: {format_version}"
        ),
    )


CONTINUE_SAFELY_TIMEOUT_SECONDS = 600


def run_continue_safely(
    workspace: ActiveWorkspaceSelection,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-m",
        "app.continue_milestone_runner",
        "--repo",
        str(workspace.workspace.path),
    ]

    try:
        return subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CONTINUE_SAFELY_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode(
                "utf-8",
                errors="replace",
            )

        if isinstance(stderr, bytes):
            stderr = stderr.decode(
                "utf-8",
                errors="replace",
            )

        timeout_message = (
            "Continue safely timed out after "
            f"{CONTINUE_SAFELY_TIMEOUT_SECONDS} seconds. "
            "The bounded run was stopped without approval, apply, "
            "Git, database, or Supabase writes."
        )

        return subprocess.CompletedProcess(
            args=command,
            returncode=124,
            stdout=stdout,
            stderr=(
                stderr.rstrip()
                + ("\n" if stderr.strip() else "")
                + timeout_message
            ),
        )


def render_workspace_context(
    selection: ActiveWorkspaceSelection,
) -> None:
    try:
        structure = inspect_workspace_structure(
            selection.workspace.name,
            max_entries=25,
        )

        git_status = inspect_git_workspace_status(
            selection.workspace.name
        )
    except Exception as exc:
        st.error(
            "Workspace context unavailable. "
            "Inspection failed closed: "
            f"{type(exc).__name__}: {exc}"
        )
        return

    workspace = selection.workspace

    st.subheader("Active workspace")

    name_col, access_col = st.columns(2)

    with name_col:
        st.write(
            f"**Workspace:** {workspace.name}"
        )
        st.write(
            f"**Path:** {workspace.path}"
        )

    with access_col:
        st.write(
            f"**Access mode:** {workspace.access_mode}"
        )
        st.write(
            "**Writable via Dev Agent:** "
            f"{selection.writable_via_dev_agent}"
        )

    st.write(
        f"**Policy:** {selection.reason}"
    )

    st.caption(
        "Writable via Dev Agent does not mean unrestricted write access. "
        "HUMAN_APPROVED_PATCH_ONLY requires explicit human review "
        "and approval before source changes."
    )

    st.write(
        "**Structure:** "
        f"exists={structure.exists}, "
        f"directory={structure.is_directory}, "
        f"inspected={structure.inspected}"
    )

    st.markdown(
        "**Bounded top-level entries**"
    )

    if structure.top_level_entries:
        st.code(
            "\n".join(
                structure.top_level_entries
            ),
            language="text",
        )
    else:
        st.write("<none>")

    st.markdown("**Git status — READ ONLY**")

    git_left, git_right = st.columns(2)

    with git_left:
        st.write(
            f"**Branch:** {git_status.branch or '<detached>'}"
        )
        st.write(
            f"**Clean:** {git_status.clean}"
        )
        st.write(
            f"**Tracked modified:** {len(git_status.tracked_modified)}"
        )

    with git_right:
        st.write(
            f"**Untracked:** {len(git_status.untracked)}"
        )
        st.write(
            f"**Staged:** {len(git_status.staged)}"
        )
        st.write(
            f"**Conflicted:** {len(git_status.conflicted)}"
        )

    st.caption(
        "Git inspection is read-only. No git add, commit, push, "
        "or other repository mutation is performed."
    )

    st.markdown(
        "**Git action plan preview — NON-EXECUTING**"
    )

    if git_status.conflicted:
        st.warning(
            "Git action planning is blocked because conflicts are present."
        )
    else:
        preview_files = tuple(
            sorted(
                set(git_status.tracked_modified)
                | set(git_status.untracked)
                | set(git_status.staged)
            )
        )

        if not preview_files:
            st.write(
                "No changed files are available for Git action planning."
            )
        else:
            git_plan = plan_git_actions(
                git_status,
                preview_files,
                "Update World OS Dev Agent",
            )

            st.write(
                "**Files in preview:** "
                f"{len(git_plan.files_to_stage)}"
            )

            st.code(
                repr(git_plan.add_command),
                language="text",
            )
            st.code(
                repr(git_plan.commit_command),
                language="text",
            )
            st.code(
                repr(git_plan.push_command),
                language="text",
            )

            st.write(
                "**Requires human approval:** "
                f"{git_plan.requires_human_approval}"
            )
            st.write(
                f"**Executable:** {git_plan.executable}"
            )
            st.write(
                f"**Blocked:** {git_plan.blocked}"
            )

            st.caption(git_plan.reason)

    st.caption(
        "Preview only. No Git action button is available and "
        "no Git mutation command is executed."
    )


st.set_page_config(
    page_title="World OS Dev Agent",
    layout="wide",
)

st.title("World OS Dev Agent")
console_version = resolve_console_version()

st.caption(
    f"Developer Console {console_version} "
    "— SAFE EXECUTION + PATCH CONTROL"
)

st.info(
    "Runtime mode is READ ONLY by default. "
    "Approved FULL_FILE_V2 patches may be applied only after explicit "
    "human confirmation in Patch review."
)

workspace_names = registered_workspace_names()

if not workspace_names:
    st.error(
        "No registered workspaces are available."
    )
    st.stop()

default_workspace = "world-os-dev-agent"
workspace_state_key = "active_workspace_name"

if (
    workspace_state_key not in st.session_state
    or st.session_state[workspace_state_key]
    not in workspace_names
):
    if default_workspace in workspace_names:
        st.session_state[workspace_state_key] = (
            default_workspace
        )
    else:
        st.session_state[workspace_state_key] = (
            workspace_names[0]
        )


def _on_active_workspace_change() -> None:
    selected = st.session_state.get(
        workspace_state_key
    )

    if selected not in workspace_names:
        st.session_state[workspace_state_key] = (
            default_workspace
            if default_workspace in workspace_names
            else workspace_names[0]
        )

    st.session_state.pop(
        "workspace_bound_task_resolution",
        None,
    )

    st.rerun()


st.selectbox(
    "Active workspace",
    options=workspace_names,
    key=workspace_state_key,
    on_change=_on_active_workspace_change,
    help=(
        "Select the registered repository used for task-state resolution, "
        "workspace inspection, safe investigation, and Continue current milestone."
    ),
)

selected_workspace_name = st.session_state[
    workspace_state_key
]

try:
    selected_workspace = select_active_workspace(
        selected_workspace_name
    )
except Exception as exc:
    st.error(
        "Workspace selection failed closed: "
        f"{type(exc).__name__}: {exc}"
    )
    st.stop()

st.subheader("Development task state")

try:
    task_resolution = load_resolved_task_state(
        selected_workspace_name
    )
except Exception as exc:
    task_resolution = None
    st.error(
        "Task-state resolution failed: "
        f"{type(exc).__name__}: {exc}"
    )

if task_resolution is not None:
    task_state = task_resolution.state

    decision_col, status_col = st.columns(2)

    with decision_col:
        st.markdown("**Resume decision**")
        st.write(task_resolution.decision)

    with status_col:
        st.markdown("**Task status**")
        st.write(task_state.status)

    st.markdown("**Milestone**")
    st.write(task_state.milestone or "<none>")

    st.markdown("**Objective**")
    st.write(task_state.objective or "<none>")

    st.markdown("**Previous milestone**")
    st.write(task_state.previous_milestone or "<none>")

st.subheader("Milestone handoff")

try:
    if not LIVE_STATE_PATH.exists():
        raise RuntimeError(
            "Canonical LIVE_STATE.md is missing."
        )

    live_state_sha256 = hashlib.sha256(
        LIVE_STATE_PATH.read_bytes()
    ).hexdigest()

    handoff_plan = build_handoff_plan(
        expected_live_state_sha256=live_state_sha256,
        live_state_path=LIVE_STATE_PATH,
        roadmap_path=ROADMAP_PATH,
    )

except Exception as exc:
    handoff_plan = None

    st.error(
        "Milestone handoff planning failed closed: "
        f"{type(exc).__name__}: {exc}"
    )

if handoff_plan is not None:
    handoff_left, handoff_right = st.columns(2)

    with handoff_left:
        st.markdown("**Current milestone**")
        st.write(
            handoff_plan.current_milestone
            or "<none>"
        )

        st.markdown("**Current objective status**")
        st.write(
            handoff_plan.current_objective_status
            or "<none>"
        )

    with handoff_right:
        st.markdown("**Next milestone**")
        st.write(
            handoff_plan.next_milestone
            or "<none>"
        )

        st.markdown("**Handoff allowed**")
        st.write(
            handoff_plan.allowed
        )

    st.markdown("**LIVE_STATE SHA256**")
    st.code(
        handoff_plan.live_state_sha256,
        language="text",
    )

    st.markdown("**Planner decision**")
    st.write(
        handoff_plan.reason
    )

    if handoff_plan.next_milestone_objective:
        st.markdown(
            "**Next milestone objective**"
        )
        st.write(
            handoff_plan.next_milestone_objective
        )

    if handoff_plan.allowed:
        st.warning(
            "Milestone handoff changes canonical context/LIVE_STATE.md. "
            "It does not approve source patches, perform Git operations, "
            "or enable Research Engine / Web writes."
        )

        handoff_confirm = st.checkbox(
            "I confirm that I want to promote the declared next milestone "
            "to the canonical current milestone.",
            key="confirm-milestone-handoff",
        )

        handoff_phrase = st.text_input(
            "Type the exact confirmation phrase",
            value="",
            key="milestone-handoff-confirmation-phrase",
            help=(
                "Required phrase: "
                + CONFIRMATION_PHRASE
            ),
        )

        phrase_matches = (
            handoff_phrase
            == CONFIRMATION_PHRASE
        )

        apply_handoff_clicked = st.button(
            "Apply milestone handoff",
            key="apply-milestone-handoff",
            type="primary",
            disabled=(
                not handoff_confirm
                or not phrase_matches
            ),
        )

        if apply_handoff_clicked:
            try:
                handoff_result = apply_live_state_handoff(
                    expected_live_state_sha256=(
                        handoff_plan.live_state_sha256
                    ),
                    confirmation=handoff_phrase,
                    live_state_path=LIVE_STATE_PATH,
                    roadmap_path=ROADMAP_PATH,
                )

            except Exception as exc:
                st.error(
                    "Milestone handoff apply failed closed: "
                    f"{type(exc).__name__}: {exc}"
                )

            else:
                if not handoff_result.applied:
                    st.error(
                        "Milestone handoff did not report applied=True."
                    )

                elif not handoff_result.validated:
                    st.error(
                        "Milestone handoff post-write validation failed."
                    )

                else:
                    st.success(
                        "Milestone handoff applied and validated."
                    )

                    st.write(
                        "**Backup:** "
                        + handoff_result.backup_path
                    )

                    st.write(
                        "**Applied SHA256:** "
                        + handoff_result.applied_sha256
                    )

                    st.info(
                        "Developer task state will be re-resolved from "
                        "canonical LIVE_STATE after reload."
                    )

                    st.rerun()

    else:
        st.info(
            "Canonical milestone handoff is currently unavailable. "
            "No LIVE_STATE write can be performed."
        )

st.divider()

st.subheader("Workspace target")

render_workspace_context(
    selected_workspace
)

if not selected_workspace.writable_via_dev_agent:
    st.warning(
        "Selected workspace is READ_ONLY. "
        "Investigation is allowed, but source modification through "
        "the Dev Agent is not permitted."
    )

st.caption(
    "Development task state and Continue current milestone are bound "
    "to the selected workspace. Source changes remain subject to that "
    "workspace's registered access policy and explicit human approval."
)

st.divider()

tab_run, tab_roadmap, tab_history, tab_patches = st.tabs(
    [
        "Run",
        "Roadmap",
        "Session history",
        "Patch review",
    ]
)


with tab_roadmap:
    render_world_os_roadmap_panel(
        master_roadmap_path=(
            ROOT
            / "context"
            / "master_roadmaps"
            / "world-os-2050.json"
        ),
        project_workspaces={
            "world-os-dev-agent": "world-os-dev-agent",
            "world-os-research-engine": "world-os-research-engine",
            "world-os-web": "world-os-web",
        },
    )


with tab_run:
    goal = st.text_area(
        "Development goal",
        value=DEFAULT_GOAL,
        height=120,
    )

    run_clicked = st.button(
        "Run safe investigation",
        type="primary",
    )

    continue_clicked = st.button(
        "Continue current milestone",
    )

    if run_clicked or continue_clicked:
        clean_goal = goal.strip()

        if run_clicked and not clean_goal:
            st.error(
                "Please enter a development goal."
            )
            st.stop()

        if continue_clicked:
            with st.spinner(
                "World OS Dev Agent is continuing the current milestone..."
            ):
                result = run_continue_safely(
                    selected_workspace
                )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            st.subheader("Status")

            if result.returncode == 0:
                st.success(
                    "Continue current milestone completed."
                )
            else:
                st.error(
                    "Continue current milestone failed with "
                    f"exit code {result.returncode}."
                )

            parsed_status = parse_continue_milestone_output(
                stdout
            )

            if parsed_status.objective:
                st.markdown("**Selected objective**")
                st.write(parsed_status.objective)

            if parsed_status.phase:
                st.write(
                    f"**Current phase:** {parsed_status.phase}"
                )

            if parsed_status.patch_id:
                st.write(
                    f"**Patch ID:** {parsed_status.patch_id}"
                )

            if parsed_status.target_file:
                st.write(
                    f"**Target file:** {parsed_status.target_file}"
                )

            if parsed_status.semantic_decision:
                st.write(
                    f"**Semantic decision:** "
                    f"{parsed_status.semantic_decision}"
                )

            if parsed_status.semantic_review:
                st.markdown("**Semantic review**")
                st.write(parsed_status.semantic_review)

            if parsed_status.transition_action:
                st.write(
                    f"**Transition action:** "
                    f"{parsed_status.transition_action}"
                )

            if parsed_status.transition_decision:
                st.write(
                    f"**Transition decision:** "
                    f"{parsed_status.transition_decision}"
                )

            if parsed_status.transition_reason:
                st.write(
                    f"**Transition reason:** "
                    f"{parsed_status.transition_reason}"
                )

            if parsed_status.status:
                if parsed_status.status == "READY_FOR_HUMAN_REVIEW":
                    st.success(
                        f"Status: {parsed_status.status}"
                    )
                elif parsed_status.status == "DRAFT":
                    st.warning(
                        f"Status: {parsed_status.status}"
                    )
                elif parsed_status.status == "REJECTED":
                    st.error(
                        f"Status: {parsed_status.status}"
                    )
                else:
                    st.info(
                        f"Status: {parsed_status.status}"
                    )

            st.subheader("Execution details")

            with st.expander(
                "Show continue milestone output"
            ):
                st.code(
                    stdout or "<no stdout>",
                    language="text",
                )

            if stderr:
                with st.expander(
                    "Show stderr"
                ):
                    st.code(
                        stderr,
                        language="text",
                    )

        else:
            command = [
                sys.executable,
                "-m",
                "app.autonomous_runner",
                "--goal",
                clean_goal,
                "--repo",
                str(selected_workspace.workspace.path),
            ]

            with st.spinner(
                "World OS Dev Agent is investigating..."
            ):
                result = subprocess.run(
                    command,
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            st.subheader("Status")

            if result.returncode == 0:
                st.success(
                    "Investigation completed."
                )
            else:
                st.error(
                    f"Investigation failed with exit code {result.returncode}."
                )

            policy_lines = extract_policy_lines(
                stdout
            )

            reviews = extract_reviews(
                stdout
            )

            left, right = st.columns(2)

            with left:
                st.subheader("Security policy")

                if policy_lines:
                    for line in policy_lines:
                        if line.startswith("PASS:"):
                            st.success(line)
                        else:
                            st.warning(line)
                else:
                    st.write(
                        "No policy decisions found."
                    )

            with right:
                st.subheader("AI review")

                if reviews:
                    st.write(
                        reviews[-1]
                    )
                else:
                    st.write(
                        "No AI review found."
                    )

            st.subheader("Execution details")

            with st.expander(
                "Show complete autonomous session"
            ):
                st.code(
                    stdout or "<no stdout>",
                    language="text",
                )

            if stderr:
                with st.expander(
                    "Show stderr"
                ):
                    st.code(
                        stderr,
                        language="text",
                    )


with tab_history:
    st.subheader("Recent autonomous sessions")

    logs = recent_session_logs()

    if not logs:
        st.write(
            "No session logs found yet."
        )
    else:
        for log_path in logs:
            with st.expander(
                log_path.name
            ):
                content = log_path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )

                reviews = extract_reviews(
                    content
                )

                if reviews:
                    st.markdown(
                        "**Latest AI review**"
                    )
                    st.write(
                        reviews[-1]
                    )

                st.markdown(
                    "**Full session**"
                )

                st.code(
                    content,
                    language="text",
                )


with tab_patches:
    st.subheader("Patch control")

    records = load_patch_records()

    if not records:
        st.write(
            "No patch records found."
        )
    else:
        for path, data in records:
            patch_id = data.get(
                "patch_id",
                path.stem,
            )

            target_file = data.get(
                "target_file",
                "<unknown>",
            )

            status = data.get(
                "status",
                "<unknown>",
            )

            format_version = data.get(
                "format_version",
                "<unknown>",
            )

            label = (
                f"{status} — {target_file} — {patch_id}"
            )

            with st.expander(
                label
            ):
                st.write(
                    f"Format: {data.get('format_version', '<unknown>')}"
                )

                st.write(
                    f"Semantic decision: "
                    f"{data.get('semantic_decision', '<unknown>')}"
                )

                if data.get(
                    "semantic_review"
                ):
                    st.markdown(
                        "**Semantic review**"
                    )
                    st.write(
                        data["semantic_review"]
                    )

                if data.get(
                    "diff_file"
                ):
                    diff_path = Path(
                        data["diff_file"]
                    )

                    if diff_path.exists():
                        st.markdown(
                            "**Review diff**"
                        )
                        st.code(
                            diff_path.read_text(
                                encoding="utf-8",
                                errors="replace",
                            ),
                            language="diff",
                        )

                if status == "READY_FOR_HUMAN_REVIEW":
                    approve_col, reject_col = st.columns(2)

                    with approve_col:
                        approve_clicked = st.button(
                            "Approve",
                            key=f"approve-{patch_id}",
                            type="primary",
                        )

                    with reject_col:
                        reject_clicked = st.button(
                            "Reject",
                            key=f"reject-{patch_id}",
                        )

                    if approve_clicked:
                        data["status"] = "APPROVED"

                        save_patch_record(
                            path,
                            data,
                        )

                        st.success(
                            "Patch approved. "
                            "Source code was NOT modified."
                        )

                        st.rerun()

                    if reject_clicked:
                        data["status"] = "REJECTED"

                        save_patch_record(
                            path,
                            data,
                        )

                        st.warning(
                            "Patch rejected."
                        )

                        st.rerun()

                elif status == "APPROVED":
                    st.success(
                        "Patch is approved and eligible for explicit apply."
                    )

                    confirm = st.checkbox(
                        "I confirm that I want to apply this approved patch.",
                        key=f"confirm-apply-{patch_id}",
                    )

                    apply_clicked = st.button(
                        "Apply approved patch",
                        key=f"apply-{patch_id}",
                        type="primary",
                        disabled=not confirm,
                    )

                    if apply_clicked:
                        with st.spinner(
                            "Applying patch with integrity checks..."
                        ):
                            result = apply_patch_by_format(
                                patch_id,
                                format_version,
                            )

                        if result.returncode == 0:
                            st.success(
                                "Patch applied successfully."
                            )

                            st.code(
                                result.stdout.strip(),
                                language="text",
                            )

                            st.rerun()
                        else:
                            st.error(
                                "Patch apply failed."
                            )

                            st.code(
                                (
                                    result.stderr.strip()
                                    or result.stdout.strip()
                                    or "<no output>"
                                ),
                                language="text",
                            )

                elif status == "REJECTED":
                    st.error(
                        "Patch rejected."
                    )

                elif status == "APPLIED":
                    st.success(
                        "Patch already applied."
                    )

                    post_apply = data.get(
                        "post_apply"
                    )

                    if isinstance(
                        post_apply,
                        dict,
                    ):
                        post_apply_validated = (
                            post_apply.get(
                                "validated"
                            )
                            is True
                        )

                        post_apply_next_action = str(
                            post_apply.get(
                                "next_action"
                            )
                            or ""
                        ).strip().upper()

                        post_apply_reason = str(
                            post_apply.get(
                                "reason"
                            )
                            or ""
                        ).strip()

                        if (
                            post_apply_validated
                            and post_apply_next_action
                            == "CONTINUE_SAFELY"
                        ):
                            st.markdown(
                                "**Next bounded development action**"
                            )

                            if post_apply_reason:
                                st.info(
                                    post_apply_reason
                                )
                            else:
                                st.info(
                                    "The applied patch passed post-apply "
                                    "validation. Continue safely to determine "
                                    "the next bounded development action."
                                )

                            continue_after_apply_clicked = st.button(
                                "Continue safely",
                                key=(
                                    "post-apply-continue-"
                                    f"{patch_id}"
                                ),
                                type="primary",
                            )

                            if continue_after_apply_clicked:
                                with st.spinner(
                                    "World OS Dev Agent is determining "
                                    "the next bounded development action..."
                                ):
                                    continue_result = (
                                        run_continue_safely(
                                            selected_workspace
                                        )
                                    )

                                continue_stdout = (
                                    continue_result.stdout.strip()
                                )

                                continue_stderr = (
                                    continue_result.stderr.strip()
                                )

                                if continue_result.returncode == 0:
                                    st.success(
                                        "Continue safely completed."
                                    )
                                else:
                                    st.error(
                                        "Continue safely failed with "
                                        f"exit code "
                                        f"{continue_result.returncode}."
                                    )

                                parsed_continue = (
                                    parse_continue_milestone_output(
                                        continue_stdout
                                    )
                                )

                                if parsed_continue.objective:
                                    st.markdown(
                                        "**Selected objective**"
                                    )
                                    st.write(
                                        parsed_continue.objective
                                    )

                                if parsed_continue.next_objective:
                                    st.markdown(
                                        "**Next objective**"
                                    )
                                    st.write(
                                        parsed_continue.next_objective
                                    )

                                if parsed_continue.next_action:
                                    st.write(
                                        "**Next action:** "
                                        f"{parsed_continue.next_action}"
                                    )

                                if parsed_continue.patch_id:
                                    st.write(
                                        "**Patch ID:** "
                                        f"{parsed_continue.patch_id}"
                                    )

                                if parsed_continue.target_file:
                                    st.write(
                                        "**Target file:** "
                                        f"{parsed_continue.target_file}"
                                    )

                                if parsed_continue.status:
                                    st.write(
                                        "**Status:** "
                                        f"{parsed_continue.status}"
                                    )

                                with st.expander(
                                    "Show Continue safely output"
                                ):
                                    st.code(
                                        continue_stdout
                                        or "<no stdout>",
                                        language="text",
                                    )

                                if continue_stderr:
                                    with st.expander(
                                        "Show Continue safely stderr"
                                    ):
                                        st.code(
                                            continue_stderr,
                                            language="text",
                                        )

                        elif not post_apply_validated:
                            st.warning(
                                "Post-apply progression metadata exists, "
                                "but validation is not confirmed."
                            )

                elif status == "ROLLED_BACK":
                    st.warning(
                        "Patch apply failed and source was rolled back."
                    )

                elif status == "ROLLBACK_FAILED":
                    st.error(
                        "CRITICAL: rollback failed."
                    )

                else:
                    st.info(
                        f"Current status: {status}"
                    )