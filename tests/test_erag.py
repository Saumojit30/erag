from unittest.mock import MagicMock
from src.llm.client import Tracker
from src.systems.erag import build_graph, conf_value, propose_queries, run_erag, targeted_retrieve


def test_propose_queries():
    llm = MagicMock()
    llm.chat.return_value = "Where was Marie Curie born?\nMarie Curie birthplace university\nWarsaw Poland history"
    tr = Tracker()

    queries = propose_queries(llm, "Marie Curie was born in Warsaw.", tr, n=3)
    assert len(queries) == 3
    assert queries[0] == "Where was Marie Curie born?"


def test_conf_value():
    sc = {"conf_majority": 0.8, "conf_draft_agreement": 0.6}
    assert conf_value(sc, {"erag": {"confidence_def": "majority"}}) == 0.8
    assert conf_value(sc, {"erag": {"confidence_def": "draft_agreement"}}) == 0.6


def test_targeted_retrieve():
    llm = MagicMock()
    llm.chat.return_value = "Query 1\nQuery 2"
    retriever = MagicMock()
    # Query 1 returns already seen doc; Query 2 returns novel doc
    retriever.search.side_effect = [
        [{"title": "Doc Seen", "sentences": ["Old."]}],
        [{"title": "Doc Novel", "sentences": ["New info."]}],
    ]

    claim = MagicMock()
    claim.text = "Sample claim text"
    claim.eff = 0.4
    pool = [{"title": "Doc Seen", "sentences": ["Old."]}]
    tr = Tracker()

    novel = targeted_retrieve(llm, retriever, claim, pool, k=3, ablate=set(), tracker=tr)
    assert len(novel) == 1
    assert novel[0]["title"] == "Doc Novel"
    assert tr.probe_searches == 2
    assert tr.retrievals == 1


def test_run_erag_observational_mode():
    item = {
        "_id": "test_obs_1",
        "question": "What is the capital of France?",
        "context": [["Paris", ["Paris is the capital of France."]]],
        "supporting_facts": [["Paris", 0]],
    }
    retriever = MagicMock()
    retriever.search.return_value = [{"title": "Paris", "sentences": ["Paris is the capital of France."], "text": "Paris. Paris is the capital of France."}]

    llm = MagicMock()
    llm.chat.side_effect = [
        "Paris",        # Hop 0 draft
        "Paris", "Paris", "Paris", "Paris", "Paris",  # 5 self-consistency samples
        '{"claims": [{"text": "Paris is the capital.", "answer": true, "depends_on": []}]}',  # Claim extraction
    ]

    nli = MagicMock()
    nli.verify.return_value = {"status": "supported", "conflict": False, "sup": [("Paris", 0.9)], "con": []}

    cfg = {
        "retrieval": {"k": 3},
        "nli": {"theta_s": 0.5, "theta_c": 0.5},
        "erag": {
            "mode": "observe",
            "max_hops": 2,
            "sc_samples": 5,
            "sc_temperature": 0.7,
            "theta_fast": 0.8,
            "theta_gap": 0.6,
            "theta_abs": 0.4,
            "max_claims": 5,
            "pool_cap": 12,
        },
    }
    tr = Tracker()

    out = run_erag(item, retriever, llm, nli, cfg, tr)

    assert out["answer"] == "Paris"
    assert out["draft"] == "Paris"
    assert out["hops"] == 0  # Observe mode stops at hop 0
    assert out["abstained"] is False
    assert out["answer_conf"] > 0.5


# ---------------------------------------------------------------------------
# TrueAdaptive v1 — call-count tests (audit §12 Step B).
#
# The real LLM.chat() increments tracker.llm_calls on every call (including
# cache hits). A plain MagicMock does NOT, so these tests use a counting
# mock that mirrors that behaviour: each chat() increments the tracker and
# returns the next scripted response in order. If the code makes an extra
# LLM call the mock runs out of responses (StopIteration) — that is an
# intentional loud failure, not a flaky mock.
# ---------------------------------------------------------------------------

_CLAIMS_JSON = '{"claims": [{"text": "Paris is the capital.", "answer": true, "depends_on": []}]}'
_POOL = [{"title": "Paris", "sentences": ["Paris is the capital of France."], "text": "Paris. Paris is the capital of France."}]
_NOVEL = [{"title": "Lyon", "sentences": ["Lyon is a city in France."], "text": "Lyon. Lyon is a city in France."}]


class _CountingLLM:
    """Mock LLM mirroring LLM.chat: every chat() counts as one LLM call."""

    def __init__(self, responses):
        self._it = iter(responses)
        self.n_calls = 0

    def chat(self, messages, tracker, **kwargs):
        tracker.llm_calls += 1
        self.n_calls += 1
        return next(self._it)


def _item():
    return {
        "_id": "test_cc_1",
        "question": "What is the capital of France?",
        "context": [["Paris", ["Paris is the capital of France."]]],
        "supporting_facts": [["Paris", 0]],
    }


def _supported_nli():
    nli = MagicMock()
    nli.verify.return_value = {"status": "supported", "conflict": False, "sup": [("Paris", 0.9)], "con": []}
    return nli


def _unresolved_then_supported_nli():
    """Unresolved while the pool has only the Paris passage (evidence
    missing, forces a hop); supported once retrieval has added Lyon.

    Deliberately a function of the pool, not of call count: real NLI is
    deterministic for a given (claim, pool), so the provisional graph and
    a rebuilt graph on the same pool must agree — a call-count mock would
    make the rebuilt graph flip to supported on identical evidence.
    """
    nli = MagicMock()

    def _verify(text, passages, **kwargs):
        titles = [p.get("title") for p in (passages or [])]
        if "Lyon" in titles:
            return {"status": "supported", "conflict": False, "sup": [("Paris", 0.9)], "con": []}
        return {"status": "unresolved", "conflict": False, "sup": [], "con": []}

    nli.verify.side_effect = _verify
    return nli


def _cfg(**erag_overrides):
    erag = {
        "mode": "active",
        "max_hops": 2,
        "sc_samples": 5,
        "sc_temperature": 0.7,
        "theta_fast": 0.8,
        "theta_gap": 0.6,
        "theta_abs": 0.4,
        "max_claims": 5,
        "pool_cap": 12,
    }
    erag.update(erag_overrides)
    return {
        "retrieval": {"k": 3},
        "nli": {"theta_s": 0.5, "theta_c": 0.5},
        "erag": erag,
    }


def test_call_count_fast_path_reference():
    """Reference config, hop-0 Fast Path: 1 draft + 5 SC + 1 claims = 7 calls."""
    llm = _CountingLLM(["Paris"] + ["Paris"] * 5 + [_CLAIMS_JSON])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(), _cfg(), tr)
    assert tr.llm_calls == 7
    assert llm.n_calls == 7
    assert out["hops"] == 0
    assert out["answer"] == "Paris"


def test_call_count_fast_path_balanced():
    """Balanced config, hop-0 Fast Path: 1 draft + 3 SC + 1 claims = 5 calls."""
    cfg = _cfg(
        sc_samples=3,
        claim_strategy="incremental",
        post_hop_resample="conditional",
        eig_strategy="llm",
        saturation_precheck=True,
    )
    llm = _CountingLLM(["Paris"] + ["Paris"] * 3 + [_CLAIMS_JSON])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(), cfg, tr)
    assert tr.llm_calls == 5
    assert out["hops"] == 0
    assert out["answer"] == "Paris"


def test_call_count_one_hop_balanced():
    """Balanced, 1 hop, draft unchanged: 5 (hop 0) + 1 EIG + 1 draft = 7 calls."""
    cfg = _cfg(
        sc_samples=3,
        claim_strategy="incremental",
        post_hop_resample="conditional",
        eig_strategy="llm",
        saturation_precheck=True,
    )
    llm = _CountingLLM(
        ["Paris"] + ["Paris"] * 3 + [_CLAIMS_JSON, "Q1\nQ2\nQ3", "Paris"]
    )
    retriever = MagicMock()
    # initial retrieval, then 3 EIG probe searches (Q1 novel, Q2/Q3 seen)
    retriever.search.side_effect = [list(_POOL), list(_NOVEL), list(_POOL), list(_POOL)]
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _unresolved_then_supported_nli(), cfg, tr)
    assert tr.llm_calls == 7
    assert out["hops"] == 1
    assert out["answer"] == "Paris"


def test_sequential_consistency_stops_at_two_on_agreement():
    from src.epistemic.confidence import sequential_consistency

    llm = _CountingLLM(["Paris", "Paris", "London"])
    tr = Tracker()
    sc = sequential_consistency(llm, "What is the capital of France?", list(_POOL), "Paris", tr, k=3)
    assert tr.llm_calls == 2
    assert sc["n_samples"] == 2
    assert sc["samples"] == ["Paris", "Paris"]
    assert sc["conf_majority"] == 1.0
    assert sc["conf_draft_agreement"] == 1.0


def test_sequential_consistency_goes_to_three_on_split():
    from src.epistemic.confidence import sequential_consistency

    llm = _CountingLLM(["Paris", "London", "Paris"])
    tr = Tracker()
    sc = sequential_consistency(llm, "What is the capital of France?", list(_POOL), "Paris", tr, k=3)
    assert tr.llm_calls == 3
    assert sc["n_samples"] == 3
    assert sc["conf_majority"] == 2 / 3


def test_sequential_consistency_same_return_shape():
    from src.epistemic.confidence import sequential_consistency, self_consistency

    llm = _CountingLLM(["Paris", "Paris", "Paris", "Paris", "Paris"])
    tr = Tracker()
    seq = sequential_consistency(llm, "What is the capital of France?", list(_POOL), "Paris", tr, k=3)
    for key in ("conf_majority", "conf_draft_agreement", "samples"):
        assert key in seq
    # Fixed sampling still fires all k samples even when unanimous.
    llm2 = _CountingLLM(["Paris"] * 5)
    tr2 = Tracker()
    fixed = self_consistency(llm2, "What is the capital of France?", list(_POOL), "Paris", tr2, k=5)
    assert tr2.llm_calls == 5
    assert fixed["conf_majority"] == 1.0


def test_call_count_sc_skipped_on_fast_path():
    """v1 gated SC, hop-0 Fast Path: 1 draft + 1 claims = 2 calls, no SC."""
    cfg = _cfg(
        sc_samples=3,
        sc_mode="sequential",
        gate_sc_behind_fast_path=True,
        claim_strategy="incremental",
        post_hop_resample="never",
        eig_strategy="direct",
        saturation_precheck=True,
    )
    llm = _CountingLLM(["Paris", _CLAIMS_JSON])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(), cfg, tr)
    assert tr.llm_calls == 2
    assert llm.n_calls == 2
    assert out["hops"] == 0
    assert out["answer"] == "Paris"
    assert out["sc_skipped_fast_path"] is True
    assert out["c0_source"] == "fast_path_min_eff"
    # c0 falls back to the graph's own min_eff when SC is skipped.
    assert out["c0"] == out["answer_conf"]


def test_call_count_v1_one_hop():
    """v1 (sequential SC + gated SC), 1 hop: hop 0 = 1 draft + 2 SC + 1 claims, hop 1 = 1 draft = 5 calls."""
    cfg = _cfg(
        sc_samples=3,
        sc_mode="sequential",
        gate_sc_behind_fast_path=True,
        claim_strategy="incremental",
        post_hop_resample="never",
        eig_strategy="direct",
        saturation_precheck=True,
    )
    # Gated order on hop 0: draft, claims, THEN sequential SC (2 samples,
    # agreeing), then hop-1 draft. EIG is direct, so no query-generation call.
    llm = _CountingLLM(["Paris", _CLAIMS_JSON, "Paris", "Paris", "Paris"])
    retriever = MagicMock()
    # initial retrieval, then 1 direct-EIG probe search (novel doc)
    retriever.search.side_effect = [list(_POOL), list(_NOVEL)]
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _unresolved_then_supported_nli(), cfg, tr)
    assert tr.llm_calls == 5
    assert out["hops"] == 1
    assert out["answer"] == "Paris"

