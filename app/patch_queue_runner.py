from __future__ import annotations

from app.ai_patch_planner import propose_patch
from app.ai_patch_reviewer import review_patch
from app.patch_queue import (
    create_patch_approval,
    save_patch_approval,
)
from app.patch_validator import validate_patch_proposal


GOAL = (
    "Prepare the next Dev Agent architecture change for "
    "human-approved local code patch generation."
)


proposal = propose_patch(GOAL)

validation = validate_patch_proposal(
    proposal
)

if validation.valid:
    semantic_review = review_patch(
        goal=GOAL,
        proposal=proposal,
    )
else:
    semantic_review = (
        "REJECT\n\n"
        "REASON:\n"
        "Structural validation failed."
    )


approval = create_patch_approval(
    goal=GOAL,
    proposal=proposal,
    target_file=validation.target_file,
    structural_valid=validation.valid,
    structural_reason=validation.reason,
    semantic_review=semantic_review,
)

path = save_patch_approval(
    approval
)


print("=" * 70)
print("WORLD OS DEV AGENT - PATCH QUEUE")
print("=" * 70)
print()
print("PATCH ID:")
print(approval.patch_id)
print()
print("TARGET FILE:")
print(approval.target_file or "<none>")
print()
print("STRUCTURAL VALID:")
print(approval.structural_valid)
print()
print("SEMANTIC DECISION:")
print(approval.semantic_decision)
print()
print("STATUS:")
print(approval.status)
print()
print("QUEUE FILE:")
print(path)
print()
print("NO PATCH WAS APPLIED.")
