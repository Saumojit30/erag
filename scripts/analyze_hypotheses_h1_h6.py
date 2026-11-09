"""H1-H6 hypothesis assessment from stored results (no live calls).

Computes, from files already on disk:
  H1: TrueAdaptive vs Standard (BM25, Test-400) paired bootstrap CI for
      dEM and dF1 (TA - Standard), McNemar exact. Balanced vs Standard
      as context. (Holm across H1/H4 is pending H4's Test-400 p-value.)
  H3: AUROC of self-consistency confidence (c0) vs correctness, with
      bootstrap CI, for TrueAdaptive (Test-400) + Reference/Balanced context.
  H5: Formal E5 assessment from the stream files (mem vs nomem vs planted).
  H6: TA gain vs IRCoT (and vs Standard), split by hop-0 retrieval
      completeness (hop-0 pool recall from trace[0] pool vs manifest gold
      titles). TA vs IRCoT is the primary H6 comparison (the report's H6
      is about E-RAG's gain over a baseline; IRCoT is the multi-hop baseline).
  H4 (dev interim only): full E-RAG Active vs no-adaptive ablation on
      Dev-100, paired bootstrap CI for dF1/dEM + McNemar, and wall-latency
      ratios. The Test-400 ablation has NOT run (needs a Groq key).

H2 is NOT in this script: it needs a labelled NLI pair set, built and run
separately (see data/nli_eval_pairs.jsonl / results/nli_eval_h2.jsonl).

Conventions (repo discipline): dedupe result rows by id keeping the LAST
row (resume-retried questions leave a stale failed row); EM/F1 from the
repo's exact_match/f1_score are already stored per row, so use stored
values; paired comparisons use identical id ordering; bootstrap seed fixed.

Usage: .venv/bin/python scripts/analyze_hypotheses_h1_h6.py
Writes: results/hypotheses_h1_h6.json (machine-readable) and prints a
human-readable summary to stdout.
"""

import json
import sys
from pathlib import Path
from statistics import mean

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.eval.metrics import auroc, brier, ece_by_level  # noqa: E402
from src.eval.stats import bootstrap_ci, mcnemar_exact, paired_bootstrap  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
N_BOOT = 10000
N_BOOT_AUROC = 2000
SEED = 0


def load_dedup(path):
    """Load a JSONL results file, deduping by id keeping the LAST row."""
    rows = {}
    n_lines = 0
    for line in open(path):
        if not line.strip():
            continue
        n_lines += 1
        r = json.loads(line)
        rows[r["id"]] = r
    return rows, n_lines


def paired(rows_a, rows_b):
    """Return (ids, a_rows, b_rows) over the shared ids, sorted by id."""
    ids = sorted(set(rows_a) & set(rows_b))
    return ids, [rows_a[i] for i in ids], [rows_b[i] for i in ids]


def auroc_ci(conf, correct, n=N_BOOT_AUROC, seed=SEED):
    """Bootstrap 95% CI for AUROC by resampling (conf, correct) pairs."""
    conf = np.asarray(conf, dtype=float)
    correct = np.asarray(correct, dtype=int)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        idx = rng.integers(0, len(conf), size=len(conf))
        c, y = conf[idx], correct[idx]
        if len(set(y.tolist())) < 2:
            continue
        try:
            vals.append(auroc(c.tolist(), y.tolist()))
        except Exception:
            continue
    vals = np.asarray(vals)
    return float(auroc(conf.tolist(), correct.tolist())), float(
        np.quantile(vals, 0.025)
    ), float(np.quantile(vals, 0.975))


def main():
    out = {}

    # ---------------------------------------------------------------- H1
    ta, ta_lines = load_dedup(ROOT / "results/trueadaptive/erag_trueadaptive_test_bm25.jsonl")
    std, _ = load_dedup(ROOT / "results/bm25/standard_bm25_test.jsonl")
    irc, _ = load_dedup(ROOT / "results/ircot_test_bm25.jsonl")
    bal, _ = load_dedup(ROOT / "results/bm25/erag_balanced_bm25_test.jsonl")
    print(f"TA rows: {len(ta)} (from {ta_lines} lines); STD-BM25: {len(std)}; "
          f"IRCoT: {len(irc)}; BAL-BM25: {len(bal)}")
    ids, ta_r, std_r = paired(ta, std)
    assert len(ids) == 400, f"expected 400 paired ids, got {len(ids)}"
    ta_em = [r["em"] for r in ta_r]
    std_em = [r["em"] for r in std_r]
    ta_f1 = [r["f1"] for r in ta_r]
    std_f1 = [r["f1"] for r in std_r]
    d_em = paired_bootstrap(std_em, ta_em, n=N_BOOT, seed=SEED)
    d_f1 = paired_bootstrap(std_f1, ta_f1, n=N_BOOT, seed=SEED)
    mc = mcnemar_exact(
        [bool(r["em"]) for r in ta_r], [bool(r["em"]) for r in std_r]
    )
    h1 = {
        "n": len(ids),
        "ta_em": mean(ta_em),
        "std_em": mean(std_em),
        "ta_f1": mean(ta_f1),
        "std_f1": mean(std_f1),
        "d_em_mean_lo_hi": d_em,
        "d_f1_mean_lo_hi": d_f1,
        "mcnemar": mc,
        "caveat": (
            "Standard-BM25 rows carry no row-level 'retriever' field "
            "(pre-provenance file); BM25 is established by the file's location "
            "in results/bm25/ and the audit record. Paired by question id "
            "(400/400). This is the v1 TrueAdaptive system, not the final "
            "tuned system: the confirmatory H1 should be re-run on the "
            "frozen tuned system at Phase 2. Holm correction is pending "
            "H4's Test-400 p-value (no Test-400 ablation run exists yet)."
        ),
    }
    out["H1"] = h1
    print(f"H1 TA vs STD-BM25: dEM={d_em[0]:.4f} 95% CI "
          f"[{d_em[1]:.4f}, {d_em[2]:.4f}], dF1={d_f1[0]:.4f} 95% CI "
          f"[{d_f1[1]:.4f}, {d_f1[2]:.4f}], McNemar b={mc['b_only']} "
          f"c={mc['a_only']} p={mc['p']:.4g}")

    # H1 context: Balanced vs Standard
    _, bal_r, std_r2 = paired(bal, std)
    d_em_b = paired_bootstrap(
        [r["em"] for r in std_r2], [r["em"] for r in bal_r], n=N_BOOT, seed=SEED
    )
    d_f1_b = paired_bootstrap(
        [r["f1"] for r in std_r2], [r["f1"] for r in bal_r], n=N_BOOT, seed=SEED
    )
    out["H1_context_balanced"] = {"d_em": d_em_b, "d_f1": d_f1_b}
    print(f"H1 ctx BAL vs STD-BM25: dEM={d_em_b[0]:.4f} "
          f"[{d_em_b[1]:.4f}, {d_em_b[2]:.4f}], dF1={d_f1_b[0]:.4f} "
          f"[{d_f1_b[1]:.4f}, {d_f1_b[2]:.4f}]")

    # ---------------------------------------------------------------- H3
    h3 = {}
    for name, rows in [("trueadaptive", ta), ("balanced_bm25", bal)]:
        ok = [r for r in rows.values() if not r.get("failed")]
        conf = [r["c0"] for r in ok]
        corr = [int(r["em"]) for r in ok]
        a, lo, hi = auroc_ci(conf, corr)
        ece, _ = ece_by_level(conf, corr)
        br = brier(conf, corr)
        # answer_conf AUROC for comparison: the older cost CSV reported
        # higher AUROCs (e.g. Reference 0.7368); those used answer_conf
        # (final confidence), not c0 (initial self-consistency). H3 is
        # about self-consistency, so c0 is the correct field; report both
        # so the discrepancy is explained, not hidden.
        a_ac, lo_ac, hi_ac = auroc_ci(
            [r["answer_conf"] for r in ok], corr
        )
        h3[name] = {
            "n": len(ok),
            "auroc_c0": a,
            "auroc_c0_ci95": [lo, hi],
            "auroc_answer_conf": a_ac,
            "auroc_answer_conf_ci95": [lo_ac, hi_ac],
            "ece": ece,
            "brier": br,
        }
        print(f"H3 {name}: AUROC(c0)={a:.4f} 95% CI [{lo:.4f}, {hi:.4f}] "
              f"AUROC(answer_conf)={a_ac:.4f} [{lo_ac:.4f}, {hi_ac:.4f}] "
              f"ECE={ece:.4f} Brier={br:.4f} (n={len(ok)})")
    # Reference Test-400 for context (file has c0)
    ref, _ = load_dedup(ROOT / "results/erag_active_test.jsonl")
    ok = [r for r in ref.values() if not r.get("failed")]
    a, lo, hi = auroc_ci([r["c0"] for r in ok], [int(r["em"]) for r in ok])
    a_ac, lo_ac, hi_ac = auroc_ci(
        [r["answer_conf"] for r in ok], [int(r["em"]) for r in ok]
    )
    h3["reference"] = {
        "n": len(ok),
        "auroc_c0": a,
        "auroc_c0_ci95": [lo, hi],
        "auroc_answer_conf": a_ac,
        "auroc_answer_conf_ci95": [lo_ac, hi_ac],
    }
    print(f"H3 reference: AUROC(c0)={a:.4f} 95% CI [{lo:.4f}, {hi:.4f}] "
          f"AUROC(answer_conf)={a_ac:.4f} [{lo_ac:.4f}, {hi_ac:.4f}] "
          f"(n={len(ok)})")
    out["H3"] = h3

    # ---------------------------------------------------------------- H6
    # Hop-0 retrieval completeness: gold titles from the test manifest,
    # hop-0 pool titles from trace[0]['pool'].
    manifest = {}
    for line in open(ROOT / "data/manifests/test.jsonl"):
        if line.strip():
            item = json.loads(line)
            manifest[item["_id"]] = item
    hop0_recall = {}
    for qid, r in ta.items():
        item = manifest[qid]
        gold_titles = {t for t, _ in item["supporting_facts"]}
        hop0 = next(
            (t for t in (r.get("trace") or []) if t.get("hop") == 0), None
        )
        pool0 = set(hop0["pool"]) if hop0 else set()
        hop0_recall[qid] = (
            len(gold_titles & pool0) / len(gold_titles) if gold_titles else 0.0
        )
    ids_all, ta_all, ir_all = paired(ta, irc)
    _, _, std_all = paired(ta, std)
    ta_by_id = {r["id"]: r for r in ta_all}
    ir_by_id = {r["id"]: r for r in ir_all}
    std_by_id = {r["id"]: r for r in std_all}
    h6 = {}
    for label, pred in [
        ("hop0_complete_recall_1.0", lambda q: hop0_recall[q] == 1.0),
        ("hop0_incomplete_recall_lt_1.0", lambda q: hop0_recall[q] < 1.0),
    ]:
        sub = [q for q in ids_all if pred(q)]
        ta_em_s = [ta_by_id[q]["em"] for q in sub]
        ir_em_s = [ir_by_id[q]["em"] for q in sub]
        std_em_s = [std_by_id[q]["em"] for q in sub]
        ta_f1_s = [ta_by_id[q]["f1"] for q in sub]
        ir_f1_s = [ir_by_id[q]["f1"] for q in sub]
        d_em = paired_bootstrap(ir_em_s, ta_em_s, n=N_BOOT, seed=SEED)
        d_f1 = paired_bootstrap(ir_f1_s, ta_f1_s, n=N_BOOT, seed=SEED)
        mc = mcnemar_exact(
            [bool(x) for x in ta_em_s], [bool(x) for x in ir_em_s]
        )
        h6[label] = {
            "n": len(sub),
            "ta_em": mean(ta_em_s),
            "ircot_em": mean(ir_em_s),
            "std_em": mean(std_em_s),
            "ta_f1": mean(ta_f1_s),
            "ircot_f1": mean(ir_f1_s),
            "d_em_ta_minus_ircot": d_em,
            "d_f1_ta_minus_ircot": d_f1,
            "mcnemar_ta_vs_ircot": mc,
        }
        print(f"H6 {label} (n={len(sub)}): TA EM={mean(ta_em_s):.4f} "
              f"IRCoT EM={mean(ir_em_s):.4f} dEM={d_em[0]:.4f} "
              f"[{d_em[1]:.4f}, {d_em[2]:.4f}] p={mc['p']:.4g}")
    out["H6"] = h6

    # ---------------------------------------------------------------- H5
    def load_list(path):
        return [
            json.loads(l) for l in open(path) if l.strip()
        ]

    mem = load_list(ROOT / "results/stream_mem.jsonl")
    nomem = load_list(ROOT / "results/stream_nomem.jsonl")
    planted = load_list(ROOT / "results/stream_planted.jsonl")
    # planted.json is a JSON array (not JSONL).
    planted_defs = json.load(open(ROOT / "data/manifests/planted.json"))

    def stream_stats(rows):
        ok = [r for r in rows if not r.get("failed")]
        return {
            "n": len(ok),
            "em": mean(r["em"] for r in ok),
            "f1": mean(r["f1"] for r in ok),
            "calls": mean(r["llm_calls"] for r in ok),
            "retrievals": mean(r["retrievals"] for r in ok)
            if ok and "retrievals" in ok[0]
            else None,
            "mem_used_rows": sum(1 for r in ok if r.get("mem_used", 0) > 0),
        }

    mem_s, nomem_s, planted_s = (
        stream_stats(mem),
        stream_stats(nomem),
        stream_stats(planted),
    )
    overridden = sum(
        1
        for r in planted
        for e in (r.get("mem_events") or [])
        if e.get("event") == "overridden"
    )
    used_no_override = [
        r["id"]
        for r in planted
        if r.get("mem_used", 0) > 0
        and not any(
            e.get("event") == "overridden"
            for e in (r.get("mem_events") or [])
        )
    ]
    # Identify the used memory passages: memory.py stores them in the pool
    # with title "memory". Report their texts so the used-but-not-overridden
    # belief can be named (otherwise its identity is not recorded in the row).
    def memory_texts(row):
        texts = []
        for t in row.get("trace") or []:
            for p in t.get("pool") or []:
                if isinstance(p, dict) and p.get("title") == "memory":
                    texts.append(p.get("text", ""))
                elif isinstance(p, dict) and p.get("is_memory"):
                    texts.append(p.get("text", ""))
        return texts

    used_beliefs = {}
    for r in planted:
        if r.get("mem_used", 0) > 0:
            used_beliefs[r["id"]] = {
                "em": r["em"],
                "memory_texts": memory_texts(r),
                "events": r.get("mem_events") or [],
            }
    h5 = {
        "mem": mem_s,
        "nomem": nomem_s,
        "planted": planted_s,
        "d_em_mem_minus_nomem": mem_s["em"] - nomem_s["em"],
        "calls_saved_per_q": nomem_s["calls"] - mem_s["calls"],
        "retrievals_saved_per_q": (
            (nomem_s["retrievals"] - mem_s["retrievals"])
            if mem_s["retrievals"] is not None
            else None
        ),
        "planted_beliefs": len(planted_defs),
        "overridden_events": overridden,
        "override_rate": overridden / len(planted_defs) if planted_defs else None,
        "used_without_override_ids": used_no_override,
        "used_beliefs": used_beliefs,
        "planted_belief_texts": [b.get("text") for b in planted_defs],
        "note": (
            "Override rate counts overridden EVENTS over planted beliefs; "
            "beliefs never retrieved cannot be overridden. A used-but-not-"
            "overridden belief passed NLI verification and entered the pool."
        ),
    }
    out["H5"] = h5
    print(f"H5 mem EM={mem_s['em']:.4f} vs nomem {nomem_s['em']:.4f} "
          f"(dEM={h5['d_em_mem_minus_nomem']:+.4f}); calls "
          f"{mem_s['calls']:.2f} vs {nomem_s['calls']:.2f} "
          f"(saved {h5['calls_saved_per_q']:+.2f}/Q); override "
          f"{overridden}/{len(planted_defs)} planted")

    # ------------------------------------------------- H4 (dev interim)
    full_dev, _ = load_dedup(ROOT / "results/erag_active_dev.jsonl")
    noad_dev, _ = load_dedup(ROOT / "results/erag_ablate_no_adaptive_dev.jsonl")
    std_dev, _ = load_dedup(ROOT / "results/standard_dev.jsonl")
    ids_d, full_r, noad_r = paired(full_dev, noad_dev)
    d_em_d = paired_bootstrap(
        [r["em"] for r in noad_r], [r["em"] for r in full_r],
        n=N_BOOT, seed=SEED,
    )
    d_f1_d = paired_bootstrap(
        [r["f1"] for r in noad_r], [r["f1"] for r in full_r],
        n=N_BOOT, seed=SEED,
    )
    mc_d = mcnemar_exact(
        [bool(r["em"]) for r in full_r], [bool(r["em"]) for r in noad_r]
    )
    lat = {}
    for nm, rows in [
        ("full_active_dev", full_r),
        ("no_adaptive_dev", noad_r),
        ("standard_dev", [std_dev[i] for i in ids_d if i in std_dev]),
    ]:
        ok = [r for r in rows if not r.get("failed")]
        lat[nm] = {
            "mean_wall_latency_s": mean(r.get("wall_latency") or 0 for r in ok),
            "mean_calls": mean(r["llm_calls"] for r in ok),
        }
    h4 = {
        "dev_interim": {
            "n": len(ids_d),
            "full_em": mean(r["em"] for r in full_r),
            "noad_em": mean(r["em"] for r in noad_r),
            "full_f1": mean(r["f1"] for r in full_r),
            "noad_f1": mean(r["f1"] for r in noad_r),
            "d_em_full_minus_noad": d_em_d,
            "d_f1_full_minus_noad": d_f1_d,
            "mcnemar": mc_d,
            "latency": lat,
            "latency_ratio_full_vs_standard_wall": (
                lat["full_active_dev"]["mean_wall_latency_s"]
                / lat["standard_dev"]["mean_wall_latency_s"]
                if lat["standard_dev"]["mean_wall_latency_s"]
                else None
            ),
            "caveat": (
                "Dev-100 only (N=100, ~+/-10pt noise); this is an INTERIM, "
                "not the confirmatory H4, which needs the Test-400 "
                "no-adaptive ablation run (not run; needs a Groq key). "
                "Wall latencies are confounded by cache state: Standard dev "
                "is heavily cache-replayed, so its wall latency is not a "
                "cache-off baseline. The 3x latency bound in H4 was a "
                "proposed limit, never confirmed; any multi-call system is "
                "far above 3x a 1-call cached Standard on wall latency."
            ),
        }
    }
    out["H4"] = h4
    print(f"H4 dev interim: dF1={d_f1_d[0]:.4f} "
          f"[{d_f1_d[1]:.4f}, {d_f1_d[2]:.4f}] dEM={d_em_d[0]:.4f} "
          f"[{d_em_d[1]:.4f}, {d_em_d[2]:.4f}] p={mc_d['p']:.4g}; "
          f"wall full={lat['full_active_dev']['mean_wall_latency_s']:.2f}s "
          f"noad={lat['no_adaptive_dev']['mean_wall_latency_s']:.2f}s "
          f"std={lat['standard_dev']['mean_wall_latency_s']:.2f}s")

    with open(ROOT / "results/hypotheses_h1_h6.json", "w") as f:
        json.dump(out, f, indent=2)
    print("Wrote results/hypotheses_h1_h6.json")


if __name__ == "__main__":
    main()
