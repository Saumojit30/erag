"""Phase 2.7 H18 — evidence-first answering (tests first).

Tests for `extract_evidence_claims` (passage claims, no draft input),
`compose_answer_messages` (claims-only compose, no context block), and
the mocked end-to-end wiring in `run_erag`. Written before the
implementation; they fail until it lands.
"""

from unittest.mock import MagicMock

from src.epistemic.claims import extract_evidence_claims
from src.llm.client import Tracker
from src.llm.prompts import COMPOSE_SYSTEM, compose_answer_messages
from src.systems.erag import run_erag

_POOL = [{"title": "Paris", "sentences": ["Paris is the capital of France."],
          "text": "Paris. Paris is the capital of France."}]
_POOL2 = [{"title": "Lyon", "sentences": ["Lyon is a city in France."],
           "text": "Lyon. Lyon is a city in France."}]


def _claim(text, status="supported", eff=0.9):
    return {"text": text, "status": status, "eff": eff}


# ---------------------------------------------------------------------------
# A.1a — extract_evidence_claims (pure-ish: mocked LLM)
# ---------------------------------------------------------------------------

_CLAIMS_EVIDENCE = (
    '{"claims": ['
    '{"text": "Paris is the capital of France.", "answer": true, "depends_on": [], "source": "question"}, '
    '{"text": "Lyon is a city in France.", "answer": false, "depends_on": [], "source": "question"}'
    ']}'
)


def test_evidence_claims_come_from_passages_not_draft():
    llm = MagicMock()
    llm.chat.return_value = _CLAIMS_EVIDENCE
    tr = Tracker()
    claims = extract_evidence_claims(llm, "What is the capital of France?",
                                     _POOL, tr, max_claims=5)
    assert len(claims) == 2
    assert claims[0]["text"] == "Paris is the capital of France."
    assert claims[0]["answer_bearing"] is True
    assert all(c["source"] == "question" for c in claims)
    # The extractor never sees a draft: no Answer input in its messages.
    user = llm.chat.call_args[0][0][1]["content"]
    assert "Answer:" not in user
    assert "What is the capital of France?" in user
    assert "Paris is the capital of France." in user


def test_evidence_claims_empty_parse_yields_no_claims():
    """A failed passage extraction yields no claims — there is no draft
    yet for a fallback atomic claim to state."""
    llm = MagicMock()
    llm.chat.return_value = "not json at all"
    tr = Tracker()
    assert extract_evidence_claims(llm, "What is the capital of France?",
                                   _POOL, tr, max_claims=5) == []


# ---------------------------------------------------------------------------
# A.1b — compose_answer_messages (prompt builder)
# ---------------------------------------------------------------------------

def test_compose_messages_claims_only_no_context():
    claims = [
        _claim("Paris is the capital of France."),
        _claim("Paris hosted the 2024 Olympics."),
    ]
    msgs = compose_answer_messages("What is the capital of France?", claims)
    assert msgs[0]["content"] == COMPOSE_SYSTEM
    user = msgs[1]["content"]
    assert "Paris is the capital of France." in user
    assert "Paris hosted the 2024 Olympics." in user
    assert "What is the capital of France?" in user
    # The restriction is the mechanism: no context block for the reader
    # to fall back on (unlike support_ranked_answer_messages).
    assert "Context:" not in user
    assert "only" in msgs[0]["content"].lower()


# ---------------------------------------------------------------------------
# A.1c — mocked end-to-end wiring in run_erag
# ---------------------------------------------------------------------------

class _CountingLLM:
    """Mock LLM mirroring LLM.chat: every chat() counts as one LLM call."""

    def __init__(self, responses):
        self._it = iter(responses)
        self.n_calls = 0
        self.systems = []

    def chat(self, messages, tracker, **kwargs):
        tracker.llm_calls += 1
        self.n_calls += 1
        self.systems.append(messages[0]["content"])
        return next(self._it)


def _item():
    return {
        "_id": "test_evidence_first_1",
        "question": "What is the capital of France?",
        "context": [["Paris", ["Paris is the capital of France."]]],
        "supporting_facts": [["Paris", 0]],
    }


def _supported_nli():
    nli = MagicMock()
    nli.verify.return_value = {"status": "supported", "conflict": False,
                               "sup": [("Paris", 0.9)], "con": []}
    return nli


def _unresolved_nli():
    nli = MagicMock()
    nli.verify.return_value = {"status": "unresolved", "conflict": False,
                               "sup": [], "con": []}
    return nli


def _cfg(**erag_overrides):
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
        "gate_sc_behind_fast_path": False,
        "claim_strategy": "incremental",
        "post_hop_resample": "never",
        "eig_strategy": "direct",
        "saturation_precheck": True,
    }
    erag.update(erag_overrides)
    return {"retrieval": {"k": 3}, "nli": {"theta_s": 0.5, "theta_c": 0.5}, "erag": erag}


def test_evidence_first_composes_draft_from_supported_claims():
    """Hop order is extract -> compose -> SC: the first call is the
    extractor (not a draft), the second is the compose, then 2 SC
    samples that stop early on agreement. No draft call is made."""
    llm = _CountingLLM([_CLAIMS_EVIDENCE, "Paris", "Paris", "Paris"])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(),
                   _cfg(evidence_first=True), tr)
    assert tr.llm_calls == 4
    assert llm.systems[0].startswith("List the short factual claims from the Context")
    assert llm.systems[1] == COMPOSE_SYSTEM
    assert out["answer"] == "Paris"
    assert out["draft"] == "Paris"
    assert out["trace"][0]["answer"] == "Paris"
    assert out["evidence_first"] is True
    assert out["c0_source"] == "sc"


def test_evidence_first_no_supported_claim_means_unknown_no_compose():
    """No supported claim: no compose call, draft 'unknown', loop
    continues on gaps (here the retriever finds nothing new)."""
    llm = _CountingLLM([_CLAIMS_EVIDENCE, "unknown", "unknown"])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _unresolved_nli(),
                   _cfg(evidence_first=True), tr)
    assert tr.llm_calls == 3
    assert COMPOSE_SYSTEM not in llm.systems
    assert out["draft"] == "unknown"
    assert out["answer"] == "unknown"
    assert out["evidence_first"] is True


def test_evidence_first_flag_off_is_byte_identical():
    """Flag off: the normal draft-first path runs, no extra call, no
    `evidence_first` field."""
    llm = _CountingLLM(["Lyon", "Lyon", "Lyon", _CLAIMS_EVIDENCE])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(), _cfg(), tr)
    assert tr.llm_calls == 4
    assert out["answer"] == "Lyon"
    assert out["draft"] == "Lyon"
    assert "evidence_first" not in out


def test_evidence_first_hop1_reextracts_from_enlarged_pool():
    """Hop 0 finds nothing supported, retrieval enlarges the pool, and
    hop 1 re-extracts passage claims from the full pool (no incremental
    reuse) instead of reusing hop-0 claims."""
    llm = _CountingLLM([_CLAIMS_EVIDENCE, "unknown", "unknown",
                        _CLAIMS_EVIDENCE, "Paris"])
    retriever = MagicMock()
    retriever.search.side_effect = [list(_POOL), list(_POOL2), list(_POOL2)]
    nli = MagicMock()
    unres = {"status": "unresolved", "conflict": False, "sup": [], "con": []}
    sup = {"status": "supported", "conflict": False,
           "sup": [("Paris", 0.9)], "con": []}
    # Hop 0: provisional graph (2) + rebuild after SC (2) unresolved;
    # hop 1: provisional graph (2) + final rebuild (2) supported.
    nli.verify.side_effect = [unres, unres, unres, unres,
                              sup, sup, sup, sup]
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, nli, _cfg(evidence_first=True), tr)
    assert tr.llm_calls == 5
    assert retriever.search.call_count >= 2
    assert out["hops"] == 1
    assert out["draft"] == "Paris"
    assert out["answer"] == "Paris"
    assert out["evidence_first"] is True
