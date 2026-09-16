from __future__ import annotations

import inspect
import sys

FOCUSED_TARGET_MODULES = ("app.console",)


def test_console_focused_target_declaration() -> None:
    assert FOCUSED_TARGET_MODULES == ("app.console",)


def test_canonical_approval_confirmation_phrase_is_nonempty() -> None:
    from app.full_file_approval import CONFIRM_PHRASE

    assert isinstance(CONFIRM_PHRASE, str)
    assert CONFIRM_PHRASE.strip()


def test_canonical_approve_record_signature_supports_console_contract() -> None:
    from app.full_file_approval import approve_record

    signature = inspect.signature(approve_record)

    assert "patch_id" in signature.parameters
    assert "confirmation" in signature.parameters

    confirmation = signature.parameters["confirmation"]

    assert confirmation.kind in {
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    }


def test_console_contract_can_reference_backend_without_importing_console() -> None:
    assert "app.console" not in sys.modules

    from app.full_file_approval import CONFIRM_PHRASE, approve_record

    assert isinstance(CONFIRM_PHRASE, str)
    assert callable(approve_record)
    assert "app.console" not in sys.modules


def test_registry_selects_this_test_for_console_change() -> None:
    from app.test_registry import (
        inspect_repository_test_registry,
        plan_test_selection,
    )

    registry = inspect_repository_test_registry(
        "world-os-dev-agent"
    )

    plan = plan_test_selection(
        registry,
        ("app/console.py",),
    )

    assert "test_console_approval" in plan.focused_test_ids

    entry = next(
        entry
        for entry in registry.tests
        if entry.test_id == "test_console_approval"
    )

    assert "app.console" in entry.declared_focused_modules