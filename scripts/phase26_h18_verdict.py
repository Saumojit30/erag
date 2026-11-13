"""Phase 2.7 H18 verdict: evidence-first answering vs improved-system baseline.

Dev-300 BM25 A/B (first 300 rows of data/manifests_dev500/dev.jsonl),
both arms re-run fresh, paired on question id, deduped keeping the
last row per id. Gate (pre-registered 2026-11-11, decision set amended
2026-11-13 before the run — Dev-100 cannot resolve a +0.02 effect):
dEM >= +0.02 AND wrong-answer rate not up AND dcalls <= +0.5.
Extend rule (pre-registered 2026-11-13, before the run): if dEM lands
in [+0.01, +0.04] with the 95% CI straddling 0, the verdict is
AMBIGUOUS and the A/B extends to the full Dev-500 instead of calling it.

The mechanism applies to every row (no trigger), so fixed/broke is
reported on rows where the two arms' answers differ, and the
gold-in-claims rate among full-recall wrong rows (H13 method) is
reported per arm: extractor coverage IS the mechanism here.

Usage:
    .venv/bin/python scripts/phase26_h18_verdict.py \\
        results/trueadaptive/erag_p27_h18_base_dev300.jsonl \\
        results/trueadaptive/erag_p27_h18_evidence_dev300.jsonl
"""

import json
import sys

sys.path.insert(0, ".")
from src.eval.stats import mcnemar_exact, paired_bootstrap
from src.eval.metrics import normalize_answer as norm


def load(path):
    seen = {}
    for line in open(path):
        if line.strip():
            row = json.loads(line)
            seen[row["id"]] = row
    return seen


def is_unknown_answer(r):
    return norm(r.get("answer", "")) in ("", "unknown")


def wrong_rate(rows):
    answered = [r for r in rows if not r.get("abstained")
                and not is_unknown_answer(r)]
    wrong = [r for r in answered if r["em"] == 0]
    return len(wrong), len(answered), (len(wrong) / len(answered) if answered else 0.0)


def claims(row):
    return [c for hop in (row.get("trace") or [])
            for c in (hop.get("graph") or [])]


def gold_in_claims(row):
    g = norm(row.get("gold", ""))
    return bool(g) and any(g in norm(c.get("text", "")) for c in claims(row))


def main(base_path, ev_path):
    base, ev = load(base_path), load(ev_path)
    ids = sorted(set(base) & set(ev))
    print(f"paired N: {len(ids)} "
          f"(base {len(base)}, evidence-first {len(ev)}, "
          f"failed base {sum(1 for r in base.values() if r.get('failed'))} / "
          f"evidence-first {sum(1 for r in ev.values() if r.get('failed'))})")
    for name, rows in (("base", base), ("evidence-first", ev)):
        rs = [rows[i] for i in ids]
        n = len(rs)
        em = sum(r["em"] for r in rs) / n
        f1 = sum(r["f1"] for r in rs) / n
        calls = sum(r["llm_calls"] for r in rs) / n
        ch = sum(r["cache_hits"] for r in rs) / n
        w, a, wr = wrong_rate(rs)
        wrong_full = [r for r in rs if r["em"] == 0 and not r.get("unknown")
                      and not r.get("abstained") and r.get("recall") == 1.0]
        gic = sum(1 for r in wrong_full if gold_in_claims(r))
        rate = gic / len(wrong_full) if wrong_full else float("nan")
        trig = (sum(1 for r in rs if r.get("evidence_first"))
                if name == "evidence-first" else None)
        extra = f" evidence_first={trig}/{n}" if trig is not None else ""
        print(f"{name}: EM={em:.4f} F1={f1:.4f} calls/Q={calls:.2f} "
              f"cache_hits/Q={ch:.2f} wrong-rate={w}/{a}={wr:.4f} "
              f"full-recall wrong={len(wrong_full)} "
              f"gold-in-claims={gic} rate={rate:.3f}{extra}")
    a_em = [base[i]["em"] for i in ids]
    b_em = [ev[i]["em"] for i in ids]
    print("McNemar (evidence-first vs base):",
          mcnemar_exact([bool(x) for x in a_em], [bool(x) for x in b_em]))
    print("paired bootstrap dEM (evidence-first-base):",
          tuple(round(x, 4) for x in paired_bootstrap(a_em, b_em)))
    print("paired bootstrap dF1 (evidence-first-base):",
          tuple(round(x, 4) for x in paired_bootstrap(
              [base[i]["f1"] for i in ids], [ev[i]["f1"] for i in ids])))
    dcalls = (sum(ev[i]["llm_calls"] for i in ids)
              - sum(base[i]["llm_calls"] for i in ids)) / len(ids)
    print(f"dcalls/Q (evidence-first-base): {dcalls:+.2f}")
    # Fixes vs breaks on rows where the two arms' answers differ
    # (the mechanism applies to every row, so there is no trigger).
    changed = [i for i in ids
               if norm(base[i].get("answer", "")) != norm(ev[i].get("answer", ""))]
    fixed = sum(1 for i in changed if ev[i]["em"] == 1 and base[i]["em"] == 0)
    broke = sum(1 for i in changed if ev[i]["em"] == 0 and base[i]["em"] == 1)
    print(f"changed answers: {len(changed)}/{len(ids)} fixed={fixed} broke={broke}")
    d_em = sum(b_em) / len(b_em) - sum(a_em) / len(a_em)
    _, _, wr_base = wrong_rate([base[i] for i in ids])
    _, _, wr_ev = wrong_rate([ev[i] for i in ids])
    gate = (d_em >= 0.02) and (wr_ev <= wr_base) and (dcalls <= 0.5)
    print(f"GATE: dEM {d_em:+.4f} (need >= +0.02), wrong-rate "
          f"{wr_ev:.4f} vs {wr_base:.4f} (need not up), "
          f"dcalls {dcalls:+.2f} (need <= +0.5) -> "
          f"{'PASS' if gate else 'FAIL'}")
    # Pre-registered extend rule (2026-11-13, before the run): a dEM in
    # the ambiguous band with a 95% CI straddling 0 is underpowered at
    # N=300 — extend to the full Dev-500 instead of calling a verdict.
    _, ci_lo, ci_hi = paired_bootstrap(a_em, b_em)
    ambiguous = (0.01 <= d_em <= 0.04) and (ci_lo <= 0.0 <= ci_hi)
    print(f"EXTEND RULE: dEM 95% CI [{ci_lo:+.4f}, {ci_hi:+.4f}] "
          f"(straddles 0: {ci_lo <= 0.0 <= ci_hi}) -> "
          f"{'AMBIGUOUS — extend A/B to the full Dev-500, do not call a verdict'
             if ambiguous else 'decided on N=300'}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
