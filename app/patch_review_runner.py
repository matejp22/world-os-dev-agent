from __future__ import annotations

from app.ai_patch_planner import propose_patch
from app.ai_patch_reviewer import review_patch
from app.patch_validator import validate_patch_proposal


GOAL = (
    "Prepare the next Dev Agent architecture change for "
    "human-approved local code patch generation."
)


proposal = propose_patch(GOAL)

print("=" * 70)
print("PATCH PROPOSAL")
print("=" * 70)
print(proposal)
print()

validation = validate_patch_proposal(proposal)

print("=" * 70)
print("STRUCTURAL VALIDATION")
print("=" * 70)
print("VALID:")
print(validation.valid)
print()
print("REASON:")
print(validation.reason)
print()

if not validation.valid:
    print("SEMANTIC REVIEW:")
    print("SKIPPED")
else:
    review = review_patch(
        goal=GOAL,
        proposal=proposal,
    )

    print("=" * 70)
    print("SEMANTIC REVIEW")
    print("=" * 70)
    print(review)
