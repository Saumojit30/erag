"""Tests for the --hopcap section (tuning step 5, tasks.md A.2).

The section (scripts/analyze_trueadaptive_test400.py, section 14) reports
the hop-2 call-tail measures for the --ta-dev file: N (deduped, keep last
row per id), failed count, EM, F1, mean llm_calls/cache_hits/live calls
per question, the hops distribution (n, mean calls, EM per hops value),
the hop-2 row count and hop-2 calls, the tail rows (>=7 calls) with their
call share, and — on hop-2 rows — the draft EM progression hop 0 -> hop 1
-> hop 2 (repo exact_match on trace[i].answer) against final EM, which is
the design's draft-level diagnostic for what hop 2 adds. With
--hopcap-baseline <file> it prints the same measures for the baseline
file and the deltas (calls/Q, live calls/Q, EM).

Section number note: tasks.md A.2 originally said "section 13" — stale,
step 4's --theta section already took 13. This section is 14 (corrected
in tasks.md with the parent task's amendment).

No LLM is called here — the tests check the computation on synthetic rows
and on the stored dev/test files.
"""

import importlib.util
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

DEV_CLAIMS = REPO_ROOT / "results/trueadaptive/erag_trueadaptive_bm25_dev_claims.jsonl"
TEST = REPO_ROOT / "results/trueadaptive/erag_trueadaptive_test_bm25.jsonl"
DEV_THETA_A = REPO_ROOT / "results/trueadaptive/erag_trueadaptive_bm25_dev_theta_a.jsonl"


def _row(id, hops, calls, em, f1=0.0, hits=0, failed=False, draft_answers=None, gold="Paris"):
    trace = [{"answer": a} for a in (draft_answers if draft_answers is not None else ["Paris"] * (hops + 1))]
    return {
        "id": id,
        "failed": failed,
        "em": em,
        "f1": f1,
        "llm_calls": calls,
        "cache_hits": hits,
        "hops": hops,
        "trace": trace,
        "gold": gold,
    }


def test_hops_distribution_and_hop2_counts():
    rows = [
        _row("a", 0, 2, 1, f1=0.9, hits=0),   # hop 0, correct
        _row("b", 0, 2, 0, f1=0.2, hits=2),   # hop 0, wrong
        _row("c", 1, 5, 1, f1=0.8, hits=1),   # hop 1, correct
        _row("d", 1, 4, 0, f1=0.0, hits=4),   # hop 1, wrong
        _row("e", 2, 8, 1, f1=1.0, hits=0),   # hop 2, correct
        _row("f", 2, 9, 0, f1=0.1, hits=3),   # hop 2, wrong
    ]
    m = analyzer.hopcap_metrics(rows)
    assert m["n"] == 6
    assert m["failed"] == 0
    assert m["em"] == 3 / 6
    assert round(m["calls"], 2) == 5.00  # (2+2+5+4+8+9)/6
    assert round(m["cache_hits"], 2) == round(10 / 6, 2)
    assert round(m["live_calls"], 2) == round(20 / 6, 2)
    assert m["hops_dist"][0] == {"n": 2, "calls": 2.0, "em": 0.5}
    assert m["hops_dist"][1] == {"n": 2, "calls": 4.5, "em": 0.5}
    assert m["hops_dist"][2] == {"n": 2, "calls": 8.5, "em": 0.5}
    assert m["hop2_rows"] == 2
    assert m["hop2_calls"] == 17
    assert m["tail_rows"] == 2
    assert m["tail_calls"] == 17
    assert round(m["tail_share"], 4) == round(17 / 30, 4)


def test_failed_rows_excluded_from_measures_but_counted():
    rows = [
        _row("a", 0, 2, 1, hits=0),
        _row("b", 2, 8, 0, hits=0),
        _row("c", 1, 5, 1, failed=True),  # failed: excluded from N/means
    ]
    m = analyzer.hopcap_metrics(rows)
    assert m["n"] == 2
    assert m["failed"] == 1
    assert m["em"] == 0.5
    assert m["hop2_rows"] == 1
    assert m["hop2_calls"] == 8
    assert m["tail_rows"] == 1


def test_dedupe_keeps_last_row(tmp_path):
    # Two rows with the same id: load() keeps the last (the resume-retried
    # stale row is the first). The hopcap measures must see only the last.
    p = tmp_path / "dup.jsonl"
    import json
    with open(p, "w") as f:
        f.write(json.dumps(_row("a", 2, 9, 0, hits=0)) + "\n")
        f.write(json.dumps(_row("a", 0, 2, 1, hits=2)) + "\n")
        f.write(json.dumps(_row("b", 1, 5, 1, hits=1)) + "\n")
    rows = analyzer.load(str(p))
    assert len(rows) == 2
    m = analyzer.hopcap_metrics(rows)
    assert m["n"] == 2
    assert m["hop2_rows"] == 0
    assert m["em"] == 1.0
    assert round(m["calls"], 2) == 3.50


def test_hop2_draft_progression():
    # Hop-2 rows: hop-0 draft wrong, hop-1 draft right on one row, hop-2
    # draft right on both. Final EM is the stored em, not the draft EM.
    rows = [
        _row("a", 2, 8, 1, draft_answers=["London", "Paris", "Paris"]),
        _row("b", 2, 9, 0, draft_answers=["London", "London", "Paris"]),
    ]
    m = analyzer.hopcap_metrics(rows)
    assert m["hop2_rows"] == 2
    assert m["hop2_draft_em"] == (0.0, 0.5, 1.0)  # hop-0, hop-1, hop-2 drafts
    assert m["hop2_final_em"] == 0.5


def test_baseline_deltas():
    cur = analyzer.hopcap_metrics([
        _row("a", 0, 2, 1, hits=0),
        _row("b", 2, 8, 0, hits=2),
    ])
    base = analyzer.hopcap_metrics([
        _row("a", 0, 2, 1, hits=0),
        _row("b", 2, 9, 0, hits=0),
    ])
    d = analyzer.hopcap_deltas(cur, base)
    assert round(d["calls"], 2) == -0.50   # (2+8)/2 - (2+9)/2
    assert round(d["live_calls"], 2) == -1.50  # (5-1) - (5.5-0)
    assert d["em"] == 0.0
    assert d["hop2_rows"] == 0


def test_stored_dev_file_reproduces_verification_numbers():
    # Tasks.md A.2 verification numbers on the step-2 tuned dev file
    # (N=100 deduped, 0 failed) and the Test-400 v1 file (N=400).
    rows = analyzer.load(str(DEV_CLAIMS))
    assert len(rows) == 100
    m = analyzer.hopcap_metrics(rows)
    assert m["failed"] == 0
    assert round(m["em"], 4) == 0.5400
    assert round(m["calls"], 2) == 4.65
    assert m["hop2_rows"] == 10
    assert m["hop2_calls"] == 78
    assert m["hops_dist"][2] == {"n": 10, "calls": 7.80, "em": 0.4}

    test_rows = analyzer.load(str(TEST))
    assert len(test_rows) == 400
    tm = analyzer.hopcap_metrics(test_rows)
    assert tm["failed"] == 0
    assert tm["hop2_rows"] == 42
    assert tm["hop2_calls"] == 334
    assert tm["tail_rows"] == 54
    assert tm["tail_calls"] == 422
    assert tm["hop2_draft_em"] == (0.1429, 0.4762, 0.5238)
    assert round(tm["hop2_final_em"], 4) == 0.4048


def test_post_step4_baseline_file():
    # The step-5 A/B baseline is the post-step-4 tuned dev file (theta_a),
    # NOT the step-2 file: EM 0.5100, 4.65 calls/Q, same hop-2 shape.
    rows = analyzer.load(str(DEV_THETA_A))
    assert len(rows) == 100
    m = analyzer.hopcap_metrics(rows)
    assert m["failed"] == 0
    assert round(m["em"], 4) == 0.5100
    assert round(m["calls"], 2) == 4.65
    assert m["hop2_rows"] == 10
    assert m["hop2_calls"] == 78


def test_hopcap_section_prints(capsys):
    rows = [
        _row("a", 0, 2, 1, f1=0.9, hits=0),
        _row("b", 2, 8, 0, f1=0.1, hits=2),
    ]
    analyzer.hopcap_section("synthetic", rows)
    out = capsys.readouterr().out
    assert "14. Hop-2 call cap (synthetic)" in out
    assert "EM=0.5000" in out
    assert "hop-2 rows: 1" in out
    assert "hop-2 calls: 8" in out
    assert "tail rows (>=7 calls): 1" in out


def test_hopcap_section_prints_baseline_deltas(capsys):
    rows = [
        _row("a", 0, 2, 1, hits=0),
        _row("b", 2, 8, 0, hits=2),
    ]
    base = [
        _row("a", 0, 2, 1, hits=0),
        _row("b", 2, 9, 0, hits=0),
    ]
    analyzer.hopcap_section("synthetic", rows, base)
    out = capsys.readouterr().out
    assert "baseline:" in out
    assert "delta calls/Q:" in out
    assert "delta live calls/Q:" in out
    assert "delta EM:" in out
