from __future__ import annotations

from app.patch_validator import validate_patch_proposal


SAFE_PROPOSAL = """
TARGET_FILE: app/patch_source_loader.py

RATIONALE:
Safe test proposal.

PROPOSED_PATCH:
--- a/app/patch_source_loader.py
+++ b/app/patch_source_loader.py
@@ -1,1 +1,2 @@
 from __future__ import annotations
+# safe test line
"""


UNSAFE_PROPOSAL = """
TARGET_FILE: app/patch_source_loader.py

RATIONALE:
Unsafe test proposal.

PROPOSED_PATCH:
--- a/app/patch_source_loader.py
+++ b/app/patch_source_loader.py
@@ -1,1 +1,2 @@
 from __future__ import annotations
+git push origin main
"""


for name, proposal in (
    ("SAFE", SAFE_PROPOSAL),
    ("UNSAFE", UNSAFE_PROPOSAL),
):
    result = validate_patch_proposal(proposal)

    print("=" * 70)
    print(name)
    print()
    print("VALID:")
    print(result.valid)
    print()
    print("REASON:")
    print(result.reason)
    print()
    print("TARGET:")
    print(result.target_file or "<none>")
    print()

