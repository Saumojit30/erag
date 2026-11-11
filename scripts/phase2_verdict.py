"""Phase 2 verdict computation (master plan section 4.2 + H1/H10/H11).

Reads stored result files only -- no live calls. Every comparison is
paired on question id, deduped keeping the last row per id. EM/F1/calls
come from the rows as stored (repo exact_match was applied by the runner).

Usage:
    python scripts/phase2_verdict.py
"""
import json
import sys
from statistics import mean

sys.path.insert(0, ".")
from src.eval.stats import mcnemar_exact, paired_bootstrap

TUNED = "results/trueadaptive/erag_trueadaptive_tuned_test.jsonl"
IRCOT_V2 = "results/ircot_test_v2_bm25.jsonl"
IRCOT_V1 = "results/ircot_test_bm25.jsonl"
TA_V1 = "results/trueadaptive/erag_trueadaptive_test_bm25.jsonl"
STANDARD = "results/bm25/standard_bm25_test.jsonl"
BALANCED = "results/bm25/erag_balanced_bm25_test.jsonl"


def load(path):
    rows = [json.loads(line) for line in open(path) if line.strip()]
    seen = {}
    for r in rows:
        seen[r["id"]] = r
    return list(seen.values())


def em_list(rows):
    ok = [r for r in rows if not r.get("failed", False)]
    return [float(r["em"]) for r in ok]


def paired(a_rows, b_rows):
    """Paired comparison of two systems on shared ids (a vs b)."""
    a = {r["id"]: r for r in a_rows if not r.get("failed", False)}
    b = {r["id"]: r for r in b_rows if not r.get("failed", False)}
    ids = sorted(set(a) & set(b))
    a_em = [float(a[i]["em"]) for i in ids]
    b_em = [float(b[i]["em"]) for i in ids]
    mc = mcnemar_exact([x == 1.0 for x in a_em], [x == 1.0 for x in b_em])
    # paired_bootstrap(a, b) returns (b - a); swap so d_em is (a - b).
    d, lo, hi = paired_bootstrap(b_em, a_em)
    return {
        "n": len(ids),
        "em_a": mean(a_em),
        "em_b": mean(b_em),
        "d_em": d,
        "ci": (lo, hi),
        "a_only": mc["a_only"],
        "b_only": mc["b_only"],
        "p": mc["p"],
    }


def wrong_rate(rows):
    ok = [r for r in rows if not r.get("failed", False)]
    answered = [r for r in ok if not r.get("unknown", False)]
    wrong = [r for r in answered if r["em"] == 0]
    return len(wrong), len(answered), (len(wrong) / len(answered) if answered else 0.0)


def calls_per_correct(rows):
    ok = [r for r in rows if not r.get("failed", False)]
    calls = mean(r["llm_calls"] for r in ok)
    em = mean(r["em"] for r in ok)
    return calls, em, (calls / em if em else float("inf"))


def main():
    tuned = load(TUNED)
    ircot = load(IRCOT_V2)
    v1 = load(TA_V1)
    standard = load(STANDARD)
    balanced = load(BALANCED)

    print(f"tuned N={len(tuned)}  ircot-v2 N={len(ircot)}  "
          f"v1 N={len(v1)}  standard N={len(standard)}  balanced N={len(balanced)}")

    print("\n=== 4.2 verdict: tuned TrueAdaptive vs fresh IRCoT (BM25, Test-400) ===")
    r = paired(tuned, ircot)
    print(f"n={r['n']} paired; tuned EM={r['em_a']:.4f} IRCoT EM={r['em_b']:.4f} "
          f"dEM={r['d_em']:+.4f} 95% CI [{r['ci'][0]:+.4f}, {r['ci'][1]:+.4f}]")
    print(f"McNemar: tuned-only={r['a_only']} IRCoT-only={r['b_only']} p={r['p']:.4g}")
    if r["em_a"] > r["em_b"] and r["p"] < 0.05:
        verdict = "WIN"
    elif r["em_a"] <= r["em_b"]:
        verdict = "LOSS"
    else:
        verdict = "INCONCLUSIVE"
    print(f"VERDICT: {verdict} (Win: tuned EM > IRCoT EM and p<0.05; "
          f"Loss: tuned <= IRCoT; Inconclusive: tuned > IRCoT but p>=0.05)")

    print("\n=== H1 confirmatory re-run: tuned vs Standard-BM25 ===")
    h1 = paired(tuned, standard)
    print(f"n={h1['n']} paired; tuned EM={h1['em_a']:.4f} Standard EM={h1['em_b']:.4f} "
          f"dEM={h1['d_em']:+.4f} 95% CI [{h1['ci'][0]:+.4f}, {h1['ci'][1]:+.4f}]")
    print(f"McNemar: tuned-only={h1['a_only']} Standard-only={h1['b_only']} p={h1['p']:.4g}")

    print("\n=== Tuned vs v1 TrueAdaptive (reported, not gated) ===")
    vv = paired(tuned, v1)
    print(f"n={vv['n']} paired; tuned EM={vv['em_a']:.4f} v1 EM={vv['em_b']:.4f} "
          f"dEM={vv['d_em']:+.4f} 95% CI [{vv['ci'][0]:+.4f}, {vv['ci'][1]:+.4f}]")
    print(f"McNemar: tuned-only={vv['a_only']} v1-only={vv['b_only']} p={vv['p']:.4g}")

    print("\n=== H11: wrong-answer rate (wrong / answered) ===")
    for name, rows in [("tuned", tuned), ("IRCoT v2", ircot)]:
        w, a, rate = wrong_rate(rows)
        print(f"{name}: {w}/{a} = {rate:.4f}")

    print("\n=== H10: LLM calls per correct answer ===")
    for name, rows in [("tuned", tuned), ("IRCoT v2", ircot), ("Balanced", balanced)]:
        calls, em, cpc = calls_per_correct(rows)
        print(f"{name}: {calls:.2f} calls/Q / EM {em:.4f} = {cpc:.2f} calls per correct answer")


if __name__ == "__main__":
    main()
