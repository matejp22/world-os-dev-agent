from __future__ import annotations

from app.context_loader import load_project_context


context = load_project_context()

print("=" * 70)
print("WORLD OS DEV AGENT - PROJECT CONTEXT")
print("=" * 70)
print()
print(context)
print()
print("=" * 70)
print("CONTEXT LENGTH:")
print(len(context))
