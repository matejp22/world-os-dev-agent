from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import openai


FOCUSED_TARGET_MODULES = ("app.ai_full_file_revision",)


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_text="  revised candidate output  "
        )


class FakeOpenAI:
    def __init__(self) -> None:
        self.responses = FakeResponses()


def test_revise_candidate_uses_deterministic_revision_contract(
    monkeypatch,
) -> None:
    fake_client = FakeOpenAI()

    monkeypatch.setattr(
        openai,
        "OpenAI",
        lambda: fake_client,
    )

    sys.modules.pop(
        "app.ai_full_file_revision",
        None,
    )

    try:
        revision_module = importlib.import_module(
            "app.ai_full_file_revision"
        )

        monkeypatch.setattr(
            revision_module,
            "load_project_context",
            lambda: "deterministic project context",
        )

        goal = "Improve the revision workflow."
        target_file = "app/example.py"
        current_content = "print('current')"
        diff = "--- a/app/example.py\n+++ b/app/example.py"
        semantic_review = "Preserve safety boundaries."

        result = revision_module.revise_candidate(
            goal=goal,
            target_file=target_file,
            current_content=current_content,
            diff=diff,
            semantic_review=semantic_review,
        )

        assert result == "revised candidate output"
        assert len(fake_client.responses.calls) == 1

        call = fake_client.responses.calls[0]

        assert call["model"] == revision_module.MODEL
        assert call["reasoning"] == {"effort": "none"}
        assert call["instructions"] == revision_module.REVISION_PROMPT

        max_output_tokens = call["max_output_tokens"]
        assert isinstance(max_output_tokens, int)
        assert max_output_tokens >= 6000

        input_text = call["input"]
        assert isinstance(input_text, str)
        assert "deterministic project context" in input_text
        assert goal in input_text
        assert target_file in input_text
        assert current_content in input_text
        assert diff in input_text
        assert semantic_review in input_text
    finally:
        sys.modules.pop(
            "app.ai_full_file_revision",
            None,
        )