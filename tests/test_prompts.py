"""Tests for the step-3 unknown-prompt variants (tuning step 3).

The variant system prompts are pre-registered in
openspec/changes/tune-unknown-prompt/design.md. These tests pin the exact
selection behavior of answer_messages: "base" is the current prompt,
"best_guess" and "cite_first" return their variant texts, an unknown
variant name falls back to "base", and the grounded re-read prompt is
unchanged. No LLM is called here — the tests check the messages the
(mocked) LLM would receive.
"""

from src.llm.prompts import (
    ANSWER_SYSTEM,
    GROUNDED_ANSWER_SYSTEM,
    answer_messages,
    grounded_answer_messages,
)


def _paras():
    return [{"title": "Maker", "sentences": ["Thon Marial Maker is a basketball player."]}]


def test_base_variant_returns_current_prompt():
    msgs = answer_messages("Who is Thon Maker?", _paras(), variant="base")
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == ANSWER_SYSTEM


def test_default_variant_is_base():
    msgs = answer_messages("Who is Thon Maker?", _paras())
    assert msgs[0]["content"] == ANSWER_SYSTEM


def test_best_guess_variant_text():
    msgs = answer_messages("Who is Thon Maker?", _paras(), variant="best_guess")
    text = msgs[0]["content"]
    assert "best short answer" in text
    assert "'unknown' only if" in text
    assert "even if you are not certain" in text
    assert text != ANSWER_SYSTEM


def test_cite_first_variant_text():
    msgs = answer_messages("Who is Thon Maker?", _paras(), variant="cite_first")
    text = msgs[0]["content"]
    assert "single sentence" in text
    assert "most relevant" in text
    assert text != ANSWER_SYSTEM


def test_unknown_variant_falls_back_to_base():
    msgs = answer_messages("Who is Thon Maker?", _paras(), variant="typo_variant")
    assert msgs[0]["content"] == ANSWER_SYSTEM


def test_grounded_reread_prompt_unchanged():
    msgs = grounded_answer_messages(
        "Who is Thon Maker?",
        [{"text": "Thon Marial Maker is a basketball player."}],
        _paras(),
    )
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == GROUNDED_ANSWER_SYSTEM
    assert "verified claims first" in msgs[0]["content"]
