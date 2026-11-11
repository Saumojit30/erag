"""Phase 2.5 H13 verdict: paired comparison of the two Dev-100 A/B files.

Computes EM/F1/calls-Q (paired, with McNemar + bootstrap CIs), the
gold-in-claims rate among full-recall wrong rows for each arm, and the
second-pass yield (median/mean second_pass_added) — then prints the
gate decision. Usage:

    .venv/bin/python scripts/phase25_h13_verdict.py \
        results/trueadaptive/erag_p25_h13_base_dev.jsonl \
        results/trueadaptive/erag_p25_h13_second_dev.jsonl
"""

import json
import re
import statistics
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


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


def claims(row):
    return [c for hop in (row.get("trace") or [])
            for c in (hop.get("graph") or [])]


def gold_in_claims(row):
    g = norm(row["gold"])
    return bool(g) and any(g in norm(c.get("text", "")) for c in claims(row))


def main(base_path, second_path):
    base, second = load(base_path), load(second_path)
    ids = sorted(set(base) & set(second))
    print(f"paired N: {len(ids)} "
          f"(base {len(base)}, second {len(second)}, "
          f"failed base {sum(1 for r in base.values() if r.get('failed'))} / "
          f"second {sum(1 for r in second.values() if r.get('failed'))})")
    for name, rows in (("baseline", base), ("second", second)):
        rs = [rows[i] for i in ids]
        n = len(rs)
        em = sum(r["em"] for r in rs) / n
        f1 = sum(r["f1"] for r in rs) / n
        calls = sum(r["llm_calls"] for r in rs) / n
        ch = sum(r["cache_hits"] for r in rs) / n
        wrong_full = [r for r in rs if r["em"] == 0 and not r.get("unknown")
                      and not r.get("abstained") and r.get("recall") == 1.0]
        gic = sum(1 for r in wrong_full if gold_in_claims(r))
        rate = gic / len(wrong_full) if wrong_full else float("nan")
        print(f"{name}: EM={em:.4f} F1={f1:.4f} calls/Q={calls:.2f} "
              f"cache_hits/Q={ch:.2f} full-recall wrong={len(wrong_full)} "
              f"gold-in-claims={gic} rate={rate:.3f}")
    a_em = [base[i]["em"] for i in ids]
    b_em = [second[i]["em"] for i in ids]
    print("McNemar:", mcnemar_exact([bool(x) for x in a_em],
                                     [bool(x) for x in b_em]))
    print("paired bootstrap dEM (second-base):",
          tuple(round(x, 4) for x in paired_bootstrap(a_em, b_em)))
    print("paired bootstrap dF1:",
          tuple(round(x, 4) for x in paired_bootstrap(
              [base[i]["f1"] for i in ids], [second[i]["f1"] for i in ids])))
    print("paired bootstrap dcalls:",
          tuple(round(x, 2) for x in paired_bootstrap(
              [base[i]["llm_calls"] for i in ids],
              [second[i]["llm_calls"] for i in ids])))
    added = [second[i].get("second_pass_added", 0) for i in ids]
    print(f"second_pass_added: median={statistics.median(added)} "
          f"mean={statistics.mean(added):.2f} "
          f"rows with 0 added={sum(1 for x in added if x == 0)}/{len(added)}")
    # Gate (pre-registered H13 criterion + cost guardrail): rate rises,
    # EM does not fall, calls/Q rise <= +1.0.
    b_wf = [base[i] for i in ids if base[i]["em"] == 0
            and not base[i].get("unknown") and not base[i].get("abstained")
            and base[i].get("recall") == 1.0]
    s_wf = [second[i] for i in ids if second[i]["em"] == 0
            and not second[i].get("unknown") and not second[i].get("abstained")
            and second[i].get("recall") == 1.0]
    b_rate = (sum(1 for r in b_wf if gold_in_claims(r)) / len(b_wf)
              if b_wf else float("nan"))
    s_rate = (sum(1 for r in s_wf if gold_in_claims(r)) / len(s_wf)
              if s_wf else float("nan"))
    d_em = sum(b_em) / len(b_em) - sum(a_em) / len(a_em)
    d_calls = (sum(second[i]["llm_calls"] for i in ids)
               - sum(base[i]["llm_calls"] for i in ids)) / len(ids)
    gate = s_rate > b_rate and d_em >= 0 and d_calls <= 1.0
    print(f"GATE: rate {b_rate:.3f} -> {s_rate:.3f}, dEM {d_em:+.4f}, "
          f"dcalls {d_calls:+.2f} -> {'PASS' if gate else 'FAIL'}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
