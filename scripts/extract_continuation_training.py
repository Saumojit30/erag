"""Extract the learned-continuation-policy training set (step 7, A.1/A.2).

Reads ONLY the post-step-4 tuned dev file
(results/trueadaptive/erag_trueadaptive_bm25_dev_theta_a.jsonl) and
data/manifests/dev.jsonl, and writes data/continuation_training_dev.jsonl
— one flat row per dev question with the design.md hop-0 features, the
label (hop-0 draft correct by repo exact_match), and the call accounting
the simulation needs.

Rules (design.md / tasks.md):
- The input MUST be a dev file: assert_dev_input refuses any path whose
  name does not contain "dev" or that contains "test". Test-400 files
  are never valid input here — training on test would contaminate the
  Phase 2 verdict.
- The row's `draft` field is the canonical draft; trace[0]['answer'] is
  the hop-0 draft. The draft-unknown feature is the row draft field
  being literally 'unknown' (the pre-registered verification count is
  6 — the 2 empty-draft rows are NOT counted here).
- The row's `recall` is FINAL recall and is never used as a hop-0
  feature. Hop-0 recall is recomputed from the manifest
  supporting_facts vs trace[0]['pool'] titles (the H6 method).
- Call accounting (verified as an invariant for EVERY row):
  hop-0 calls = 1 draft + 1 extraction + SC samples, where SC samples
  are 0 when SC was skipped on the Fast Path (c0_source ==
  "fast_path_min_eff"), 2 when c0 == 1.0, else 3. (Sequential SC stops
  at 2 only on two agreeing samples, so c0 == 1.0 implies 2 samples
  and c0 in {1/3, 2/3} implies 3; c0 == 0.5 cannot occur.) Later hops:
  1 draft + 1 extraction iff the draft changed vs the hop-0 draft
  (incremental claim reuse); +1 for a grounded re-read when triggered.
  EIG probes cost 0 (eig_strategy direct) and post-hop resample costs
  0 (post_hop_resample never). If the invariant fails for any row,
  main() refuses to write the training set.
- The oracle ceiling (perfect draft-correctness model: STOP on correct
  drafts, CONTINUE on wrong ones) is computed under the same
  prefix-validity rule as the simulation: CONTINUE rows whose stored
  trace stopped at hop 0 are EXCLUDED (no simulable outcome).

No LLM calls, no src/ changes, no Test-400 file is opened.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from src.eval.metrics import exact_match, f1_score

DEV_FILE = "results/trueadaptive/erag_trueadaptive_bm25_dev_theta_a.jsonl"
DEV_MANIFEST = "data/manifests/dev.jsonl"
OUT = "data/continuation_training_dev.jsonl"

# Hop-0 features in order (design.md). `fast_path` and `sc_skipped` are
# the same fact (c0_source == "fast_path_min_eff" iff
# sc_skipped_fast_path); both are extracted, but the model feature list
# in train_continuation_policy.py drops `sc_skipped` — perfect
# collinearity would split the coefficient arbitrarily between them.
FEATURES = [
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
    "sc_skipped",
]


def assert_dev_input(path):
    """Refuse any input file that is not a dev file (assert on the path)."""
    name = Path(path).name.lower()
    if "test" in name or "dev" not in name:
        raise ValueError(
            f"refusing non-dev input file: {path!r} — the continuation "
            "policy trains on dev traces only; test files would "
            "contaminate the Phase 2 verdict"
        )


def load_rows(path):
    """Load a result JSONL, deduped by id keeping the LAST row."""
    assert_dev_input(path)
    seen = {}
    for line in open(path):
        if line.strip():
            r = json.loads(line)
            seen[r["id"]] = r
    return list(seen.values())


def load_manifest(path):
    assert_dev_input(path)
    out = {}
    for line in open(path):
        if line.strip():
            item = json.loads(line)
            out[item["_id"]] = item
    return out


def hop0_recall(row, manifest_item):
    """Hop-0 recall: gold supporting titles vs trace[0] pool titles."""
    gold = {t for t, _ in manifest_item.get("supporting_facts", [])}
    pool0 = set((row.get("trace") or [{}])[0].get("pool") or [])
    if not gold:
        return 0.0
    return len(gold & pool0) / len(gold)


def hop0_calls(row):
    """LLM calls made during hop 0: draft + extraction + SC samples."""
    if row.get("c0_source") == "fast_path_min_eff":
        sc = 0
    elif row.get("c0") == 1.0:
        sc = 2
    else:
        sc = 3
    return 1 + 1 + sc


def later_calls(row):
    """LLM calls after hop 0: per-hop draft (+ extraction iff the draft
    changed vs the hop-0 draft), plus the grounded re-read if triggered."""
    from src.eval.metrics import normalize_answer

    init = normalize_answer((row.get("trace") or [{}])[0].get("answer", ""))
    total = 0
    for hop in (row.get("trace") or [])[1:]:
        total += 1  # draft
        if normalize_answer(hop.get("answer", "")) != init:
            total += 1  # extraction (incremental reuse skipped it otherwise)
    if row.get("grounded_reread"):
        total += 1
    return total


def verify_accounting(row):
    """hop-0 calls + later-hop calls == stored llm_calls."""
    return hop0_calls(row) + later_calls(row) == row["llm_calls"]


def extract_features(row, manifest_item):
    """One flat training row: design.md hop-0 features + label + the
    fields the counterfactual simulation needs."""
    graph = (row.get("trace") or [{}])[0].get("graph") or []
    statuses = [c.get("status") for c in graph]
    ab = [c for c in graph if c.get("answer_bearing")]
    confs = [c.get("conf", 0.0) for c in graph]
    hop0_answer = (row.get("trace") or [{}])[0].get("answer", "")
    return {
        "id": row["id"],
        # hop-0 features (design.md, in FEATURES order)
        "c0": float(row.get("c0", 0.0)),
        "fast_path": 1 if row.get("c0_source") == "fast_path_min_eff" else 0,
        "n_supported": statuses.count("supported"),
        "n_unresolved": statuses.count("unresolved"),
        "n_contradicted": statuses.count("contradicted"),
        "n_conflict": sum(1 for c in graph if c.get("conflict")),
        "ab_supported": 1 if any(c.get("status") == "supported" for c in ab) else 0,
        "ab_contradicted": 1 if any(c.get("status") == "contradicted" for c in ab) else 0,
        "mean_claim_conf": (sum(confs) / len(confs)) if confs else 0.0,
        "hop0_recall": hop0_recall(row, manifest_item),
        "type_comparison": 1 if row.get("type") == "comparison" else 0,
        "draft_unknown": 1 if row.get("draft") == "unknown" else 0,
        "sc_skipped": 1 if row.get("sc_skipped_fast_path") else 0,
        # label: hop-0 draft correct by repo exact_match
        "label": int(exact_match(hop0_answer, row["gold"])),
        # call accounting + simulation inputs
        "hop0_calls": hop0_calls(row),
        "total_calls": row["llm_calls"],
        "cache_hits": row.get("cache_hits", 0),
        "hops": row.get("hops", 0),
        "hop0_answer": hop0_answer,
        "final_answer": row.get("answer", ""),
        "final_em": float(row.get("em", 0)),
        "final_f1": float(row.get("f1", 0.0)),
        "hop0_f1": f1_score(hop0_answer, row["gold"]),
        "gold": row["gold"],
        "accounting_ok": bool(verify_accounting(row)),
    }


def oracle_ceiling(rows):
    """Perfect draft-correctness model under the simulation rule.

    STOP on correct drafts (hop-0 draft + hop-0 calls), CONTINUE on
    wrong ones (stored final answer + stored total calls); CONTINUE
    rows whose stored trace stopped at hop 0 are EXCLUDED. Bounds what
    any policy can win here — a policy near the oracle is suspicious,
    not impressive (design.md).
    """
    ems, calls, excluded = [], [], 0
    for r in rows:
        if r["label"] == 1:
            ems.append(1.0)
            calls.append(r["hop0_calls"])
        elif r["hops"] == 0:
            excluded += 1
        else:
            ems.append(r["final_em"])
            calls.append(r["total_calls"])
    n = len(ems)
    return {
        "included": n,
        "excluded": excluded,
        "em": (sum(ems) / n) if n else 0.0,
        "calls": (sum(calls) / n) if n else 0.0,
    }


def extract_all(dev_path, manifest_path):
    """Extract the training rows and the verification summary."""
    dev_rows = load_rows(dev_path)
    manifest = load_manifest(manifest_path)
    rows = [extract_features(r, manifest[r["id"]]) for r in dev_rows]
    ok = [r for r in dev_rows if not r.get("failed", False)]
    hop0_correct = [exact_match((r.get("trace") or [{}])[0].get("answer", ""), r["gold"]) for r in ok]
    from collections import Counter

    summary = {
        "n": len(dev_rows),
        "failed": sum(1 for r in dev_rows if r.get("failed", False)),
        "hop0_em": (sum(hop0_correct) / len(hop0_correct)) if hop0_correct else 0.0,
        "final_em": (sum(r["em"] for r in ok) / len(ok)) if ok else 0.0,
        "fixed": sum(1 for r, c in zip(ok, hop0_correct) if not c and r["em"] == 1),
        "broke": sum(1 for r, c in zip(ok, hop0_correct) if c and r["em"] == 0),
        "hops": dict(sorted(Counter(r.get("hops", 0) for r in ok).items())),
        "abstained": sum(1 for r in ok if r.get("abstained")),
        "draft_unknown": sum(1 for r in ok if r.get("draft") == "unknown"),
        "calls_per_q": (sum(r["llm_calls"] for r in ok) / len(ok)) if ok else 0.0,
        "accounting_violations": sum(1 for r in rows if not r["accounting_ok"]),
        "oracle": oracle_ceiling(rows),
        "rows": rows,
    }
    return summary


# Pre-registered verification numbers (tasks.md A.1): the extraction MUST
# reproduce these exactly before any training.
EXPECTED = {
    "n": 100,
    "failed": 0,
    "hop0_em": 0.4800,
    "final_em": 0.5100,
    "fixed": 6,
    "broke": 3,
    "hops": {0: 45, 1: 45, 2: 10},
    "abstained": 15,
    "draft_unknown": 6,
    "calls_per_q": 4.65,
    "accounting_violations": 0,
}


def check_verification(summary):
    """Fail loudly unless the extraction reproduces the pre-registered
    verification numbers exactly."""
    bad = []
    for key, want in EXPECTED.items():
        got = summary[key]
        if isinstance(want, float):
            if round(float(got), 4) != want:
                bad.append(f"{key}: got {got!r}, want {want!r}")
        elif got != want:
            bad.append(f"{key}: got {got!r}, want {want!r}")
    if bad:
        raise AssertionError(
            "extraction does not reproduce the verification numbers:\n"
            + "\n".join("  " + b for b in bad)
        )


def main():
    ap = argparse.ArgumentParser(description="Extract continuation-policy training set (dev only)")
    ap.add_argument("--dev", default=DEV_FILE, help="post-step-4 tuned dev file")
    ap.add_argument("--manifest", default=DEV_MANIFEST, help="dev manifest")
    ap.add_argument("--out", default=OUT, help="training-set output JSONL")
    args = ap.parse_args()

    summary = extract_all(args.dev, args.manifest)
    check_verification(summary)

    with open(args.out, "w") as f:
        for r in summary["rows"]:
            f.write(json.dumps(r) + "\n")
    o = summary["oracle"]
    print(f"wrote {args.out}: N={summary['n']} deduped, failed={summary['failed']}")
    print(f"hop-0 draft EM={summary['hop0_em']:.4f} final EM={summary['final_em']:.4f} "
          f"fixed={summary['fixed']} broke={summary['broke']} hops={summary['hops']}")
    print(f"abstained={summary['abstained']} draft-unknown={summary['draft_unknown']} "
          f"calls/Q={summary['calls_per_q']:.2f} accounting violations={summary['accounting_violations']}")
    print(f"oracle ceiling (perfect draft-correctness model): included={o['included']} "
          f"excluded={o['excluded']} EM={o['em']:.4f} calls/Q={o['calls']:.2f}")
    print("verification numbers reproduced exactly — training may proceed.")


if __name__ == "__main__":
    main()
