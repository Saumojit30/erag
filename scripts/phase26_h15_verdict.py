"""Phase 2.6 H15 verdict: paired comparison of the two Dev-100 A/B files.

Computes EM/F1/calls-Q (paired, with McNemar + bootstrap CIs), the
trigger rate, and fixes/breaks on triggered rows, then prints the gate
decision. Gate (pre-registered): dEM >= +0.02 AND dcalls <= +0.5 AND
fixes > breaks on triggered rows. Usage:

    .venv/bin/python scripts/phase26_h15_verdict.py \
        results/trueadaptive/erag_p26_h15_base_dev.jsonl \
        results/trueadaptive/erag_p26_h15_ranked_dev.jsonl
"""

import json
import sys

sys.path.insert(0, ".")
from src.eval.stats import mcnemar_exact, paired_bootstrap


def load(path):
    seen = {}
    for line in open(path):
        if line.strip():
            row = json.loads(line)
            seen[row["id"]] = row
    return seen


def main(base_path, ranked_path):
    base, ranked = load(base_path), load(ranked_path)
    ids = sorted(set(base) & set(ranked))
    print(f"paired N: {len(ids)} "
          f"(base {len(base)}, ranked {len(ranked)}, "
          f"failed base {sum(1 for r in base.values() if r.get('failed'))} / "
          f"ranked {sum(1 for r in ranked.values() if r.get('failed'))})")
    for name, rows in (("baseline", base), ("ranked", ranked)):
        rs = [rows[i] for i in ids]
        n = len(rs)
        em = sum(r["em"] for r in rs) / n
        f1 = sum(r["f1"] for r in rs) / n
        calls = sum(r["llm_calls"] for r in rs) / n
        ch = sum(r["cache_hits"] for r in rs) / n
        print(f"{name}: EM={em:.4f} F1={f1:.4f} calls/Q={calls:.2f} "
              f"cache_hits/Q={ch:.2f}")
    trig = [i for i in ids if ranked[i].get("support_ranked")]
    fixed = sum(1 for i in trig if base[i]["em"] == 0 and ranked[i]["em"] == 1)
    broke = sum(1 for i in trig if base[i]["em"] == 1 and ranked[i]["em"] == 0)
    print(f"trigger fired: {len(trig)}/{len(ids)}; "
          f"on triggered rows fixed={fixed} broke={broke}")
    a_em = [base[i]["em"] for i in ids]
    b_em = [ranked[i]["em"] for i in ids]
    print("McNemar:", mcnemar_exact([bool(x) for x in a_em],
                                     [bool(x) for x in b_em]))
    print("paired bootstrap dEM (ranked-base):",
          tuple(round(x, 4) for x in paired_bootstrap(a_em, b_em)))
    print("paired bootstrap dF1:",
          tuple(round(x, 4) for x in paired_bootstrap(
              [base[i]["f1"] for i in ids], [ranked[i]["f1"] for i in ids])))
    print("paired bootstrap dcalls:",
          tuple(round(x, 2) for x in paired_bootstrap(
              [base[i]["llm_calls"] for i in ids],
              [ranked[i]["llm_calls"] for i in ids])))
    d_em = sum(b_em) / len(b_em) - sum(a_em) / len(a_em)
    d_calls = (sum(ranked[i]["llm_calls"] for i in ids)
               - sum(base[i]["llm_calls"] for i in ids)) / len(ids)
    gate = d_em >= 0.02 and d_calls <= 0.5 and fixed > broke
    print(f"GATE: dEM {d_em:+.4f}, dcalls {d_calls:+.2f}, "
          f"fixed {fixed} > broke {broke} -> {'PASS' if gate else 'FAIL'}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
