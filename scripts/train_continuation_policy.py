"""Fit the learned continuation policy and run the counterfactual
simulation (step 7, A.3).

Loads the A.1 training set (data/continuation_training_dev.jsonl — dev
only; the loader refuses any path that is not a dev file), fits a
logistic regression on the standardized hop-0 features, chooses tau by
5-fold cross-validation to maximize saved calls at simulated EM >=
0.5000, and simulates the policy on dev from the stored traces.

Pre-registered simulation rule (design.md): STOP -> hop-0 draft +
hop-0 calls; CONTINUE -> stored final answer + stored total calls.
Rows where the policy says CONTINUE but the stored trace stopped at
hop 0 have no simulable outcome: EXCLUDED from the simulated numbers,
counted and reported. If they exceed 10% of rows, Phase A STOPS here
(no Gate A verdict — the simulation cannot gate the policy).

Gate A (design.md, out-of-fold predictions only): simulated EM >=
0.5000 AND simulated calls/Q strictly below 4.65. If logistic
regression fails Gate A, ONE alternative is tried — a depth-2 decision
tree — and the better cross-validated result is taken; no third model,
no feature search after seeing results.

This script does NOT train the final model and does NOT write the
policy artifact: if Gate A passes, that is reported and the final
training is the parent's decision. It writes the cross-validated
simulation summary (data/continuation_simulation_dev.json) for the
analyzer's --policy agreement check.

Simulation limitations (recorded, not hidden): the STOP branch uses
the hop-0 draft and hop-0 calls, ignoring the end-of-run grounded
re-read (+1 call, may change the answer) and abstention that would
apply live to a stopped row. Live calls/Q is reported as the stored
live calls/Q over included rows — an upper bound, since hop-level
cache hits are not stored and STOP can only remove calls.
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")

from src.eval.metrics import is_unknown

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

_EXTRACT = REPO_ROOT / "scripts" / "extract_continuation_training.py"
_spec = importlib.util.spec_from_file_location(
    "extract_continuation_training", _EXTRACT
)
extract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extract)

from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

TRAINING_FILE = "data/continuation_training_dev.jsonl"
SIM_OUT = "data/continuation_simulation_dev.json"
BASELINE_CALLS = 4.65
BASELINE_EM = 0.5100
GATE_EM_FLOOR = 0.5000
CV_SEED = 42

# Model features: the extraction feature list minus `sc_skipped`, which
# is perfectly collinear with `fast_path` (c0_source ==
# "fast_path_min_eff" iff sc_skipped_fast_path). Keeping both would
# split the coefficient arbitrarily between them.
MODEL_FEATURES = [f for f in extract.FEATURES if f != "sc_skipped"]


def load_training(path):
    """Load the A.1 training set (dev only — refuses test paths)."""
    extract.assert_dev_input(path)
    return [json.loads(line) for line in open(path) if line.strip()]


def simulate(rows, proba, tau):
    """Counterfactual simulation of the policy on stored traces.

    Decision: CONTINUE iff P(draft correct) < tau, else STOP. STOP rows
    take the hop-0 draft and hop-0 calls; CONTINUE rows take the stored
    final answer and stored total calls. CONTINUE rows whose stored
    trace stopped at hop 0 are EXCLUDED (no simulable outcome).
    Returns the simulated measures over included rows only.
    """
    included_em, included_f1, included_calls, included_live = [], [], [], []
    n_stop = n_continue = n_excluded = 0
    answered = 0
    for r, p in zip(rows, proba):
        cont = p < tau
        if cont and r["hops"] == 0:
            n_excluded += 1
            continue
        if cont:
            n_continue += 1
            included_em.append(float(r["final_em"]))
            included_f1.append(float(r["final_f1"]))
            included_calls.append(r["total_calls"])
            if not is_unknown(r["final_answer"]):
                answered += 1
        else:
            n_stop += 1
            included_em.append(float(r["label"]))
            included_f1.append(float(r["hop0_f1"]))
            included_calls.append(r["hop0_calls"])
            if not is_unknown(r["hop0_answer"]):
                answered += 1
        # Stored live calls (upper bound on policy live calls: STOP can
        # only remove calls, and hop-level cache hits are not stored).
        included_live.append(r["total_calls"] - r.get("cache_hits", 0))
    n = len(included_em)
    return {
        "n_included": n,
        "n_excluded": n_excluded,
        "n_stop": n_stop,
        "n_continue": n_continue,
        "em": (sum(included_em) / n) if n else 0.0,
        "f1": (sum(included_f1) / n) if n else 0.0,
        "calls": (sum(included_calls) / n) if n else 0.0,
        "live_calls_upper": (sum(included_live) / n) if n else 0.0,
        "coverage": (answered / n) if n else 0.0,
    }


def oof_proba(make_model, X, y):
    """Out-of-fold P(draft correct) from 5-fold CV (scaler fit per fold
    inside the pipeline — no leakage from held-out rows)."""
    pipe = Pipeline([("scaler", StandardScaler()), ("model", make_model())])
    cv = StratifiedKFold(5, shuffle=True, random_state=CV_SEED)
    return cross_val_predict(pipe, X, y, cv=cv, method="predict_proba")[:, 1]


def choose_tau(rows, proba):
    """Tau grid search on the out-of-fold predictions: maximize saved
    calls subject to simulated EM >= 0.5000. Returns (tau, sim, feasible).
    If no tau is feasible, returns the max-EM tau and feasible=False."""
    best = None
    best_em = None
    for tau in [round(0.05 * i, 2) for i in range(1, 20)]:
        sim = simulate(rows, proba, tau)
        saved = BASELINE_CALLS - sim["calls"]
        if sim["em"] >= GATE_EM_FLOOR and (best is None or saved > best[2]):
            best = (tau, sim, saved)
        if best_em is None or sim["em"] > best_em[1]["em"]:
            best_em = (tau, sim, saved)
    if best is not None:
        return best[0], best[1], True
    return best_em[0], best_em[1], False


def evaluate_model(name, make_model, X, y, rows):
    """Cross-validated simulation for one model: OOF proba, tau choice,
    Gate A check on the OOF numbers."""
    proba = oof_proba(make_model, X, y)
    tau, sim, feasible = choose_tau(rows, proba)
    gate = feasible and sim["calls"] < BASELINE_CALLS
    return {
        "model": name,
        "tau": tau,
        "tau_feasible": feasible,
        "sim": sim,
        "gate_a_pass": bool(gate),
        "exclusion_rate": sim["n_excluded"] / len(rows) if rows else 0.0,
    }


def main():
    ap = argparse.ArgumentParser(description="Train + simulate the continuation policy (dev only)")
    ap.add_argument("--training", default=TRAINING_FILE)
    ap.add_argument("--sim-out", default=SIM_OUT)
    args = ap.parse_args()

    rows = load_training(args.training)
    X = np.array([[r[f] for f in MODEL_FEATURES] for r in rows], dtype=float)
    y = np.array([r["label"] for r in rows], dtype=int)
    print(f"training rows: {len(rows)} (labels: {int(y.sum())} correct drafts, "
          f"{len(y) - int(y.sum())} wrong); features: {MODEL_FEATURES}")

    lr = evaluate_model(
        "logistic_regression",
        lambda: LogisticRegression(max_iter=1000, random_state=CV_SEED),
        X, y, rows,
    )
    _report(lr)
    winner = lr

    if not lr["gate_a_pass"]:
        print("logistic regression does not pass Gate A — trying the ONE "
              "pre-registered alternative (depth-2 decision tree).")
        tree = evaluate_model(
            "decision_tree_depth2",
            lambda: DecisionTreeClassifier(max_depth=2, random_state=CV_SEED),
            X, y, rows,
        )
        _report(tree)
        # Better = passes Gate A first, then more saved calls.
        winner = tree if (tree["gate_a_pass"], BASELINE_CALLS - tree["sim"]["calls"]) > (
            lr["gate_a_pass"], BASELINE_CALLS - lr["sim"]["calls"]) else lr

    if winner["exclusion_rate"] > 0.10:
        print(f"STOP: prefix-validity exclusions are {winner['exclusion_rate']:.1%} "
              f"({winner['sim']['n_excluded']}/{len(rows)} rows) — above the 10% "
              "ceiling. The simulation cannot gate the policy; Phase A stops "
              "here and the policy must be evaluated live instead.")
        return

    sim = winner["sim"]
    summary = {
        "model": winner["model"],
        "tau": winner["tau"],
        "n_included": sim["n_included"],
        "n_excluded": sim["n_excluded"],
        "em": sim["em"],
        "f1": sim["f1"],
        "calls": sim["calls"],
        "live_calls_upper": sim["live_calls_upper"],
        "coverage": sim["coverage"],
        "gate_a_pass": winner["gate_a_pass"],
        "baseline_em": BASELINE_EM,
        "baseline_calls": BASELINE_CALLS,
        "training_file": args.training,
        "n_train": len(rows),
    }
    with open(args.sim_out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"wrote simulation summary: {args.sim_out}")
    if winner["gate_a_pass"]:
        print(f"GATE A PASSES on cross-validated numbers ({winner['model']}, "
              f"tau={winner['tau']}): simulated EM={sim['em']:.4f} "
              f"(>= 0.5000), calls/Q={sim['calls']:.2f} (< 4.65). "
              "Final-model training and the artifact are NOT done here — "
              "that is the parent's decision.")
    else:
        print(f"GATE A FAILS on cross-validated numbers ({winner['model']}, "
              f"tau={winner['tau']}): simulated EM={sim['em']:.4f}, "
              f"calls/Q={sim['calls']:.2f}. No wiring, no live run, no "
              "threshold re-picking.")


def _report(result):
    sim = result["sim"]
    print(f"[{result['model']}] tau={result['tau']} "
          f"(feasible at EM>=0.5: {result['tau_feasible']}): "
          f"simulated EM={sim['em']:.4f} F1={sim['f1']:.4f} "
          f"calls/Q={sim['calls']:.2f} (saved {BASELINE_CALLS - sim['calls']:+.2f}) "
          f"live/Q<={sim['live_calls_upper']:.2f} (stored upper bound) "
          f"coverage={sim['coverage']:.3f} "
          f"STOP={sim['n_stop']} CONTINUE={sim['n_continue']} "
          f"excluded={sim['n_excluded']}/{sim['n_included'] + sim['n_excluded']} "
          f"({result['exclusion_rate']:.1%}) — Gate A: "
          f"{'PASS' if result['gate_a_pass'] else 'FAIL'}")


if __name__ == "__main__":
    main()
