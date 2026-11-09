"""Tests for the --theta section (tuning step 4, task A.1).

The section (scripts/analyze_trueadaptive_test400.py, section 13) reports
selective-answering metrics at abstention thresholds for the --ta-dev file:
EM, F1, selective EM, wrong-answer rate among answered, wrong answers among
all rows, coverage, mean llm_calls/cache_hits/live calls per question, and
the two unknown populations — plus the counterfactual table at
t = 0.40..0.80, computed the same way as section 4.

The populations are classified by DRAFT TEXT (is_unknown from
src/eval/metrics.py — "unknown" or the empty string counts), NOT by the
abstained flag (tasks.md A.1, design.md): at higher thresholds a
model-unknown row flips abstained=True in a live run while its answer
stays "unknown", and classifying by the flag would move it into the
system-abstained population. One stored dev row already shows why the
distinction matters: its draft is literally "unknown" AND its abstained
flag is set (conf 0.258) — by draft text it is model-unknown, by flag it
is system-abstained (see test_flag_counts_differ_by_one_swapped_row).

No LLM is called here — the tests check the computation on synthetic rows
and on the stored step-2 tuned dev file.
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


def _row(id, draft, conf, em, abstained=False, f1=0.0, calls=5, hits=0):
    return {
        "id": id,
        "failed": False,
        "draft": draft,
        "abstained": abstained,
        "answer_conf": conf,
        "em": em,
        "f1": f1,
        "llm_calls": calls,
        "cache_hits": hits,
    }


def test_populations_classified_by_draft_text():
    rows = [
        _row("a", "unknown", 0.95, 0),  # model-unknown (reader refused)
        _row("b", "", 0.42, 0),  # model-unknown (empty draft counts)
        _row("c", "Paris", 0.25, 0, abstained=True),  # system-abstained
        # Draft is "unknown" AND the flag is set: the reader refused, so
        # this is model-unknown, not system-abstained.
        _row("d", "unknown", 0.26, 0, abstained=True),
        _row("e", "Paris", 0.90, 1),  # answered, correct
        _row("f", "London", 0.80, 0),  # answered, wrong
    ]
    m = analyzer.theta_metrics(rows, 0.40)
    assert m["n"] == 6
    assert m["model_unknown"] == 3
    assert m["abstained"] == 1
    assert m["answered"] == 2
    assert m["correct"] == 1
    assert m["em"] == 1 / 6
    assert m["selective_em"] == 0.5
    assert m["wrong_rate"] == 0.5
    assert m["wrong_all"] == 1
    assert m["coverage"] == 2 / 6


def test_live_run_artifact_row_stays_model_unknown():
    # Design.md: at t=0.50 a dev model-unknown row (answer_conf 0.424,
    # empty-string answer) would flip abstained=True in a live run while
    # its answer stays "unknown". It must stay model-unknown at every
    # threshold, not move into the system-abstained population.
    rows = [
        _row("a", "", 0.424, 0, abstained=True),
        _row("b", "Paris", 0.90, 1),
    ]
    for t in (0.40, 0.50, 0.65, 0.80):
        m = analyzer.theta_metrics(rows, t)
        assert m["model_unknown"] == 1
        assert m["abstained"] == 0
        assert m["answered"] == 1


def test_counterfactual_withholds_low_confidence_answers():
    rows = [
        _row("a", "Paris", 0.45, 1),
        _row("b", "London", 0.48, 0),
        _row("c", "Rome", 0.90, 1),
        _row("d", "Madrid", 0.95, 1),
        _row("e", "unknown", 0.99, 0),
    ]
    m40 = analyzer.theta_metrics(rows, 0.40)
    assert (m40["answered"], m40["correct"]) == (4, 3)
    assert m40["em"] == 3 / 5
    assert m40["selective_em"] == 0.75
    assert m40["wrong_rate"] == 0.25
    assert m40["coverage"] == 0.8
    # At t=0.50 the two low-confidence answers (one correct, one wrong)
    # are withheld; the model-unknown row stays unknown.
    m50 = analyzer.theta_metrics(rows, 0.50)
    assert (m50["answered"], m50["correct"]) == (2, 2)
    assert m50["em"] == 2 / 5
    assert m50["selective_em"] == 1.0
    assert m50["wrong_rate"] == 0.0
    assert m50["coverage"] == 0.4


def test_abstained_and_model_unknown_stay_out_at_any_threshold():
    rows = [
        _row("a", "unknown", 0.95, 0),
        _row("b", "Paris", 0.25, 0, abstained=True),
        _row("c", "Rome", 0.90, 1),
    ]
    m = analyzer.theta_metrics(rows, 0.99)
    assert m["answered"] == 0
    assert m["correct"] == 0
    assert m["em"] == 0.0
    assert m["selective_em"] == 0.0
    assert m["coverage"] == 0.0
    assert m["model_unknown"] == 1
    assert m["abstained"] == 1


def test_wrong_rate_is_one_minus_selective_em():
    rows = [
        _row("a", "Paris", 0.9, 1),
        _row("b", "London", 0.9, 0),
        _row("c", "Rome", 0.9, 0),
    ]
    m = analyzer.theta_metrics(rows, 0.40)
    assert m["selective_em"] == 1 / 3
    assert m["wrong_rate"] == 1 - m["selective_em"]


def test_plateau_when_no_confidence_in_gap():
    rows = [
        _row("a", "Paris", 0.45, 1),
        _row("b", "London", 0.90, 1),
        _row("c", "Rome", 0.95, 0),
    ]
    # No answered row has answer_conf in [0.50, 0.65), so the 0.50 and
    # 0.65 counterfactuals must be identical.
    assert analyzer.theta_metrics(rows, 0.50) == analyzer.theta_metrics(rows, 0.65)


def test_flag_counts_differ_by_one_swapped_row():
    # The stored step-2 tuned dev file, flag-based counts (what section 12
    # reports): 7 model-unknown, 8 system-abstained. The --theta section
    # classifies by draft text instead, which swaps exactly one row: the
    # abstained row whose draft is literally "unknown" (conf 0.258).
    rows = analyzer.load(str(DEV_CLAIMS))
    ok = [r for r in rows if not r.get("failed", False)]
    assert len(ok) == 100
    flag_unk = [r for r in ok if r.get("unknown") and not r.get("abstained")]
    flag_ab = [r for r in ok if r.get("abstained")]
    assert len(flag_unk) == 7
    assert len(flag_ab) == 8
    swapped = [r for r in flag_ab if r.get("draft") == "unknown"]
    assert len(swapped) == 1
    assert swapped[0]["answer_conf"] < 0.4


def test_stored_dev_file_reproduces_verification_numbers():
    # Tasks.md A.1 verification numbers on the step-2 tuned dev file
    # (N=100 deduped, 0 failed). Populations are the draft-text counts
    # (8 model-unknown, 7 abstained) — see the test above for why they
    # differ from the flag counts (7/8).
    rows = analyzer.load(str(DEV_CLAIMS))
    assert len(rows) == 100
    assert sum(1 for r in rows if r.get("failed", False)) == 0
    m40 = analyzer.theta_metrics(rows, 0.40)
    assert round(m40["em"], 4) == 0.5400
    assert round(m40["f1"], 4) == 0.6391
    assert round(m40["selective_em"], 4) == 0.6353
    assert (m40["correct"], m40["answered"]) == (54, 85)
    assert round(m40["wrong_rate"], 4) == 0.3647
    assert m40["wrong_all"] == 31
    assert round(m40["coverage"], 4) == 0.8500
    assert round(m40["calls"], 2) == 4.65
    assert round(m40["cache_hits"], 2) == 2.53
    assert round(m40["live_calls"], 2) == 2.12
    assert m40["model_unknown"] == 8
    assert m40["abstained"] == 7

    m50 = analyzer.theta_metrics(rows, 0.50)
    assert round(m50["em"], 4) == 0.5100
    assert round(m50["selective_em"], 4) == 0.6456
    assert round(m50["wrong_rate"], 4) == 0.3544
    assert round(m50["coverage"], 4) == 0.7900

    # t=0.65 identical to t=0.50 (answer_conf gap 0.492 -> 0.667).
    assert analyzer.theta_metrics(rows, 0.65) == m50

    m75 = analyzer.theta_metrics(rows, 0.75)
    assert round(m75["em"], 4) == 0.4700
    assert round(m75["selective_em"], 4) == 0.6351
    assert round(m75["wrong_rate"], 4) == 0.3649
    assert round(m75["coverage"], 4) == 0.7400


def test_theta_section_prints(capsys):
    rows = [
        _row("a", "Paris", 0.90, 1, calls=4, hits=2),
        _row("b", "unknown", 0.95, 0, calls=6, hits=0),
    ]
    analyzer.theta_section("synthetic", rows)
    out = capsys.readouterr().out
    assert "13. Theta_abs selective answering (synthetic)" in out
    assert "EM=0.5000" in out
    assert "selective EM=1.0000" in out
    assert "t=0.50:" in out
    assert "t=0.80:" in out
