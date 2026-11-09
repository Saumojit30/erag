"""Tests for Phase A of the learned continuation policy (tuning step 7).

Tests first: the extraction (A.1), the call-accounting invariant (A.2),
and the counterfactual simulation (A.3) are specified here against
hand-built mocked traces before the implementation exists.

Rules these tests enforce (from design.md / tasks.md):
- Training source is ONLY the post-step-4 tuned dev file + dev.jsonl.
  The extractor MUST refuse any input path that is not a dev file.
- Row keys are used exactly as stored: the row's `draft` field is the
  canonical draft (trace[0]['answer'] is the hop-0 draft); the row's
  `recall` is FINAL recall and must NOT be used as a hop-0 feature —
  hop-0 recall is recomputed from the manifest supporting_facts vs
  trace[0]['pool'] titles (the H6 method).
- Hop-0 calls = 1 draft + 1 extraction + SC samples (0 when SC was
  skipped on the Fast Path, 2 when c0 == 1.0, else 3 — sequential SC
  stops at 2 only on two agreeing samples, so c0 == 1.0 implies 2
  samples and c0 in {1/3, 2/3} implies 3). Later hops: 1 draft +
  1 extraction iff the draft changed vs the hop-0 draft (incremental
  claim reuse); +1 for a grounded re-read when triggered. EIG probes
  cost 0 (eig_strategy direct) and post-hop resample costs 0
  (post_hop_resample never). The invariant hop0 + later == llm_calls
  must hold for EVERY row.
- Simulation (pre-registered rule): STOP -> hop-0 draft + hop-0 calls;
  CONTINUE -> stored final answer + stored total calls. Rows where the
  policy says CONTINUE but the stored trace stopped at hop 0 have no
  simulable outcome: EXCLUDED from the simulated numbers, counted and
  reported.

No LLM is called here and no Test-400 file is opened anywhere in this
file — training on test would contaminate the Phase 2 verdict.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

_EXTRACT = REPO_ROOT / "scripts" / "extract_continuation_training.py"
_spec = importlib.util.spec_from_file_location(
    "extract_continuation_training", _EXTRACT
)
extract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extract)

_TRAIN = REPO_ROOT / "scripts" / "train_continuation_policy.py"
_spec_t = importlib.util.spec_from_file_location(
    "train_continuation_policy", _TRAIN
)
train = importlib.util.module_from_spec(_spec_t)
_spec_t.loader.exec_module(train)

DEV_THETA_A = (
    REPO_ROOT / "results/trueadaptive/erag_trueadaptive_bm25_dev_theta_a.jsonl"
)
DEV_MANIFEST = REPO_ROOT / "data/manifests/dev.jsonl"
TEST_FILE = REPO_ROOT / "results/trueadaptive/erag_trueadaptive_test_bm25.jsonl"


def _claim(text, status, answer_bearing=False, conf=0.9):
    return {
        "text": text,
        "answer_bearing": answer_bearing,
        "depends_on": [],
        "c0": 1.0,
        "status": status,
        "sup": [],
        "con": [],
        "conflict": False,
        "conf": conf,
        "eff": 0.9,
        "source": "draft",
    }


def _row(
    id,
    gold="Paris",
    draft="Paris",
    hop0_answer="Paris",
    c0=1.0,
    c0_source="fast_path_min_eff",
    sc_skipped=True,
    hops=0,
    calls=2,
    hits=2,
    type_="bridge",
    answers=None,
    graph=None,
    pool=None,
    grounded_reread=False,
    em=1,
    f1=1.0,
):
    trace = []
    for h, a in enumerate(answers if answers is not None else [hop0_answer]):
        trace.append({
            "hop": h,
            "answer": a,
            "pool": pool if pool is not None else ["Paris", "Lyon"],
            "graph": graph if (h == 0 and graph is not None) else [],
        })
    return {
        "id": id,
        "gold": gold,
        "draft": draft,
        "answer": draft,
        "c0": c0,
        "c0_source": c0_source,
        "sc_skipped_fast_path": sc_skipped,
        "hops": hops,
        "llm_calls": calls,
        "cache_hits": hits,
        "type": type_,
        "trace": trace,
        "grounded_reread": grounded_reread,
        "em": em,
        "f1": f1,
        "failed": False,
        "abstained": False,
    }


def _manifest_item(id, titles=("Paris", "Lyon")):
    return {"_id": id, "supporting_facts": [[t, 0] for t in titles]}


# ------------------------------------------------------------------ A.1
def test_extract_features_handbuilt_row():
    graph = [
        _claim("Paris is the capital.", "supported", answer_bearing=True, conf=0.95),
        _claim("Lyon is a city.", "unresolved", conf=0.6),
    ]
    row = _row("q1", graph=graph, pool=["Paris", "Lyon"])
    feats = extract.extract_features(row, _manifest_item("q1"))
    assert feats["c0"] == 1.0
    assert feats["fast_path"] == 1
    assert feats["sc_skipped"] == 1
    assert feats["n_supported"] == 1
    assert feats["n_unresolved"] == 1
    assert feats["n_contradicted"] == 0
    assert feats["n_conflict"] == 0
    assert feats["ab_supported"] == 1
    assert feats["ab_contradicted"] == 0
    assert feats["mean_claim_conf"] == pytest.approx(0.775)
    assert feats["hop0_recall"] == 1.0
    assert feats["type_comparison"] == 0
    assert feats["draft_unknown"] == 0
    assert feats["label"] == 1  # hop-0 draft "Paris" == gold
    assert feats["hop0_calls"] == 2  # draft + extraction, SC skipped
    assert feats["total_calls"] == 2


def test_extract_features_wrong_draft_and_unknown_flag():
    graph = [
        _claim("London is the capital.", "contradicted", answer_bearing=True, conf=0.8),
        _claim("Something else.", "unresolved", conf=0.5),
    ]
    row = _row(
        "q2", gold="Paris", draft="unknown", hop0_answer="London",
        c0=2 / 3, c0_source="sc", sc_skipped=False,
        answers=["London"], graph=graph, pool=["London"],
    )
    feats = extract.extract_features(row, _manifest_item("q2", titles=("Paris",)))
    assert feats["label"] == 0  # hop-0 draft "London" != gold "Paris"
    assert feats["draft_unknown"] == 1  # row draft field is literally 'unknown'
    assert feats["fast_path"] == 0
    assert feats["n_contradicted"] == 1
    assert feats["ab_contradicted"] == 1
    assert feats["ab_supported"] == 0
    assert feats["hop0_recall"] == 0.0  # pool ["London"] misses gold title
    assert feats["hop0_calls"] == 5  # draft + extraction + 3 SC samples


def test_extract_refuses_test_file_path():
    with pytest.raises(ValueError):
        extract.assert_dev_input(str(TEST_FILE))
    with pytest.raises(ValueError):
        extract.assert_dev_input("/tmp/some_test_file.jsonl")
    with pytest.raises(ValueError):
        extract.assert_dev_input("/tmp/random_file.jsonl")
    # The real dev file passes.
    extract.assert_dev_input(str(DEV_THETA_A))


# ------------------------------------------------------------------ A.2
def test_accounting_invariant_handbuilt_rows():
    # Fast-path row: hop 0 only, SC skipped -> 2 calls.
    a = _row("a", hops=0, calls=2, hits=2)
    assert extract.hop0_calls(a) == 2
    assert extract.later_calls(a) == 0
    assert extract.verify_accounting(a) is True
    # SC row, c0 == 1.0 -> 2 samples; hop 1 draft changed -> extraction.
    # hop0 = 1 + 1 + 2 = 4; later = 1 draft + 1 extraction = 2; total 6.
    b = _row(
        "b", c0=1.0, c0_source="sc", sc_skipped=False, hops=1, calls=6,
        answers=["London", "Paris"],
    )
    assert extract.hop0_calls(b) == 4
    assert extract.later_calls(b) == 2
    assert extract.verify_accounting(b) is True
    # SC row, c0 == 2/3 -> 3 samples; hop 1 draft unchanged (no extraction),
    # hop 2 draft changed (extraction); re-read triggered (+1, counted in
    # later_calls — everything after hop 0).
    # hop0 = 1 + 1 + 3 = 5; later = (1 + 0) + (1 + 1) + 1 re-read = 4; total 9.
    c = _row(
        "c", c0=2 / 3, c0_source="sc", sc_skipped=False, hops=2, calls=9,
        answers=["London", "London", "Paris"], grounded_reread=True,
    )
    assert extract.hop0_calls(c) == 5
    assert extract.later_calls(c) == 4
    assert extract.verify_accounting(c) is True
    # Tampered total breaks the invariant.
    d = _row(
        "b", c0=1.0, c0_source="sc", sc_skipped=False, hops=1, calls=7,
        answers=["London", "Paris"],
    )
    assert extract.verify_accounting(d) is False


def test_stored_dev_file_reproduces_verification_numbers():
    # Tasks.md A.1 verification numbers on the post-step-4 tuned dev file.
    out = extract.extract_all(str(DEV_THETA_A), str(DEV_MANIFEST))
    assert out["n"] == 100
    assert out["failed"] == 0
    assert out["hop0_em"] == pytest.approx(0.4800)
    assert out["final_em"] == pytest.approx(0.5100)
    assert out["fixed"] == 6
    assert out["broke"] == 3
    assert out["hops"] == {0: 45, 1: 45, 2: 10}
    assert out["abstained"] == 15
    assert out["draft_unknown"] == 6
    assert out["calls_per_q"] == pytest.approx(4.65)
    assert out["accounting_violations"] == 0  # invariant holds for every row
    # Oracle ceiling is recorded (perfect draft-correctness model).
    assert "oracle" in out
    assert out["oracle"]["excluded"] == 17  # wrong drafts on stopped rows
    assert out["oracle"]["included"] == 83
    assert out["oracle"]["em"] == pytest.approx(0.6506, abs=1e-4)
    assert out["oracle"]["calls"] == pytest.approx(4.61, abs=0.01)


# ------------------------------------------------------------------ A.3
def _train_row(id, label, hops, hop0_calls, total_calls, hits,
               hop0_answer, final_answer, final_em, hop0_f1=0.0,
               final_f1=0.0, gold="Paris"):
    return {
        "id": id,
        "label": label,
        "hops": hops,
        "hop0_calls": hop0_calls,
        "total_calls": total_calls,
        "cache_hits": hits,
        "hop0_answer": hop0_answer,
        "final_answer": final_answer,
        "final_em": final_em,
        "final_f1": final_f1,
        "hop0_f1": hop0_f1,
        "gold": gold,
    }


def test_simulation_handbuilt_four_rows():
    # A: correct draft, stopped at hop 0, high P -> STOP, keeps hop-0 outcome.
    # B: wrong draft, went to hop 1, low P -> CONTINUE, keeps stored outcome.
    # C: wrong draft, stopped at hop 0, low P -> CONTINUE but no stored
    #    hop-1 outcome -> EXCLUDED.
    # D: correct draft, went to hop 1, high P -> STOP, saves the hop-1 calls.
    rows = [
        _train_row("a", 1, 0, 2, 2, 2, "Paris", "Paris", 1, 1.0, 1.0),
        _train_row("b", 0, 1, 4, 6, 6, "London", "Paris", 1, 0.0, 1.0),
        _train_row("c", 0, 0, 2, 2, 2, "London", "London", 0, 0.0, 0.0),
        _train_row("d", 1, 1, 4, 6, 6, "Paris", "Paris", 1, 1.0, 1.0),
    ]
    proba = [0.9, 0.2, 0.2, 0.9]  # P(draft correct); CONTINUE iff P < tau
    sim = train.simulate(rows, proba, tau=0.5)
    assert sim["n_excluded"] == 1  # row c only
    assert sim["n_included"] == 3
    assert sim["n_stop"] == 2
    assert sim["n_continue"] == 1  # among included rows
    assert sim["em"] == pytest.approx(1.0)  # a, b, d all correct
    assert sim["calls"] == pytest.approx(4.0)  # (2 + 6 + 4) / 3
    assert sim["coverage"] == pytest.approx(1.0)


def test_simulation_stop_on_unknown_draft_counts_unanswered():
    rows = [
        _train_row("a", 0, 0, 2, 2, 2, "unknown", "unknown", 0, 0.0, 0.0),
        _train_row("b", 1, 0, 2, 2, 2, "Paris", "Paris", 1, 1.0, 1.0),
    ]
    sim = train.simulate(rows, [0.9, 0.9], tau=0.5)  # both STOP
    assert sim["n_included"] == 2
    assert sim["em"] == pytest.approx(0.5)
    assert sim["coverage"] == pytest.approx(0.5)  # row a answered 'unknown'


def test_simulation_tau_moves_decisions():
    rows = [
        _train_row("a", 1, 1, 4, 6, 6, "Paris", "Paris", 1, 1.0, 1.0),
        _train_row("b", 0, 1, 4, 6, 6, "London", "Paris", 1, 0.0, 1.0),
    ]
    low = train.simulate(rows, [0.9, 0.2], tau=0.1)  # both STOP
    assert low["n_stop"] == 2
    assert low["em"] == pytest.approx(0.5)  # row b keeps wrong hop-0 draft
    assert low["calls"] == pytest.approx(4.0)
    high = train.simulate(rows, [0.9, 0.2], tau=0.95)  # both CONTINUE
    assert high["n_continue"] == 2
    assert high["em"] == pytest.approx(1.0)
    assert high["calls"] == pytest.approx(6.0)
