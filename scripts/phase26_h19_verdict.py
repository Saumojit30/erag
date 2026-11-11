"""Phase 2.7 H19 verdict: extractive final read vs improved-system baseline.

Dev-100 BM25 A/B, both arms re-run fresh, paired on question id,
deduped keeping the last row per id. Gate (pre-registered 2026-11-11):
dEM >= +0.02 AND wrong-answer rate not up AND dcalls <= +0.5.

Usage:
    .venv/bin/python scripts/phase26_h19_verdict.py \\
        results/trueadaptive/erag_p27_h19_base_dev.jsonl \\
        results/trueadaptive/erag_p27_h19_extractive_dev.jsonl
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


def main(base_path, ext_path):
    base, ext = load(base_path), load(ext_path)
    ids = sorted(set(base) & set(ext))
    print(f"paired N: {len(ids)} "
          f"(base {len(base)}, extractive {len(ext)}, "
          f"failed base {sum(1 for r in base.values() if r.get('failed'))} / "
          f"extractive {sum(1 for r in ext.values() if r.get('failed'))})")
    for name, rows in (("base", base), ("extractive", ext)):
        rs = [rows[i] for i in ids]
        n = len(rs)
        em = sum(r["em"] for r in rs) / n
        f1 = sum(r["f1"] for r in rs) / n
        calls = sum(r["llm_calls"] for r in rs) / n
        ch = sum(r["cache_hits"] for r in rs) / n
        w, a, wr = wrong_rate(rs)
        trig = sum(1 for r in rs if r.get("extractive")) if name == "extractive" else None
        extra = f" trigger={trig}/{n}" if trig is not None else ""
        print(f"{name}: EM={em:.4f} F1={f1:.4f} calls/Q={calls:.2f} "
              f"cache_hits/Q={ch:.2f} wrong-rate={w}/{a}={wr:.4f}{extra}")
    a_em = [base[i]["em"] for i in ids]
    b_em = [ext[i]["em"] for i in ids]
    print("McNemar (extractive vs base):",
          mcnemar_exact([bool(x) for x in a_em], [bool(x) for x in b_em]))
    print("paired bootstrap dEM (extractive-base):",
          tuple(round(x, 4) for x in paired_bootstrap(a_em, b_em)))
    print("paired bootstrap dF1 (extractive-base):",
          tuple(round(x, 4) for x in paired_bootstrap(
              [base[i]["f1"] for i in ids], [ext[i]["f1"] for i in ids])))
    dcalls = (sum(ext[i]["llm_calls"] for i in ids)
              - sum(base[i]["llm_calls"] for i in ids)) / len(ids)
    print(f"dcalls/Q (extractive-base): {dcalls:+.2f}")
    # Fixes vs breaks on triggered rows (extractive arm only).
    trig_ids = [i for i in ids if ext[i].get("extractive")]
    fixed = sum(1 for i in trig_ids if ext[i]["em"] == 1 and base[i]["em"] == 0)
    broke = sum(1 for i in trig_ids if ext[i]["em"] == 0 and base[i]["em"] == 1)
    print(f"triggered rows: {len(trig_ids)}/{len(ids)} fixed={fixed} broke={broke}")
    d_em = sum(b_em) / len(b_em) - sum(a_em) / len(a_em)
    _, _, wr_base = wrong_rate([base[i] for i in ids])
    _, _, wr_ext = wrong_rate([ext[i] for i in ids])
    gate = (d_em >= 0.02) and (wr_ext <= wr_base) and (dcalls <= 0.5)
    print(f"GATE: dEM {d_em:+.4f} (need >= +0.02), wrong-rate "
          f"{wr_ext:.4f} vs {wr_base:.4f} (need not up), "
          f"dcalls {dcalls:+.2f} (need <= +0.5) -> "
          f"{'PASS' if gate else 'FAIL'}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
