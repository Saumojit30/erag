"""Tests for the --adaptive-rag section (change adaptive-rag-baseline, C.2).

The section (scripts/analyze_trueadaptive_test400.py, section 16)
reports the Adaptive-RAG run file: N (deduped, keep last row per id),
failed count, EM, F1, mean llm_calls/Q, route distribution (counts +
EM + calls/Q per route, from the per-row `route` field the router
writes; rows without the field are reported as unknown, never
assumed), and the H8 paired comparison vs the tuned TrueAdaptive
file and vs IRCoT (McNemar exact two-sided, dEM with 95% paired
bootstrap CI).

No LLM is called here. The verification runs on the existing IRCoT
Test-400 BM25 file, which predates the router and must reproduce
EM 0.4200, 2.545 calls/Q.
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

IRCOT_TEST = REPO_ROOT / "results/ircot_test_bm25.jsonl"


def _row(id, route, em, f1=0.0, calls=3, failed=False, route_p=0.8):
    r = {
        "id": id,
        "failed": failed,
        "em": em,
        "f1": f1,
        "llm_calls": calls,
        "gold": "Paris",
    }
    if route is not None:
        r["route"] = route
        r["route_p"] = route_p
    return r


def test_adaptive_rag_metrics_synthetic():
    rows = [
        _row("a", "A", 1, f1=1.0, calls=1),
        _row("b", "A", 0, f1=0.0, calls=1),
        _row("c", "B", 1, f1=0.9, calls=2),
        _row("d", "C", 1, f1=0.8, calls=5),
        _row("e", "C", 0, f1=0.2, calls=6),
        _row("f", None, 0, f1=0.0, calls=3),  # no route field -> unknown
    ]
    m = analyzer.adaptive_rag_metrics(rows)
    assert m["n"] == 6
    assert m["failed"] == 0
    assert m["em"] == 3 / 6
    assert round(m["calls"], 2) == 3.00  # (1+1+2+5+6+3)/6
    assert m["routes"]["A"] == {"n": 2, "em": 0.5, "calls": 1.0}
    assert m["routes"]["B"] == {"n": 1, "em": 1.0, "calls": 2.0}
    assert m["routes"]["C"] == {"n": 2, "em": 0.5, "calls": 5.5}
    assert m["routes"]["unknown"] == {"n": 1, "em": 0.0, "calls": 3.0}


def test_adaptive_rag_failed_rows_excluded_but_counted():
    rows = [
        _row("a", "B", 1, calls=2),
        _row("b", "C", 0, calls=5, failed=True),
    ]
    m = analyzer.adaptive_rag_metrics(rows)
    assert m["n"] == 1
    assert m["failed"] == 1
    assert m["em"] == 1.0
    assert m["routes"]["B"] == {"n": 1, "em": 1.0, "calls": 2.0}
    assert "C" not in m["routes"]


def test_paired_comparison_synthetic():
    # AR: a,b correct; other: b,c correct -> AR-only 1 (a), other-only 1 (c).
    ar = [_row("a", "B", 1), _row("b", "B", 1), _row("c", "B", 0)]
    other = [_row("a", None, 0), _row("b", None, 1), _row("c", None, 1)]
    p = analyzer.adaptive_rag_paired(ar, other)
    assert p["n"] == 3
    assert p["ar_only"] == 1
    assert p["other_only"] == 1
    assert p["d_em"] == 0.0
    assert p["mcnemar_p"] == 1.0


def test_paired_comparison_uses_id_intersection():
    ar = [_row("a", "B", 1), _row("b", "B", 0)]
    other = [_row("a", None, 0), _row("z", None, 1)]
    p = analyzer.adaptive_rag_paired(ar, other)
    assert p["n"] == 1  # only id "a" is shared
    assert p["ar_only"] == 1
    assert p["other_only"] == 0


def test_stored_ircot_test_reproduces():
    # Tasks.md C.2 verification: on the existing IRCoT Test-400 file
    # the section reproduces EM 0.4200, 2.545 calls/Q — and every row
    # is "unknown" (no route field predates the router).
    rows = analyzer.load(str(IRCOT_TEST))
    assert len(rows) == 400
    m = analyzer.adaptive_rag_metrics(rows)
    assert m["failed"] == 0
    assert round(m["em"], 4) == 0.4200
    assert round(m["calls"], 3) == 2.545
    assert set(m["routes"]) == {"unknown"}
    assert m["routes"]["unknown"]["n"] == 400


def test_adaptive_rag_section_prints(capsys):
    rows = [
        _row("a", "A", 1, f1=1.0, calls=1),
        _row("b", "B", 0, f1=0.0, calls=2),
        _row("c", "C", 1, f1=0.8, calls=5),
    ]
    analyzer.adaptive_rag_section("synthetic", rows)
    out = capsys.readouterr().out
    assert "16. Adaptive-RAG baseline (synthetic)" in out
    assert "EM=0.6667" in out
    assert "route A: n=1" in out
    assert "route B: n=1" in out
    assert "route C: n=1" in out


def test_adaptive_rag_section_paired_lines(capsys):
    ar = [_row("a", "B", 1), _row("b", "B", 1), _row("c", "B", 0)]
    ta = [_row("a", None, 0), _row("b", None, 1), _row("c", None, 1)]
    ir = [_row("a", None, 1), _row("b", None, 0), _row("c", None, 0)]
    analyzer.adaptive_rag_section("synthetic", ar, ta_rows=ta, ircot_rows=ir)
    out = capsys.readouterr().out
    assert "H8 vs tuned TrueAdaptive" in out
    assert "vs IRCoT" in out
    assert "McNemar" in out
    assert "dEM" in out
