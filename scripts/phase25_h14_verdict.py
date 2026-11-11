"""Phase 2.5 H14 verdict: paired comparison of the two Dev-100 A/B files.

Computes EM/F1/calls-Q (paired, with McNemar + bootstrap CIs) and prints
the gate decision. Gate (pre-registered, dev replication check): any
positive paired dEM at <= +1.0 calls/Q. Usage:

    .venv/bin/python scripts/phase25_h14_verdict.py \
        results/trueadaptive/erag_p25_h14_base_dev.jsonl \
        results/trueadaptive/erag_p25_h14_eager_dev.jsonl
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


def main(base_path, eager_path):
    base, eager = load(base_path), load(eager_path)
    ids = sorted(set(base) & set(eager))
    print(f"paired N: {len(ids)} "
          f"(base {len(base)}, eager {len(eager)}, "
          f"failed base {sum(1 for r in base.values() if r.get('failed'))} / "
          f"eager {sum(1 for r in eager.values() if r.get('failed'))})")
    for name, rows in (("baseline", base), ("eager", eager)):
        rs = [rows[i] for i in ids]
        n = len(rs)
        em = sum(r["em"] for r in rs) / n
        f1 = sum(r["f1"] for r in rs) / n
        calls = sum(r["llm_calls"] for r in rs) / n
        ch = sum(r["cache_hits"] for r in rs) / n
        print(f"{name}: EM={em:.4f} F1={f1:.4f} calls/Q={calls:.2f} "
              f"cache_hits/Q={ch:.2f}")
    a_em = [base[i]["em"] for i in ids]
    b_em = [eager[i]["em"] for i in ids]
    print("McNemar:", mcnemar_exact([bool(x) for x in a_em],
                                     [bool(x) for x in b_em]))
    print("paired bootstrap dEM (eager-base):",
          tuple(round(x, 4) for x in paired_bootstrap(a_em, b_em)))
    print("paired bootstrap dF1:",
          tuple(round(x, 4) for x in paired_bootstrap(
              [base[i]["f1"] for i in ids], [eager[i]["f1"] for i in ids])))
    print("paired bootstrap dcalls:",
          tuple(round(x, 2) for x in paired_bootstrap(
              [base[i]["llm_calls"] for i in ids],
              [eager[i]["llm_calls"] for i in ids])))
    d_em = sum(b_em) / len(b_em) - sum(a_em) / len(a_em)
    d_calls = (sum(eager[i]["llm_calls"] for i in ids)
               - sum(base[i]["llm_calls"] for i in ids)) / len(ids)
    gate = d_em > 0 and d_calls <= 1.0
    print(f"GATE: dEM {d_em:+.4f}, dcalls {d_calls:+.2f} -> "
          f"{'PASS' if gate else 'FAIL'}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
