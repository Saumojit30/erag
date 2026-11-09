import json
import math
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.llm.client import Tracker
from src.systems.erag import build_graph, conf_value, propose_queries, run_erag, targeted_retrieve

REPO_ROOT = Path(__file__).resolve().parents[1]
_POLICY_ARTIFACT = REPO_ROOT / "configs" / "continuation_policy_dev.json"
_DEV_THETA_A = REPO_ROOT / "results/trueadaptive/erag_trueadaptive_bm25_dev_theta_a.jsonl"
_DEV_MANIFEST = REPO_ROOT / "data/manifests/dev.jsonl"
_TRAINING_FILE = REPO_ROOT / "data/continuation_training_dev.jsonl"


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


# ---------------------------------------------------------------------------
# Tune-reader-grounding (step 1) — conditional claim-grounded re-read
# (tasks.md A.1). Tests first: mocked LLM on the v1 fast-path base (2 calls:
# 1 draft + 1 claims, SC skipped). The re-read is the 3rd call when it fires.
# ---------------------------------------------------------------------------

def _v1_gated_cfg(**erag_overrides):
    return _cfg(
        sc_samples=3,
        sc_mode="sequential",
        gate_sc_behind_fast_path=True,
        claim_strategy="incremental",
        post_hop_resample="never",
        eig_strategy="direct",
        saturation_precheck=True,
        **erag_overrides,
    )


def test_reread_triggered_on_unknown_draft():
    """Draft 'unknown' + supported answer claim -> 1 re-read, draft replaced."""
    llm = _CountingLLM(["unknown", _CLAIMS_JSON, "Paris"])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(), _v1_gated_cfg(ground_final_read=True), tr)
    assert tr.llm_calls == 3
    assert out["answer"] == "Paris"
    assert out["draft"] == "Paris"
    assert out["grounded_reread"] is True
    assert out["reread_trigger"] == "unknown"
    assert out["reread_answer"] == "Paris"
    # Original draft stays inspectable in the trace's last hop entry.
    assert out["trace"][-1]["answer"] == "unknown"


def test_reread_triggered_on_disagreement():
    """Draft 'Lyon' is not in claim 'Paris is the capital.' -> re-read, replaced."""
    llm = _CountingLLM(["Lyon", _CLAIMS_JSON, "Paris"])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(), _v1_gated_cfg(ground_final_read=True), tr)
    assert tr.llm_calls == 3
    assert out["answer"] == "Paris"
    assert out["draft"] == "Paris"
    assert out["grounded_reread"] is True
    assert out["reread_trigger"] == "disagree"
    assert out["trace"][-1]["answer"] == "Lyon"


def test_no_reread_when_draft_agrees():
    """Draft 'Paris' is a substring of the claim text -> no re-read, 2 calls."""
    llm = _CountingLLM(["Paris", _CLAIMS_JSON])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(), _v1_gated_cfg(ground_final_read=True), tr)
    assert tr.llm_calls == 2
    assert out["answer"] == "Paris"
    assert out["grounded_reread"] is False
    assert out["reread_trigger"] is None
    assert out["reread_answer"] is None


def test_reread_returning_unknown_keeps_draft():
    """Re-read returns 'unknown' -> original draft stands, no further re-read."""
    llm = _CountingLLM(["Lyon", _CLAIMS_JSON, "unknown"])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(), _v1_gated_cfg(ground_final_read=True), tr)
    assert tr.llm_calls == 3
    assert out["answer"] == "Lyon"
    assert out["draft"] == "Lyon"
    assert out["grounded_reread"] is True
    assert out["reread_trigger"] == "disagree"
    assert out["reread_answer"] == "unknown"


def test_no_reread_when_flag_off():
    """Flag off: no re-read, no new record fields, v1 behavior exactly."""
    llm = _CountingLLM(["unknown", _CLAIMS_JSON])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(), _v1_gated_cfg(), tr)
    assert tr.llm_calls == 2
    assert out["answer"] == "unknown"
    assert "grounded_reread" not in out
    assert "reread_trigger" not in out
    assert "reread_answer" not in out




# ---------------------------------------------------------------------------
# Tune-hop2-sc-cap (step 5) — the max_hops cap binds (tasks.md A.1).
# Tests first: mocked LLM on the v1 gated base. The NLI always returns
# unresolved, so gaps always exist and the loop always wants another hop;
# the retriever always returns a novel passage, so targeted_retrieve
# always finds new evidence. The ONLY thing that can stop the loop is the
# cap (or the Fast Path, which cannot fire while gaps exist). A test that
# only reaches hop 0 (e.g. all claims supported -> Fast Path) would NOT
# prove the cap binds; both tests below must enter hop 1.
# ---------------------------------------------------------------------------

_NOVEL2 = [{"title": "Marseille", "sentences": ["Marseille is a city in France."], "text": "Marseille. Marseille is a city in France."}]


def _always_unresolved_nli():
    nli = MagicMock()
    nli.verify.return_value = {"status": "unresolved", "conflict": False, "sup": [], "con": []}
    return nli


def test_max_hops_1_never_reaches_hop_2():
    """max_hops=1: the run enters hop 1 and stops there (5 calls).

    Call order on the v1 gated base: hop 0 = 1 draft + 1 claims + 2
    sequential-SC samples (agreeing, stops at 2), then 1 direct-EIG probe
    finds Lyon; hop 1 = 1 draft (incremental claims reuse, no extraction
    call). The hop-2 draft + extraction calls must not happen: 5 calls
    total proves it, and the counting mock would raise StopIteration on
    a 6th call. The retriever's probe list has exactly 2 entries, so a
    runaway loop would also fail loudly on the exhausted side_effect.
    """
    llm = _CountingLLM(["Paris", _CLAIMS_JSON, "Paris", "Paris", "Paris"])
    retriever = MagicMock()
    retriever.search.side_effect = [list(_POOL), list(_NOVEL)]
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _always_unresolved_nli(),
                   _v1_gated_cfg(max_hops=1), tr)
    assert out["hops"] == 1
    assert len(out["trace"]) == 2
    assert tr.llm_calls == 5
    assert llm.n_calls == 5


def test_max_hops_2_control_reaches_hop_2():
    """Control: the SAME mocks with max_hops=2 reach hop 2 (6 calls).

    If the cap test above passed because the mocks never wanted a second
    hop (e.g. the loop stopped early for another reason), this control
    would also stop at hop 1 — it does not. The extra call is exactly
    the hop-2 draft; hop-2 extraction is still skipped (incremental
    claims reuse, draft unchanged).
    """
    llm = _CountingLLM(["Paris", _CLAIMS_JSON, "Paris", "Paris", "Paris", "Paris"])
    retriever = MagicMock()
    retriever.search.side_effect = [list(_POOL), list(_NOVEL), list(_NOVEL2)]
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _always_unresolved_nli(),
                   _v1_gated_cfg(max_hops=2), tr)
    assert out["hops"] == 2
    assert len(out["trace"]) == 3
    assert tr.llm_calls == 6
    assert llm.n_calls == 6


def test_build_graph_preserves_claim_source():
    """Step 2: claim "source" survives build_graph into the trace graph JSON.

    Without this threading, the --claims analyzer's source measures read 0
    on every file (the graph boundary dropped the field), and the D.1 gate's
    <=10% answer-bearing-question-sourced check would pass vacuously.
    """
    claims = [
        {"text": "Thon Maker is a basketball player.", "answer_bearing": True, "depends_on": [], "source": "draft"},
        {"text": "Thon Marial Maker was born in South Sudan.", "answer_bearing": False, "depends_on": [], "source": "question"},
        {"text": "A claim with no source field.", "answer_bearing": False, "depends_on": []},
    ]
    g = build_graph(claims, [], None, 0.8, {"erag": {}, "nli": {}}, set())
    assert [c["source"] for c in g.to_json()] == ["draft", "question", "draft"]


# ---------------------------------------------------------------------------
# Step 6 (tune-memory-effectiveness, A.1): row carries the memory
# measurement fields. B.1 adds them to run_erag's output dict; these
# mocked tests prove the fields match what memory actually returned.
# Without them, the --position analyzer's store-size measures would read
# the E5 gap again (used-belief texts unrecoverable from stored rows).
# ---------------------------------------------------------------------------

def _obs_mem_run(memory):
    """Observational-mode run with a mocked memory object (or None)."""
    item = {
        "_id": "test_mem_1",
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
    return run_erag(item, retriever, llm, nli, cfg, Tracker(), memory)


def test_run_erag_row_carries_mem_fields():
    """Step 6 A.1: the row's mem fields match the mocked memory.

    The mock memory holds 2 items and its read returns 1 passage; the
    row must report store size 2 (post-row; the mock's write is a no-op,
    so nothing is added) and exactly the returned passage's text.
    """
    memory = MagicMock()
    memory.items = [{"text": "belief one"}, {"text": "belief two"}]
    memory.read.return_value = ([{"text": "stored belief one"}], [])
    out = _obs_mem_run(memory)
    assert out["mem_store_size"] == 2
    assert out["mem_texts"] == ["stored belief one"]
    assert out["mem_used"] == 1


def test_run_erag_row_mem_fields_off():
    """Step 6 A.1: with memory=None the fields are 0 / []."""
    out = _obs_mem_run(None)
    assert out["mem_store_size"] == 0
    assert out["mem_texts"] == []
    assert out["mem_used"] == 0


# ---------------------------------------------------------------------------
# Learned continuation policy (step 7, B.1) — wiring the policy into run_erag
#
# Tests first: src/epistemic/continuation_policy.py does not exist yet, so
# the module-level tests fail on import and the run_erag tests fail on the
# missing policy_decision / policy_p fields until the wiring lands.
# The P values below were computed from the retrained artifact (tau=0.05)
# by independent pure arithmetic before these tests were written:
#   fast-path supported row -> P = 0.7571 (STOP)
#   gaps-unresolved draft "Paris" -> P = 0.6291 (STOP despite gaps)
#   draft "unknown", recall 0.0 -> P = 0.0201 (CONTINUE)
#   no_conf supported row -> P = 0.6893 (STOP)
# ---------------------------------------------------------------------------


def _policy_cfg(**erag_overrides):
    """_v1_gated_cfg plus the retrained policy artifact."""
    return _v1_gated_cfg(continuation_policy=str(_POLICY_ARTIFACT), **erag_overrides)


def test_policy_loads_real_artifact():
    """The retrained artifact loads with the expected format."""
    from src.epistemic.continuation_policy import load_policy

    art = load_policy(str(_POLICY_ARTIFACT))
    assert art["model"] == "logistic_regression"
    assert art["features"] == [
        "c0",
        "fast_path",
        "n_supported",
        "n_unresolved",
        "n_contradicted",
        "n_conflict",
        "ab_supported",
        "ab_contradicted",
        "mean_claim_conf",
        "hop0_recall",
        "type_comparison",
        "draft_unknown",
    ]
    assert art["tau"] == pytest.approx(0.05)
    assert len(art["coefficients"]) == 12
    assert len(art["scaler_mean"]) == 12
    assert len(art["scaler_scale"]) == 12


def test_policy_probability_matches_independent_arithmetic():
    """policy_probability reproduces the artifact's formula, computed
    independently from the raw JSON (no shared code)."""
    from src.epistemic.continuation_policy import load_policy, policy_probability

    art = load_policy(str(_POLICY_ARTIFACT))
    raw = json.loads(_POLICY_ARTIFACT.read_text())
    feats = {
        "c0": 0.97905,
        "fast_path": 1,
        "n_supported": 1,
        "n_unresolved": 0,
        "n_contradicted": 0,
        "n_conflict": 0,
        "ab_supported": 1,
        "ab_contradicted": 0,
        "mean_claim_conf": 0.97905,
        "hop0_recall": 1.0,
        "type_comparison": 0,
        "draft_unknown": 0,
    }
    z = raw["intercept"] + sum(
        c * (feats[name] - m) / s
        for c, name, m, s in zip(
            raw["coefficients"], raw["features"], raw["scaler_mean"], raw["scaler_scale"]
        )
    )
    expected = 1.0 / (1.0 + math.exp(-z))
    assert policy_probability(art, feats) == pytest.approx(expected, abs=1e-12)
    assert policy_probability(art, feats) == pytest.approx(0.7571, abs=0.002)


def test_policy_load_missing_file_raises():
    """A missing artifact file raises loudly, never falls back to static."""
    from src.epistemic.continuation_policy import load_policy

    with pytest.raises(FileNotFoundError):
        load_policy("/nonexistent/continuation_policy_dev.json")


def test_policy_load_malformed_artifact_raises(tmp_path):
    """Bad JSON, wrong model, and length mismatches all raise ValueError."""
    from src.epistemic.continuation_policy import load_policy

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not json")
    with pytest.raises(ValueError):
        load_policy(str(bad_json))

    wrong_model = tmp_path / "wrong.json"
    wrong_model.write_text(json.dumps({"model": "decision_tree", "features": ["c0"]}))
    with pytest.raises(ValueError):
        load_policy(str(wrong_model))

    mismatch = tmp_path / "mismatch.json"
    mismatch.write_text(
        json.dumps(
            {
                "model": "logistic_regression",
                "features": ["c0", "fast_path"],
                "coefficients": [0.1],
                "intercept": 0.0,
                "scaler_mean": [0.0, 0.0],
                "scaler_scale": [1.0, 1.0],
                "tau": 0.05,
            }
        )
    )
    with pytest.raises(ValueError):
        load_policy(str(mismatch))

    # Right lengths, wrong feature list (one renamed): the coefficients
    # are positional, so this must fail loudly rather than score on a
    # wrong subset. (Parent-added hardening, 2026-11-09.)
    from src.epistemic.continuation_policy import MODEL_FEATURES

    renamed = tmp_path / "renamed.json"
    wrong_features = list(MODEL_FEATURES)
    wrong_features[-1] = "sc_skipped"
    renamed.write_text(
        json.dumps(
            {
                "model": "logistic_regression",
                "features": wrong_features,
                "coefficients": [0.0] * 12,
                "intercept": 0.0,
                "scaler_mean": [0.0] * 12,
                "scaler_scale": [1.0] * 12,
                "tau": 0.05,
            }
        )
    )
    with pytest.raises(ValueError):
        load_policy(str(renamed))


def test_policy_features_agree_with_training_set():
    """PROOF of live/stored feature agreement (step 7 B.1): the live
    hop0_features function, fed each stored dev row's hop-0 state
    (c0, c0_source, sc_skipped_fast_path, trace[0] graph/pool/answer,
    manifest supporting_facts, row type), reproduces every feature in
    data/continuation_training_dev.jsonl row-for-row to 1e-9.

    draft_unknown uses the HOP-0 draft (trace[0]['answer']), not the
    row's final draft field — the retrain's correction.
    """
    from src.epistemic.continuation_policy import FEATURES, hop0_features

    dev_rows = {}
    for line in _DEV_THETA_A.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            dev_rows[row["id"]] = row  # dedupe by id, keep last row
    manifest = {}
    for line in _DEV_MANIFEST.read_text().splitlines():
        if line.strip():
            item = json.loads(line)
            manifest[item["_id"]] = item
    train = {}
    for line in _TRAINING_FILE.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            train[row["id"]] = row
    assert len(dev_rows) == 100
    assert len(train) == 100
    for qid, row in dev_rows.items():
        t = train[qid]
        feats = hop0_features(
            c0=row["c0"],
            c0_source=row["c0_source"],
            sc_skipped=row.get("sc_skipped_fast_path", False),
            graph_claims=row["trace"][0]["graph"],
            pool_titles=row["trace"][0]["pool"],
            supporting_facts=manifest[qid].get("supporting_facts"),
            question_type=row.get("type"),
            hop0_draft=row["trace"][0]["answer"],
        )
        for k in FEATURES:
            assert feats[k] == pytest.approx(t[k], abs=1e-9), f"{qid} {k}"


def test_policy_stop_fast_path_row():
    """Policy STOP on a would-be fast-path row: ends at hop 0, 2 calls,
    no retrieval beyond the initial one."""
    llm = _CountingLLM(["Paris", _CLAIMS_JSON])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(), _policy_cfg(), tr)
    assert out["hops"] == 0
    assert tr.llm_calls == 2
    assert out["policy_decision"] == "stop"
    assert out["policy_p"] == pytest.approx(0.7571, abs=0.002)
    assert retriever.search.call_count == 1


def test_policy_stop_despite_gaps():
    """Policy STOP binds even when gaps exist (the static system would
    continue): ends at hop 0, no EIG probe search."""
    llm = _CountingLLM(["Paris", _CLAIMS_JSON, "Paris", "Paris"])
    retriever = MagicMock()
    retriever.search.side_effect = [list(_POOL), list(_NOVEL)]
    tr = Tracker()
    out = run_erag(
        _item(), retriever, llm, _unresolved_then_supported_nli(), _policy_cfg(), tr
    )
    assert out["hops"] == 0
    assert tr.llm_calls == 4  # draft + claims + 2 SC samples; no hop-1 draft
    assert out["policy_decision"] == "stop"
    assert out["policy_p"] == pytest.approx(0.6291, abs=0.002)
    assert retriever.search.call_count == 1  # no EIG probe


def test_policy_continue_unknown_draft():
    """Policy CONTINUE on a draft-'unknown' row with recall 0: enters
    hop 1, retrieves, and answers from the hop-1 evidence."""
    item = _item()
    item["supporting_facts"] = [["Lyon", 0]]  # hop-0 recall 0.0
    llm = _CountingLLM(
        ["unknown", _CLAIMS_JSON, "unknown", "unknown", "Paris", _CLAIMS_JSON]
    )
    retriever = MagicMock()
    retriever.search.side_effect = [list(_POOL), list(_NOVEL)]
    tr = Tracker()
    out = run_erag(
        item, retriever, llm, _unresolved_then_supported_nli(), _policy_cfg(), tr
    )
    assert out["hops"] == 1
    assert tr.llm_calls == 6  # hop 0: draft + claims + 2 SC; hop 1: draft + claims
    assert out["policy_decision"] == "continue"
    assert out["policy_p"] == pytest.approx(0.0201, abs=0.002)
    assert out["answer"] == "Paris"
    assert retriever.search.call_count == 2  # initial + EIG probe


def test_policy_continue_fast_path_row_uses_weakest_claim(tmp_path):
    """Policy CONTINUE on a would-be fast-path row (no gaps): the
    retrieval target is the weakest claim, mirroring the static
    min_eff < theta_fast fallback. Uses a synthetic always-CONTINUE
    artifact (intercept -10) so the decision does not depend on the
    fitted coefficients."""
    art_path = tmp_path / "policy.json"
    art_path.write_text(
        json.dumps(
            {
                "model": "logistic_regression",
                "features": [
                    "c0",
                    "fast_path",
                    "n_supported",
                    "n_unresolved",
                    "n_contradicted",
                    "n_conflict",
                    "ab_supported",
                    "ab_contradicted",
                    "mean_claim_conf",
                    "hop0_recall",
                    "type_comparison",
                    "draft_unknown",
                ],
                "coefficients": [0.0] * 12,
                "intercept": -10.0,
                "scaler_mean": [0.0] * 12,
                "scaler_scale": [1.0] * 12,
                "tau": 0.05,
            }
        )
    )
    llm = _CountingLLM(["Paris", _CLAIMS_JSON, "Paris"])
    retriever = MagicMock()
    retriever.search.side_effect = [list(_POOL), list(_NOVEL)]
    tr = Tracker()
    out = run_erag(
        _item(),
        retriever,
        llm,
        _supported_nli(),
        _v1_gated_cfg(continuation_policy=str(art_path)),
        tr,
    )
    assert out["hops"] == 1
    assert out["policy_decision"] == "continue"
    assert retriever.search.call_count == 2
    assert retriever.search.call_args_list[1].args[0] == "Paris is the capital."


def test_policy_governs_under_no_conf_ablation():
    """Under no_conf the static code always continues; with the policy
    flag present the policy decision still governs at hop 0 (STOP here)."""
    llm = _CountingLLM(["Paris", _CLAIMS_JSON])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(
        _item(),
        retriever,
        llm,
        _supported_nli(),
        _policy_cfg(ablate=["no_conf"]),
        tr,
    )
    assert out["hops"] == 0
    assert tr.llm_calls == 2
    assert out["policy_decision"] == "stop"
    assert out["policy_p"] == pytest.approx(0.6893, abs=0.002)
    assert retriever.search.call_count == 1


def test_policy_flag_absent_fast_path_row_unchanged():
    """Control: flag absent, fast-path row behaves exactly as before
    (2 calls, hop 0) and carries no policy fields."""
    llm = _CountingLLM(["Paris", _CLAIMS_JSON])
    retriever = MagicMock()
    retriever.search.return_value = list(_POOL)
    tr = Tracker()
    out = run_erag(_item(), retriever, llm, _supported_nli(), _v1_gated_cfg(), tr)
    assert out["hops"] == 0
    assert tr.llm_calls == 2
    assert "policy_decision" not in out
    assert "policy_p" not in out


def test_policy_absent_control_continues_on_gaps():
    """Control: flag absent, gaps row behaves exactly as before
    (5 calls, hop 1) and carries no policy fields."""
    llm = _CountingLLM(["Paris", _CLAIMS_JSON, "Paris", "Paris", "Paris"])
    retriever = MagicMock()
    retriever.search.side_effect = [list(_POOL), list(_NOVEL)]
    tr = Tracker()
    out = run_erag(
        _item(), retriever, llm, _unresolved_then_supported_nli(), _v1_gated_cfg(), tr
    )
    assert out["hops"] == 1
    assert tr.llm_calls == 5
    assert "policy_decision" not in out
    assert "policy_p" not in out
