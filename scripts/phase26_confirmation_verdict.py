"""Phase 2.5 confirmation verdict: improved system vs fresh IRCoT, Test-400.

Same verdict shape as master plan section 4.2 (Phase 2): primary EM,
paired McNemar exact two-sided, alpha 0.05; plus the H11 wrong-answer
rate and the H10 cost-per-correct-answer legs. Reads stored files only.

Usage:
    .venv/bin/python scripts/phase26_confirmation_verdict.py \\
        results/trueadaptive/erag_trueadaptive_improved_test.jsonl \\
        results/ircot_test_v3_bm25.jsonl
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


def is_unknown_answer(r):
    from src.eval.metrics import normalize_answer as norm
    return norm(r.get("answer", "")) in ("", "unknown")


def main(improved_path, ircot_path):
    imp, irc = load(improved_path), load(ircot_path)
    ids = sorted(set(imp) & set(irc))
    print(f"paired N: {len(ids)} "
          f"(improved {len(imp)}, ircot {len(irc)}, "
          f"failed improved {sum(1 for r in imp.values() if r.get('failed'))} / "
          f"ircot {sum(1 for r in irc.values() if r.get('failed'))})")
    for name, rows in (("improved", imp), ("ircot", irc)):
        rs = [rows[i] for i in ids]
        n = len(rs)
        em = sum(r["em"] for r in rs) / n
        f1 = sum(r["f1"] for r in rs) / n
        calls = sum(r["llm_calls"] for r in rs) / n
        ch = sum(r["cache_hits"] for r in rs) / n
        answered = [r for r in rs if not r.get("abstained")
                    and not is_unknown_answer(r)]
        wrong = [r for r in answered if r["em"] == 0]
        n_correct = sum(r["em"] for r in rs)
        print(f"{name}: EM={em:.4f} F1={f1:.4f} calls/Q={calls:.2f} "
              f"cache_hits/Q={ch:.2f} wrong-rate={len(wrong)}/{len(answered)}"
              f"={len(wrong) / max(len(answered), 1):.4f} "
              f"calls/correct={sum(r['llm_calls'] for r in rs) / max(n_correct, 1):.2f}")
    a_em = [imp[i]["em"] for i in ids]
    b_em = [irc[i]["em"] for i in ids]
    print("McNemar (improved vs ircot):",
          mcnemar_exact([bool(x) for x in a_em], [bool(x) for x in b_em]))
    print("paired bootstrap dEM (improved-ircot):",
          tuple(round(x, 4) for x in paired_bootstrap(a_em, b_em)))
    d_em = sum(a_em) / len(a_em) - sum(b_em) / len(b_em)
    p = mcnemar_exact([bool(x) for x in a_em], [bool(x) for x in b_em])["p"]
    if d_em > 0 and p < 0.05:
        verdict = "WIN (improved beats IRCoT, p<0.05)"
    elif d_em <= 0:
        verdict = "LOSS (improved <= IRCoT)"
    else:
        verdict = "INCONCLUSIVE (improved > IRCoT but p>=0.05)"
    print(f"VERDICT: dEM {d_em:+.4f}, p={p:.4f} -> {verdict}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
