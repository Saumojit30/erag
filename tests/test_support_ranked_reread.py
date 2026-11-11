"""Phase 2.6 H15 — support-ranked final re-read (tests first).

Tests for `find_top_supported_rival` (pure), `support_ranked_answer_messages`
(prompt builder), and the mocked end-to-end wiring in `run_erag`. Written
before the implementation; they fail until it lands.
"""

from unittest.mock import MagicMock

from src.llm.client import Tracker
from src.llm.prompts import support_ranked_answer_messages
from src.systems.erag import find_top_supported_rival, run_erag

_POOL = [{"title": "Paris", "sentences": ["Paris is the capital of France."],
          "text": "Paris. Paris is the capital of France."}]


def _claim(text, status="supported", eff=0.9):
    return {"text": text, "status": status, "eff": eff}


# ---------------------------------------------------------------------------
# A.1 — find_top_supported_rival (pure function)
# ---------------------------------------------------------------------------

def test_rival_returns_none_when_draft_in_top3():
    claims = [
        _claim("Lyon is the capital.", eff=0.95),
        _claim("Paris is the capital of France.", eff=0.9),
        _claim("Lyon is a city in France.", eff=0.8),
    ]
    assert find_top_supported_rival(claims, "Lyon") is None


def test_rival_returns_top3_sorted_by_eff_when_draft_absent():
    claims = [
        _claim("Paris is the capital of France.", eff=0.98),
        _claim("Paris hosted the 2024 Olympics.", eff=0.95),
        _claim("Lyon is the capital.", eff=0.8),
        _claim("Paris is in France.", eff=0.92),
    ]
    out = find_top_supported_rival(claims, "Lyon")
    assert out is not None
    assert [c["text"] for c in out] == [
        "Paris is the capital of France.",
        "Paris hosted the 2024 Olympics.",
        "Paris is in France.",
    ]


def test_rival_no_supported_claims_is_none():
    claims = [_claim("Lyon is the capital.", status="unresolved")]
    assert find_top_supported_rival(claims, "Lyon") is None


def test_rival_unknown_draft_is_none():
    claims = [_claim("Paris is the capital of France.", eff=0.95)]
    assert find_top_supported_rival(claims, "unknown") is None
    assert find_top_supported_rival(claims, "") is None


def test_rival_top_k_parameter():
    claims = [
        _claim("Paris is the capital of France.", eff=0.99),
        _claim("Paris hosted the 2024 Olympics.", eff=0.98),
        _claim("Paris is in France.", eff=0.97),
        _claim("Paris has the Eiffel Tower.", eff=0.96),
        _claim("Paris is on the Seine.", eff=0.95),
        _claim("Lyon is the capital.", eff=0.8),
    ]
    # Draft is 6th by eff: absent from top-5, present in top-6.
    assert find_top_supported_rival(claims, "Lyon", k=5) is not None
    assert find_top_supported_rival(claims, "Lyon", k=5) is not None
    assert len(find_top_supported_rival(claims, "Lyon", k=5)) == 5
    assert find_top_supported_rival(claims, "Lyon", k=6) is None


# ---------------------------------------------------------------------------
# A.2 — support_ranked_answer_messages (prompt builder)
# ---------------------------------------------------------------------------

def test_ranked_messages_lists_only_top_claims():
    top = [
        _claim("Paris is the capital of France."),
        _claim("Paris hosted the 2024 Olympics."),
    ]
    msgs = support_ranked_answer_messages("What is the capital of France?",
                                          top, _POOL)
    user = msgs[1]["content"]
    assert "Paris is the capital of France." in user
    assert "Paris hosted the 2024 Olympics." in user
    assert "What is the capital of France?" in user
    assert "Paris is the capital of France." in user  # context block present
    assert "only" in msgs[0]["content"].lower() or "these" in msgs[0]["content"].lower()


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


# Three rival claims first, the draft's own claim last: with equal effs the
# stable sort keeps insertion order, so the top-3 are the Paris claims and
# the draft "Lyon" is unbacked -> the re-read fires.
_CLAIMS_RIVAL = (
    '{"claims": ['
    '{"text": "Paris is the capital of France.", "answer": false, "depends_on": [], "source": "question"}, '
    '{"text": "Paris hosted the 2024 Olympics.", "answer": false, "depends_on": [], "source": "question"}, '
    '{"text": "Paris is in France.", "answer": false, "depends_on": [], "source": "question"}, '
    '{"text": "Lyon is the capital.", "answer": true, "depends_on": [], "source": "draft"}'
    ']}'
)

# Draft's own claim first: the top-3 back the draft -> no re-read.
_CLAIMS_BACKED = (
    '{"claims": ['
    '{"text": "Lyon is the capital.", "answer": true, "depends_on": [], "source": "draft"}, '
    '{"text": "Paris is the capital of France.", "answer": false, "depends_on": [], "source": "question"}'
    ']}'
)


def _item():
    return {
        "_id": "test_ranked_1",
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


def test_ranked_reread_fires_and_replaces_draft():
    """Draft 'Lyon' is unbacked by the top-3 supported claims (all Paris):
    one re-read grounded on the top-3, draft replaced."""
    llm = _CountingLLM(["Lyon", _CLAIMS_RIVAL, "Paris"])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(),
                   _v1_gated_cfg(ground_final_read=True, support_ranked_reread=True), tr)
    assert tr.llm_calls == 3
    assert out["answer"] == "Paris"
    assert out["draft"] == "Paris"
    assert out["grounded_reread"] is True
    assert out["reread_trigger"] == "support_ranked"
    assert out["reread_answer"] == "Paris"
    assert out["support_ranked"] is True
    assert out["trace"][-1]["answer"] == "Lyon"


def test_no_ranked_reread_when_flag_off():
    """Flag off: no extra call, no new fields — byte-identical to the improved system."""
    llm = _CountingLLM(["Lyon", _CLAIMS_RIVAL])
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
    assert "support_ranked" not in out


def test_no_ranked_reread_when_draft_backed():
    """Draft's own claim is in the top-3: trigger absent, no extra call."""
    llm = _CountingLLM(["Lyon", _CLAIMS_BACKED])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(),
                   _v1_gated_cfg(ground_final_read=True, support_ranked_reread=True), tr)
    assert tr.llm_calls == 2
    assert out["answer"] == "Lyon"
    assert out["draft"] == "Lyon"
    assert out["grounded_reread"] is False
    assert out["reread_trigger"] is None
    assert out["support_ranked"] is False


def test_ranked_reread_returning_unknown_keeps_draft():
    """Support-ranked re-read returns 'unknown' -> original draft stands."""
    llm = _CountingLLM(["Lyon", _CLAIMS_RIVAL, "unknown"])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(),
                   _v1_gated_cfg(ground_final_read=True, support_ranked_reread=True), tr)
    assert tr.llm_calls == 3
    assert out["answer"] == "Lyon"
    assert out["draft"] == "Lyon"
    assert out["grounded_reread"] is True
    assert out["reread_trigger"] == "support_ranked"
    assert out["reread_answer"] == "unknown"
    assert out["support_ranked"] is True
