"""Phase 2.6 H16: sweep the NLI verifier thresholds on stored Dev-100 traces.

No live LLM calls: the verifier is a local cross-encoder and its
claim-passage scores are memoized, so the sweep re-runs the exact
production `NLI.verify` call over a threshold grid on stored claims.

Eval: claims from results/trueadaptive/erag_p25_h14_base_dev.jsonl
(tuned + contested Dev-100, all-live), passages reconstructed from the
dev manifest, proxy labels by gold-fact containment. Rows in file order:
first 70 selection, last 30 held out. The 60-pair H2 set is a second
check for the contradicted class (which the manifest cannot label),
never used for selection.

Usage (from the repo root):
    HF_HUB_OFFLINE=1 HF_HUB_DISABLE_XET=1 .venv/bin/python \\
        scripts/sweep_nli_thresholds.py
Output: results/nli_threshold_sweep.json + a printed table.
"""

import json
import re
import sys

sys.path.insert(0, ".")

THETA_S = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
THETA_C = [0.40, 0.50, 0.60, 0.70]
DEV_FILE = "results/trueadaptive/erag_p25_h14_base_dev.jsonl"
MANIFEST = "data/manifests/dev.jsonl"
PAIRS_FILE = "data/nli_eval_pairs.jsonl"
OUT = "results/nli_threshold_sweep.json"
SPLIT = 70  # first 70 rows selection, rest held out


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


def load_rows(path):
    seen = {}
    for line in open(path):
        if line.strip():
            r = json.loads(line)
            seen[r["id"]] = r
    return [seen[k] for k in sorted(seen)]


def main():
    from src.epistemic.nli import NLI

    manifest = {}
    for line in open(MANIFEST):
        if line.strip():
            m = json.loads(line)
            manifest[m["_id"]] = m

    rows = load_rows(DEV_FILE)
    print(f"dev rows: {len(rows)} (selection {SPLIT}, held out {len(rows) - SPLIT})")

    # Collect claims: deduped by normalized text per row; keep the first
    # hop's pool for the passages.
    claims = []  # (row_idx, text, pool_titles, label)
    unresolved_titles = 0
    for ri, r in enumerate(rows):
        m = manifest.get(r["id"])
        if m is None:
            continue
        ctx = {title: sents for title, sents in m.get("context", [])}
        gold_facts = []
        for title, idx in m.get("supporting_facts", []):
            sents = ctx.get(title, [])
            if 0 <= idx < len(sents):
                gold_facts.append(norm(sents[idx]))
        seen_texts = set()
        for hop in r.get("trace") or []:
            pool = hop.get("pool") or []
            for c in hop.get("graph") or []:
                text = c.get("text", "")
                nt = norm(text)
                if not nt or nt in seen_texts or len(nt) < 10:
                    continue
                seen_texts.add(nt)
                label = "supported" if any(
                    (nt in gf or gf in nt) and gf for gf in gold_facts
                ) else "not-supported"
                claims.append((ri, text, pool, label, ctx))
    n_sup = sum(1 for c in claims if c[3] == "supported")
    print(f"claims: {len(claims)} ({n_sup} proxy-supported, "
          f"{len(claims) - n_sup} not-supported)")

    # Resolve pools once per claim (titles -> passage dicts).
    resolved = []
    for ri, text, pool, label, ctx in claims:
        passages = []
        for t in pool:
            if t in ctx:
                passages.append({"title": t, "sentences": ctx[t]})
            else:
                unresolved_titles += 1
        resolved.append((ri, text, passages, label))
    print(f"unresolved pool titles skipped: {unresolved_titles}")

    nli = NLI()
    sel = [c for c in resolved if c[0] < SPLIT]
    held = [c for c in resolved if c[0] >= SPLIT]
    print(f"selection claims: {len(sel)}, held-out claims: {len(held)}")

    def metrics(items, theta_s, theta_c):
        tp = fp = fn = tn = 0
        for _, text, passages, label in items:
            if not passages:
                continue
            st = nli.verify(text, passages, theta_s=theta_s, theta_c=theta_c,
                            pre_filter=True)["status"]
            pred_sup = st == "supported"
            if label == "supported" and pred_sup:
                tp += 1
            elif label == "supported":
                fn += 1
            elif pred_sup:
                fp += 1
            else:
                tn += 1
        rec = tp / (tp + fn) if tp + fn else 0.0
        prec = tp / (tp + fp) if tp + fp else 0.0
        f1_sup = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        rec_ns = tn / (tn + fp) if tn + fp else 0.0
        prec_ns = tn / (tn + fn) if tn + fn else 0.0
        f1_ns = 2 * prec_ns * rec_ns / (prec_ns + rec_ns) if prec_ns + rec_ns else 0.0
        return {
            "supported_recall": round(rec, 4),
            "supported_precision": round(prec, 4),
            "f1_supported": round(f1_sup, 4),
            "macro_f1": round((f1_sup + f1_ns) / 2, 4),
            "pred_supported_frac": round((tp + fp) / max(tp + fp + fn + tn, 1), 4),
            "n": tp + fp + fn + tn,
        }

    # 60-pair H2 set: 3-class check (never used for selection).
    pairs = [json.loads(l) for l in open(PAIRS_FILE) if l.strip()]
    print(f"H2 pairs: {len(pairs)}")

    def pairs_metrics(theta_s, theta_c):
        from sklearn.metrics import f1_score, recall_score
        y_true, y_pred = [], []
        for p in pairs:
            passage = {"title": "", "sentences": p["premise"]}
            st = nli.verify(p["hypothesis"], [passage], theta_s=theta_s,
                            theta_c=theta_c, pre_filter=True)["status"]
            y_true.append(p["gold"])
            y_pred.append(st)
        labels = ["supported", "contradicted", "unresolved"]
        rec = recall_score(y_true, y_pred, labels=labels, average=None,
                           zero_division=0)
        return {
            "macro_f1_3class": round(
                f1_score(y_true, y_pred, labels=labels, average="macro",
                         zero_division=0), 4),
            "supported_recall": round(float(rec[0]), 4),
            "contradicted_recall": round(float(rec[1]), 4),
        }

    grid = []
    for ts in THETA_S:
        for tc in THETA_C:
            sel_m = metrics(sel, ts, tc)
            held_m = metrics(held, ts, tc)
            pm = pairs_metrics(ts, tc)
            row = {"theta_s": ts, "theta_c": tc,
                   "selection": sel_m, "held_out": held_m, "pairs_60": pm}
            grid.append(row)
            print(f"ts={ts:.2f} tc={tc:.2f} | sel macroF1={sel_m['macro_f1']:.4f} "
                  f"supRec={sel_m['supported_recall']:.4f} | held "
                  f"macroF1={held_m['macro_f1']:.4f} "
                  f"supRec={held_m['supported_recall']:.4f} | pairs "
                  f"macroF1={pm['macro_f1_3class']:.4f} "
                  f"conRec={pm['contradicted_recall']:.4f}")

    clearing = [g for g in grid
                if g["held_out"]["macro_f1"] >= 0.70
                and g["held_out"]["supported_recall"] >= 0.70]
    clearing.sort(key=lambda g: (-g["held_out"]["macro_f1"],
                                 -g["held_out"]["supported_recall"]))
    best = clearing[0] if clearing else None
    if best:
        print(f"\nGATE: CLEARING pair theta_s={best['theta_s']} "
              f"theta_c={best['theta_c']} (held-out macroF1="
              f"{best['held_out']['macro_f1']}, supRec="
              f"{best['held_out']['supported_recall']})")
    else:
        best_sel = max(grid, key=lambda g: (g["selection"]["macro_f1"],
                                            g["selection"]["supported_recall"]))
        print("\nGATE: NO pair clears macroF1 >= 0.70 AND supRec >= 0.70 on "
              "held-out claims. Best on selection: "
              f"theta_s={best_sel['theta_s']} theta_c={best_sel['theta_c']} "
              f"(sel macroF1={best_sel['selection']['macro_f1']}, "
              f"held macroF1={best_sel['held_out']['macro_f1']}, "
              f"held supRec={best_sel['held_out']['supported_recall']}). "
              "H16 NOT SUPPORTED on the eval leg; thresholds stay 0.5/0.5.")

    out = {
        "dev_file": DEV_FILE,
        "n_claims": len(claims),
        "n_proxy_supported": n_sup,
        "split_rows": SPLIT,
        "selection_claims": len(sel),
        "held_out_claims": len(held),
        "unresolved_titles_skipped": unresolved_titles,
        "grid": grid,
        "clearing": clearing,
        "best": best,
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
