"""Phase 2.5 H12 — contested-claim resolution (tests first).

Tests for `find_contested` (pure), `contested_answer_messages` (prompt
builder), and the mocked end-to-end wiring in `run_erag`. Written before
the implementation; they fail until it lands.
"""

from unittest.mock import MagicMock

from src.llm.client import Tracker
from src.llm.prompts import contested_answer_messages
from src.systems.erag import find_contested, run_erag

_POOL = [{"title": "Paris", "sentences": ["Paris is the capital of France."],
          "text": "Paris. Paris is the capital of France."}]


def _claim(text, source="draft", status="supported", answer_bearing=False, eff=0.9):
    return {"text": text, "status": status, "source": source,
            "answer_bearing": answer_bearing, "eff": eff}


# ---------------------------------------------------------------------------
# A.1 — find_contested (pure function)
# ---------------------------------------------------------------------------

def test_find_contested_returns_both_sides_sorted_by_eff():
    claims = [
        _claim("Lyon is the capital.", source="draft", answer_bearing=True, eff=0.8),
        _claim("Paris is the capital of France.", source="question", eff=0.95),
        _claim("Lyon is a city in France.", source="question", eff=0.7),
    ]
    out = find_contested(claims, "Lyon")
    assert out is not None
    agreeing, disagreeing = out
    assert [c["text"] for c in agreeing] == ["Lyon is the capital."]
    # "Lyon is a city in France." is question-sourced but CONTAINS the
    # draft, so it is neither agreeing (not draft-sourced) nor disagreeing.
    assert [c["text"] for c in disagreeing] == ["Paris is the capital of France."]


def test_find_contested_unknown_draft_is_none():
    claims = [_claim("Paris is the capital.", source="draft", answer_bearing=True)]
    assert find_contested(claims, "unknown") is None
    assert find_contested(claims, "") is None


def test_find_contested_no_agreeing_claim_is_none():
    claims = [_claim("Paris is the capital of France.", source="question")]
    assert find_contested(claims, "Lyon") is None


def test_find_contested_no_disagreeing_claim_is_none():
    claims = [_claim("Lyon is the capital.", source="draft", answer_bearing=True)]
    assert find_contested(claims, "Lyon") is None


def test_find_contested_unresolved_agreeing_claim_is_none():
    claims = [
        _claim("Lyon is the capital.", source="draft", answer_bearing=True,
               status="unresolved"),
        _claim("Paris is the capital of France.", source="question"),
    ]
    assert find_contested(claims, "Lyon") is None


# ---------------------------------------------------------------------------
# A.2 — contested_answer_messages (prompt builder)
# ---------------------------------------------------------------------------

def test_contested_messages_lists_both_sides_separately():
    agreeing = [_claim("Lyon is the capital.", source="draft")]
    disagreeing = [_claim("Paris is the capital of France.", source="question")]
    msgs = contested_answer_messages("What is the capital of France?",
                                     agreeing, disagreeing, _POOL)
    user = msgs[1]["content"]
    assert "Lyon is the capital." in user
    assert "Paris is the capital of France." in user
    assert "What is the capital of France?" in user
    assert "Paris is the capital of France." in user  # context block present
    # The two sides are under separate headings.
    assert user.index("Lyon is the capital.") != user.index("Paris is the capital of France.")
    assert "different" in msgs[0]["content"].lower() or "disagree" in msgs[0]["content"].lower()


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


_CLAIMS_CONTESTED = (
    '{"claims": ['
    '{"text": "Lyon is the capital.", "answer": true, "depends_on": [], "source": "draft"}, '
    '{"text": "Paris is the capital of France.", "answer": false, "depends_on": [], "source": "question"}'
    ']}'
)


def _item():
    return {
        "_id": "test_contested_1",
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


def test_contested_reread_fires_and_replaces_draft():
    """Draft 'Lyon' agrees with the draft-sourced claim, but a supported
    question-sourced claim says Paris: contested -> 1 re-read, draft replaced."""
    llm = _CountingLLM(["Lyon", _CLAIMS_CONTESTED, "Paris"])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(),
                   _v1_gated_cfg(ground_final_read=True, contested_resolution=True), tr)
    assert tr.llm_calls == 3
    assert out["answer"] == "Paris"
    assert out["draft"] == "Paris"
    assert out["grounded_reread"] is True
    assert out["reread_trigger"] == "contested"
    assert out["reread_answer"] == "Paris"
    assert out["contested"] is True
    assert out["trace"][-1]["answer"] == "Lyon"


def test_no_contested_reread_when_flag_off():
    """Flag off: no extra call, no new fields — byte-identical to the tuned system."""
    llm = _CountingLLM(["Lyon", _CLAIMS_CONTESTED])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(),
                   _v1_gated_cfg(ground_final_read=True), tr)
    assert tr.llm_calls == 2
    assert out["answer"] == "Lyon"
    assert out["draft"] == "Lyon"
    assert out["grounded_reread"] is False
    assert out["reread_trigger"] is None
    assert "contested" not in out


def test_contested_reread_returning_unknown_keeps_draft():
    """Contested re-read returns 'unknown' -> original draft stands."""
    llm = _CountingLLM(["Lyon", _CLAIMS_CONTESTED, "unknown"])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(),
                   _v1_gated_cfg(ground_final_read=True, contested_resolution=True), tr)
    assert tr.llm_calls == 3
    assert out["answer"] == "Lyon"
    assert out["draft"] == "Lyon"
    assert out["grounded_reread"] is True
    assert out["reread_trigger"] == "contested"
    assert out["reread_answer"] == "unknown"
    assert out["contested"] is True
