"""Phase 2.5 H13 — extraction recall, second pass (tests first).

Tests for `merge_claims` (pure), `second_pass_messages` (prompt
builder), and the mocked end-to-end wiring in `run_erag`. Written before
the implementation; they fail until it lands.
"""

from unittest.mock import MagicMock

from src.epistemic.claims import merge_claims, second_pass_messages
from src.llm.client import Tracker
from src.systems.erag import run_erag

_POOL = [{"title": "Paris", "sentences": ["Paris is the capital of France."],
          "text": "Paris. Paris is the capital of France."}]


def _claim(text, source="draft", answer_bearing=False):
    return {"text": text, "source": source, "answer_bearing": answer_bearing,
            "depends_on": [], "fallback": False}


# ---------------------------------------------------------------------------
# A.1 — merge_claims (pure function)
# ---------------------------------------------------------------------------

def test_merge_drops_duplicate_normalized_text():
    existing = [_claim("Paris is the capital.")]
    additional = [_claim("Paris is the capital", source="question"),
                  _claim("Lyon is a city in France.", source="question")]
    merged = merge_claims(existing, additional)
    assert [c["text"] for c in merged] == [
        "Paris is the capital.", "Lyon is a city in France."]


def test_merge_appends_new_claims_in_order():
    existing = [_claim("Paris is the capital.")]
    additional = [_claim("Paris is in France.", source="question"),
                  _claim("France is in Europe.", source="question")]
    merged = merge_claims(existing, additional)
    assert len(merged) == 3
    assert merged[0]["text"] == "Paris is the capital."
    assert merged[1]["text"] == "Paris is in France."


def test_merge_empty_additional_is_noop():
    existing = [_claim("Paris is the capital.")]
    assert merge_claims(existing, []) == existing


def test_merge_article_differences_count_as_duplicates():
    existing = [_claim("Paris is the capital of France.")]
    additional = [_claim("Paris is capital of France.", source="question")]
    assert len(merge_claims(existing, additional)) == 1


# ---------------------------------------------------------------------------
# A.2 — second_pass_messages (prompt builder)
# ---------------------------------------------------------------------------

def test_second_pass_messages_lists_existing_claims_and_asks_for_more():
    existing = [_claim("Paris is the capital.")]
    msgs = second_pass_messages("What is the capital of France?", "Paris",
                                existing, _POOL)
    user = msgs[1]["content"]
    assert "Paris is the capital." in user  # existing claims listed
    assert "What is the capital of France?" in user
    assert "Paris is the capital of France." in user  # context present
    system = msgs[0]["content"].lower()
    assert "not already" in system or "additional" in system


# ---------------------------------------------------------------------------
# A.2b — second-pass source default (spec scenario)
# ---------------------------------------------------------------------------

def test_second_pass_missing_source_defaults_to_question():
    """Claims without a source field from the second pass are recorded as
    question-sourced; an explicit 'draft' is kept as-is."""
    from src.epistemic.claims import extract_claims_second_pass
    llm = _CountingLLM([
        '{"claims": ['
        '{"text": "Paris is in France.", "answer": false, "depends_on": []}, '
        '{"text": "Paris is the capital.", "answer": true, "depends_on": [], "source": "draft"}'
        ']}'
    ])
    tr = Tracker()
    out = extract_claims_second_pass(llm, "What is the capital of France?",
                                     "Paris", _POOL, [], tr, max_claims=5)
    assert out[0]["source"] == "question"
    assert out[1]["source"] == "draft"


# ---------------------------------------------------------------------------
# A.3 — mocked end-to-end wiring in run_erag
# ---------------------------------------------------------------------------

class _CountingLLM:
    """Mock LLM mirroring LLM.chat: every chat() counts as one LLM call."""

    def __init__(self, responses):
        self._it = iter(responses)
        self.n_calls = 0

    def chat(self, messages, tracker, **kwargs):
        tracker.llm_calls += 1
        self.n_calls += 1
        return next(self._it)


_CLAIMS_FIRST = (
    '{"claims": ['
    '{"text": "Paris is the capital.", "answer": true, "depends_on": [], "source": "draft"}'
    ']}'
)
_CLAIMS_SECOND = (
    '{"claims": ['
    '{"text": "Paris is the capital.", "answer": false, "depends_on": [], "source": "question"}, '
    '{"text": "Paris is in France.", "answer": false, "depends_on": [], "source": "question"}'
    ']}'
)


def _item():
    return {
        "_id": "test_h13_1",
        "question": "What is the capital of France?",
        "context": [["Paris", ["Paris is the capital of France."]]],
        "supporting_facts": [["Paris", 0]],
    }


def _supported_nli():
    nli = MagicMock()
    nli.verify.return_value = {"status": "supported", "conflict": False,
                               "sup": [("Paris", 0.9)], "con": []}
    return nli


def _v1_gated_cfg(**erag_overrides):
    erag = {
        "mode": "active",
        "max_hops": 2,
        "sc_samples": 3,
        "sc_temperature": 0.7,
        "theta_fast": 0.8,
        "theta_gap": 0.6,
        "theta_abs": 0.4,
        "max_claims": 5,
        "pool_cap": 12,
        "sc_mode": "sequential",
        "gate_sc_behind_fast_path": True,
        "claim_strategy": "incremental",
        "post_hop_resample": "never",
        "eig_strategy": "direct",
        "saturation_precheck": True,
    }
    erag.update(erag_overrides)
    return {"retrieval": {"k": 3}, "nli": {"theta_s": 0.5, "theta_c": 0.5}, "erag": erag}


def test_second_pass_adds_one_new_claim_and_costs_one_call():
    """Hop 0: draft + first extraction + second pass (1 new + 1 duplicate)
    -> graph has 2 claims, second_pass_added == 1, 3 calls total."""
    llm = _CountingLLM(["Paris", _CLAIMS_FIRST, _CLAIMS_SECOND])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(),
                   _v1_gated_cfg(ground_final_read=True, second_extraction=True), tr)
    assert tr.llm_calls == 3
    assert out["answer"] == "Paris"
    assert out["second_extraction"] is True
    assert out["second_pass_added"] == 1
    assert len(out["trace"][0]["graph"]) == 2
    assert out["trace"][0]["graph"][1]["text"] == "Paris is in France."


def test_no_second_pass_when_flag_off():
    """Flag off: no extra call, no new fields — identical to the base system."""
    llm = _CountingLLM(["Paris", _CLAIMS_FIRST])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(),
                   _v1_gated_cfg(ground_final_read=True), tr)
    assert tr.llm_calls == 2
    assert out["answer"] == "Paris"
    assert "second_pass_added" not in out
    assert "second_extraction" not in out
    assert len(out["trace"][0]["graph"]) == 1
