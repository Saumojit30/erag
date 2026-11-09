"""Tests for the --policy section (tuning step 7, tasks.md A.5).

The section (scripts/analyze_trueadaptive_test400.py, section 15)
reports the learned-continuation-policy run file: N (deduped, keep last
row per id), failed count, EM, F1, mean llm_calls/cache_hits/live calls
per question, the hops distribution (n, mean calls, EM per hops value),
policy decision counts (STOP vs CONTINUE from a per-row
`policy_decision` field; rows without the field are reported as
unknown, never assumed), STOP-rows' EM vs CONTINUE-rows' EM, and — with
a simulation JSON — the agreement check vs the Phase A simulation
(Delta EM, Delta calls/Q; the Gate B +/-0.02 / +/-0.2 check).

No LLM is called here and no Test-400 file is opened anywhere in this
file — the verification runs on the theta_a dev baseline only.
"""

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

_ANALYZER = REPO_ROOT / "scripts" / "analyze_trueadaptive_test400.py"
_spec = importlib.util.spec_from_file_location(
    "analyze_trueadaptive_test400", _ANALYZER
)
analyzer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(analyzer)

DEV_THETA_A = REPO_ROOT / "results/trueadaptive/erag_trueadaptive_bm25_dev_theta_a.jsonl"


def _row(id, hops, calls, em, f1=0.0, hits=0, failed=False,
         decision=None, gold="Paris"):
    r = {
        "id": id,
        "failed": failed,
        "em": em,
        "f1": f1,
        "llm_calls": calls,
        "cache_hits": hits,
        "hops": hops,
        "trace": [{"answer": "Paris"} for _ in range(hops + 1)],
        "gold": gold,
    }
    if decision is not None:
        r["policy_decision"] = decision
    return r


def test_policy_metrics_synthetic():
    rows = [
        _row("a", 0, 2, 1, f1=0.9, hits=0, decision="STOP"),
        _row("b", 0, 2, 0, f1=0.2, hits=2, decision="STOP"),
        _row("c", 1, 5, 1, f1=0.8, hits=1, decision="CONTINUE"),
        _row("d", 1, 4, 0, f1=0.0, hits=4, decision="CONTINUE"),
        _row("e", 1, 6, 1, f1=1.0, hits=0),  # no decision field -> unknown
    ]
    m = analyzer.policy_metrics(rows)
    assert m["n"] == 5
    assert m["failed"] == 0
    assert m["em"] == 3 / 5
    assert round(m["calls"], 2) == 3.80  # (2+2+5+4+6)/5
    assert round(m["live_calls"], 2) == round(12 / 5, 2)
    assert m["decisions"] == {"STOP": 2, "CONTINUE": 2, "unknown": 1}
    assert m["stop_em"] == 0.5  # rows a, b
    assert m["continue_em"] == 0.5  # rows c, d
    assert m["hops_dist"][0] == {"n": 2, "calls": 2.0, "em": 0.5}
    assert m["hops_dist"][1] == {"n": 3, "calls": 5.0, "em": 2 / 3}


def test_policy_rows_without_field_all_unknown():
    rows = [_row("a", 0, 2, 1), _row("b", 1, 5, 0)]
    m = analyzer.policy_metrics(rows)
    assert m["decisions"] == {"STOP": 0, "CONTINUE": 0, "unknown": 2}
    assert m["stop_em"] is None
    assert m["continue_em"] is None


def test_policy_failed_rows_excluded_but_counted():
    rows = [
        _row("a", 0, 2, 1, decision="STOP"),
        _row("b", 1, 5, 0, failed=True, decision="CONTINUE"),
    ]
    m = analyzer.policy_metrics(rows)
    assert m["n"] == 1
    assert m["failed"] == 1
    assert m["decisions"] == {"STOP": 1, "CONTINUE": 0, "unknown": 0}


def test_stored_theta_a_baseline_reproduces():
    # Tasks.md A.5 verification: on the theta_a baseline file the section
    # reproduces EM 0.5100, 4.65 calls/Q — and every row is "unknown"
    # (no policy_decision field predates the policy).
    rows = analyzer.load(str(DEV_THETA_A))
    assert len(rows) == 100
    m = analyzer.policy_metrics(rows)
    assert m["failed"] == 0
    assert round(m["em"], 4) == 0.5100
    assert round(m["calls"], 2) == 4.65
    assert m["decisions"] == {"STOP": 0, "CONTINUE": 0, "unknown": 100}
    assert m["stop_em"] is None
    assert m["continue_em"] is None


def test_policy_section_prints(capsys):
    rows = [
        _row("a", 0, 2, 1, f1=0.9, hits=0, decision="STOP"),
        _row("b", 1, 5, 0, f1=0.1, hits=2, decision="CONTINUE"),
    ]
    analyzer.policy_section("synthetic", rows)
    out = capsys.readouterr().out
    assert "15. Learned continuation policy (synthetic)" in out
    assert "EM=0.5000" in out
    assert "STOP: 1" in out
    assert "CONTINUE: 1" in out
    assert "STOP-rows EM" in out
    assert "CONTINUE-rows EM" in out


def test_policy_section_agreement_check(capsys):
    rows = [
        _row("a", 0, 2, 1, f1=0.9, hits=0, decision="STOP"),
        _row("b", 1, 5, 0, f1=0.1, hits=2, decision="CONTINUE"),
    ]
    sim = {"em": 0.5000, "calls": 3.98}
    analyzer.policy_section("synthetic", rows, simulation=sim)
    out = capsys.readouterr().out
    # Live EM 0.5000 vs sim 0.5000 -> dEM +0.0000; live calls 3.50 vs
    # sim 3.98 -> dCalls -0.48.
    assert "agreement vs simulation" in out
    assert "dEM: +0.0000" in out
    assert "dCalls/Q: -0.48" in out


def test_policy_section_baseline_deltas(capsys):
    rows = [_row("a", 0, 2, 1, decision="STOP")]
    base = [_row("a", 0, 2, 1), _row("b", 1, 5, 0)]
    analyzer.policy_section("synthetic", rows, baseline_rows=base)
    out = capsys.readouterr().out
    assert "baseline:" in out
    assert "delta calls/Q:" in out
    assert "delta EM:" in out
