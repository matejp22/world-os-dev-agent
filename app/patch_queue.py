from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = PROJECT_ROOT / "pending_patches"


ALLOWED_STATUSES = {
    "DRAFT",
    "VALIDATED",
    "REJECTED",
    "READY_FOR_HUMAN_REVIEW",
    "APPROVED",
    "APPLIED",
}


@dataclass
class PatchApproval:
    patch_id: str
    created_at: str
    goal: str
    target_file: str | None
    structural_valid: bool
    structural_reason: str
    semantic_decision: str
    semantic_review: str
    status: str
    proposal: str


def semantic_decision_from_review(review: str) -> str:
    first_line = review.strip().splitlines()[0].strip()

    if first_line in {
        "REJECT",
        "REVISE",
        "APPROVE_FOR_HUMAN_REVIEW",
    }:
        return first_line

    return "UNKNOWN"


def determine_status(
    structural_valid: bool,
    semantic_decision: str,
) -> str:
    if not structural_valid:
        return "REJECTED"

    if semantic_decision == "REJECT":
        return "REJECTED"

    if semantic_decision == "REVISE":
        return "DRAFT"

    if semantic_decision == "APPROVE_FOR_HUMAN_REVIEW":
        return "READY_FOR_HUMAN_REVIEW"

    return "DRAFT"


def create_patch_approval(
    goal: str,
    proposal: str,
    target_file: str | None,
    structural_valid: bool,
    structural_reason: str,
    semantic_review: str,
) -> PatchApproval:
    semantic_decision = semantic_decision_from_review(
        semantic_review
    )

    status = determine_status(
        structural_valid=structural_valid,
        semantic_decision=semantic_decision,
    )

    if status not in ALLOWED_STATUSES:
        raise RuntimeError(
            f"Invalid patch status: {status}"
        )

    return PatchApproval(
        patch_id=str(uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
        goal=goal,
        target_file=target_file,
        structural_valid=structural_valid,
        structural_reason=structural_reason,
        semantic_decision=semantic_decision,
        semantic_review=semantic_review,
        status=status,
        proposal=proposal,
    )


def save_patch_approval(
    approval: PatchApproval,
) -> Path:
    QUEUE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = QUEUE_DIR / f"{approval.patch_id}.json"

    path.write_text(
        json.dumps(
            asdict(approval),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return path
