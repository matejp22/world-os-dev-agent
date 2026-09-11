from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
import shutil

from app.live_state import (
    current_milestone_version,
    load_live_state,
)
from app.live_state_handoff_writer import (
    LIVE_STATE_PATH,
    ROADMAP_PATH,
    LiveStateHandoffCandidate,
    build_live_state_handoff_candidate,
)
from app.milestone_handoff import (
    milestone_version,
    roadmap_expected_successor,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

LIVE_STATE_PATH = (
    PROJECT_ROOT
    / "context"
    / "LIVE_STATE.md"
)

BACKUP_DIR = (
    PROJECT_ROOT
    / "backups"
)

EXPECTED_TARGET = "context/LIVE_STATE.md"

CONFIRMATION_PHRASE = (
    "CONFIRM LIVE_STATE MILESTONE HANDOFF"
)


@dataclass(frozen=True)
class LiveStateHandoffApplyResult:
    target_file: str
    original_sha256: str
    applied_sha256: str
    backup_path: str
    applied: bool
    validated: bool
    reason: str


def _sha256_file(
    path: Path,
) -> str:
    return sha256(
        path.read_bytes()
    ).hexdigest()


def apply_live_state_handoff(
    *,
    expected_live_state_sha256: str,
    confirmation: str,
    live_state_path: Path = LIVE_STATE_PATH,
    roadmap_path: Path | None = None,
    backup_dir: Path = BACKUP_DIR,
) -> LiveStateHandoffApplyResult:
    if confirmation != CONFIRMATION_PHRASE:
        raise RuntimeError(
            "Explicit human confirmation phrase is required."
        )

    expected_target = (
        PROJECT_ROOT
        / "context"
        / "LIVE_STATE.md"
    ).resolve()

    target = live_state_path.resolve()

    if (
        live_state_path == LIVE_STATE_PATH
        and target != expected_target
    ):
        raise RuntimeError(
            "Canonical LIVE_STATE target validation failed."
        )

    if not live_state_path.exists():
        raise RuntimeError(
            "LIVE_STATE target does not exist."
        )

    if not live_state_path.is_file():
        raise RuntimeError(
            "LIVE_STATE target is not a regular file."
        )

    actual_sha = _sha256_file(
        live_state_path
    )

    if (
        actual_sha.casefold()
        != expected_live_state_sha256.strip().casefold()
    ):
        raise RuntimeError(
            "LIVE_STATE SHA256 mismatch before apply."
        )

    candidate_kwargs = {
        "expected_live_state_sha256":
            expected_live_state_sha256,
        "live_state_path":
            live_state_path,
    }

    if roadmap_path is not None:
        candidate_kwargs["roadmap_path"] = roadmap_path

    candidate = build_live_state_handoff_candidate(
        **candidate_kwargs
    )

    if not candidate.validated:
        raise RuntimeError(
            "LIVE_STATE handoff candidate is not validated."
        )

    if candidate.target_file != EXPECTED_TARGET:
        raise RuntimeError(
            "Unexpected LIVE_STATE candidate target."
        )

    if candidate.original_sha256 != actual_sha:
        raise RuntimeError(
            "LIVE_STATE candidate original SHA mismatch."
        )

    previous_version = milestone_version(
        candidate.current_milestone
    )

    next_version = milestone_version(
        candidate.next_milestone
    )

    if previous_version is None:
        raise RuntimeError(
            "Previous milestone version is missing."
        )

    if next_version is None:
        raise RuntimeError(
            "Next milestone version is missing."
        )

    effective_roadmap_path = (
        roadmap_path
        if roadmap_path is not None
        else ROADMAP_PATH
    )

    if not effective_roadmap_path.exists():
        raise RuntimeError(
            "ROADMAP target does not exist."
        )

    if not effective_roadmap_path.is_file():
        raise RuntimeError(
            "ROADMAP target is not a regular file."
        )

    roadmap_text = effective_roadmap_path.read_text(
        encoding="utf-8-sig"
    )

    expected_successor = roadmap_expected_successor(
        roadmap_text,
        previous_version,
    )

    if expected_successor is None:
        raise RuntimeError(
            "ROADMAP does not define a deterministic "
            "successor for the current milestone."
        )

    if next_version != expected_successor:
        raise RuntimeError(
            "Candidate milestone is not the immediate "
            "ROADMAP successor."
        )

    candidate_bytes = candidate.candidate_content.encode(
        "utf-8"
    )

    candidate_sha = sha256(
        candidate_bytes
    ).hexdigest()

    if candidate_sha != candidate.candidate_sha256:
        raise RuntimeError(
            "LIVE_STATE candidate SHA mismatch."
        )

    backup_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    backup_path = (
        backup_dir
        / (
            live_state_path.name
            + ".before-handoff."
            + actual_sha[:12]
            + ".bak"
        )
    )

    backup_preexisting = backup_path.exists()

    if backup_preexisting:
        if not backup_path.is_file():
            raise RuntimeError(
                "Existing LIVE_STATE backup is not a regular file."
            )

        if _sha256_file(
            backup_path
        ) != actual_sha:
            raise RuntimeError(
                "Existing LIVE_STATE backup SHA does not match "
                "the current canonical LIVE_STATE."
            )

    stage_path = live_state_path.with_name(
        "." + live_state_path.name + ".handoff.stage"
    )

    if stage_path.exists():
        raise RuntimeError(
            "LIVE_STATE handoff stage already exists."
        )

    source_replaced = False

    try:
        if not backup_preexisting:
            shutil.copy2(
                live_state_path,
                backup_path,
            )

        if _sha256_file(
            backup_path
        ) != actual_sha:
            raise RuntimeError(
                "LIVE_STATE backup SHA verification failed."
            )

        with stage_path.open(
            "xb"
        ) as handle:
            handle.write(
                candidate_bytes
            )
            handle.flush()
            os.fsync(
                handle.fileno()
            )

        if _sha256_file(
            stage_path
        ) != candidate_sha:
            raise RuntimeError(
                "LIVE_STATE stage SHA verification failed."
            )

        os.replace(
            stage_path,
            live_state_path,
        )

        source_replaced = True

        applied_sha = _sha256_file(
            live_state_path
        )

        if applied_sha != candidate_sha:
            raise RuntimeError(
                "Applied LIVE_STATE SHA mismatch."
            )

        parsed = load_live_state(
            live_state_path
        )

        if current_milestone_version(
            parsed
        ) != next_version:
            raise RuntimeError(
                "Applied LIVE_STATE current milestone validation failed."
            )

        if parsed.current_objective_status != "ACTIVE":
            raise RuntimeError(
                "Applied LIVE_STATE status validation failed."
            )

        if parsed.next_milestone is not None:
            raise RuntimeError(
                "Applied LIVE_STATE next milestone must be empty."
            )

        if parsed.next_milestone_objective is not None:
            raise RuntimeError(
                "Applied LIVE_STATE next objective must be empty."
            )

        if previous_version not in parsed.completed_milestones:
            raise RuntimeError(
                "Applied LIVE_STATE lost previous COMPLETE milestone."
            )

        return LiveStateHandoffApplyResult(
            target_file=EXPECTED_TARGET,
            original_sha256=actual_sha,
            applied_sha256=applied_sha,
            backup_path=str(
                backup_path
            ),
            applied=True,
            validated=True,
            reason=(
                "LIVE_STATE milestone handoff applied and "
                "post-write validation passed."
            ),
        )

    except Exception:
        if source_replaced:
            shutil.copy2(
                backup_path,
                live_state_path,
            )

            if _sha256_file(
                live_state_path
            ) != actual_sha:
                raise RuntimeError(
                    "LIVE_STATE rollback SHA verification failed."
                )

        if stage_path.exists():
            stage_path.unlink()

        raise


if __name__ == "__main__":
    print(
        "LIVE_STATE handoff apply writer loaded. "
        "No write is performed without explicit confirmation."
    )
