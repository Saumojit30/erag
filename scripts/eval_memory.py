"""Analyze Verified-Belief Episodic Memory performance and override dynamics (Experiment E5).

Evaluates:
1. Memory Reuse Rate (% of questions utilizing verified prior beliefs)
2. External Retrievals Saved (retrievals_nomem - retrievals_mem)
3. Accuracy & F1 impact (EM, F1 comparison between stream_nomem and stream_mem)
4. Planted Wrong-Belief Overrides (% of synthetic erroneous beliefs detected & purged)
5. False Repetition Avoidance (preventing propagation of obsolete or erroneous beliefs)
"""

import json
import os
import sys
from typing import Any, Dict, List
import numpy as np


def load_run(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def analyze_memory(
    nomem_path: str = "results/stream_nomem.jsonl",
    mem_path: str = "results/stream_mem.jsonl",
    planted_path: str = "results/stream_planted.jsonl",
    plant_def_path: str = "data/manifests/planted.json",
):
    print("=" * 70)
    print("EXPERIMENT E5: VERIFIED-BELIEF EPISODIC MEMORY BENCHMARK")
    print("=" * 70)

    nomem = load_run(nomem_path)
    mem = load_run(mem_path)
    planted = load_run(planted_path)

    if not nomem or not mem:
        print("[!] stream_nomem or stream_mem results not found yet.")
        return

    n = len(mem)
    nomem_em = np.mean([r.get("em", 0.0) for r in nomem])
    mem_em = np.mean([r.get("em", 0.0) for r in mem])
    nomem_f1 = np.mean([r.get("f1", 0.0) for r in nomem])
    mem_f1 = np.mean([r.get("f1", 0.0) for r in mem])

    nomem_ret = np.mean([r.get("retrievals", 1.0) for r in nomem])
    mem_ret = np.mean([r.get("retrievals", 1.0) for r in mem])

    reused = sum(1 for r in mem if r.get("mem_used", False))
    reuse_rate = reused / n if n > 0 else 0.0

    print(f"\n1. Memory Utilization & Efficiency:")
    print(f"   Questions in stream:       {n}")
    print(f"   Memory Reuse Rate:         {reuse_rate * 100:.1f}% ({reused}/{n} questions)")
    print(f"   External Retrievals/Q (No-Mem): {nomem_ret:.2f}")
    print(f"   External Retrievals/Q (Mem):    {mem_ret:.2f}")
    print(f"   Retrieval Reduction:            {((nomem_ret - mem_ret) / max(nomem_ret, 1e-6)) * 100:+.1f}%")

    print(f"\n2. Accuracy Impact:")
    print(f"   EM:  No-Mem = {nomem_em:.4f} | Mem = {mem_em:.4f} (Delta: {mem_em - nomem_em:+.4f})")
    print(f"   F1:  No-Mem = {nomem_f1:.4f} | Mem = {mem_f1:.4f} (Delta: {mem_f1 - nomem_f1:+.4f})")

    if planted and os.path.exists(plant_def_path):
        with open(plant_def_path, "r", encoding="utf-8") as f:
            plant_defs = json.load(f)
        n_planted = len(plant_defs)

        all_overrides = []
        for r in planted:
            for ev in r.get("mem_events", []):
                if ev.get("event") == "overridden":
                    all_overrides.append(ev)

        unique_overridden = set(ev.get("belief", "") for ev in all_overrides)

        print(f"\n3. Planted Wrong-Belief Override Dynamics:")
        print(f"   Synthetic Wrong Beliefs:   {n_planted}")
        print(f"   Total Override Events:     {len(all_overrides)}")
        print(f"   Unique Beliefs Purged:     {len(unique_overridden)} / {n_planted}")
        print(f"   Override Success Rate:     {(len(unique_overridden) / max(n_planted, 1)) * 100:.1f}%")
        print("\n   Override Log:")
        for ev in all_overrides:
            print(f"     [-] Purged: \"{ev.get('belief')}\"")
            print(f"         Contradicted by fresh passage: {ev.get('by')}")

    print("\n" + "=" * 70)


# --- Step 6 (tune-memory-effectiveness): --position section -----------------
# Added for tasks.md A.2. Reports per-arm metrics, the position split
# (early 0-1 / mid 2-3 / late 4-5, from the sidecar), the paired
# mem-vs-nomem difference WITHIN each band, the fired-row paired
# difference, and the planted override rate + false-claim-in-answer
# check (design.md Gate 3). The E5 cache finding is load-bearing here:
# an arm whose live calls/Q is ~0 replayed from cache and must be
# discarded, not analyzed — the section prints that tripwire warning
# instead of letting the numbers pass unnoticed.
# Fields the section reads are fields the runner already writes
# (mem_used, mem_events, llm_calls, cache_hits, retrievals, em, f1,
# answer, gold). mem_store_size / mem_texts come from B.1; on older
# files that lack them the section reports "not recorded", never zero
# (zero would mean "empty store", a different claim).

BANDS = [("early", 0, 1), ("mid", 2, 3), ("late", 4, 5)]


def band_of(position):
    """Position band for a 0-based position within a cluster, or None."""
    if position is None:
        return None
    for name, lo, hi in BANDS:
        if lo <= position <= hi:
            return name
    return None


def dedupe_rows(rows):
    """Deduplicate rows by id, keeping the LAST row per id."""
    seen = {}
    for i, r in enumerate(rows):
        key = r.get("id", f"row-{i}")
        seen[key] = r
    return list(seen.values())


def load_clusters(path):
    """Load the {qid: {cluster, cluster_index, position}} sidecar.

    Returns {} when the file is missing or unreadable; the section then
    reports the position split as unavailable instead of failing.
    """
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {qid: v for qid, v in data.items()
            if isinstance(v, dict) and "position" in v}


def _mean(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return float(sum(vals)) / len(vals)


def _fmt(x, nd=4):
    return f"{x:.{nd}f}" if x is not None else "n/a (not recorded)"


def arm_metrics(rows, clusters):
    """Per-arm metrics for a deduped, non-failed row list.

    `clusters` maps qid -> {"position": ...}; rows whose qid is absent
    from it count in the overall numbers but in no band.
    """
    deduped = dedupe_rows(rows)
    failed = sum(1 for r in deduped if r.get("failed", False))
    rows = [r for r in deduped if not r.get("failed", False)]
    n = len(rows)
    store_sizes = [r["mem_store_size"] for r in rows
                   if "mem_store_size" in r]
    texts_seen = []
    for r in rows:
        for t in r.get("mem_texts", []) or []:
            if t not in texts_seen:
                texts_seen.append(t)
    overrides = sum(1 for r in rows for ev in r.get("mem_events", [])
                    if ev.get("event") == "overridden")
    bands = {}
    for name, lo, hi in BANDS:
        brow = [r for r in rows
                if band_of((clusters.get(r.get("id"), {}) or {})
                           .get("position")) == name]
        bstore = [r["mem_store_size"] for r in brow
                  if "mem_store_size" in r]
        bands[name] = {
            "n": len(brow),
            "em": _mean([r.get("em", 0.0) for r in brow]),
            "calls": _mean([r.get("llm_calls", 0) for r in brow]),
            "live_calls": _mean([r.get("llm_calls", 0)
                                 - r.get("cache_hits", 0) for r in brow]),
            "store_size_mean": _mean(bstore) if bstore else None,
        }
    return {
        "n": n,
        "failed": failed,
        "em": _mean([r.get("em", 0.0) for r in rows]),
        "f1": _mean([r.get("f1", 0.0) for r in rows]),
        "calls": _mean([r.get("llm_calls", 0) for r in rows]),
        "live_calls": _mean([r.get("llm_calls", 0)
                             - r.get("cache_hits", 0) for r in rows]),
        "cache_hits": _mean([r.get("cache_hits", 0) for r in rows]),
        "retrievals": _mean([r.get("retrievals") for r in rows
                             if "retrievals" in r]),
        "fired": sum(1 for r in rows if r.get("mem_used", 0) > 0),
        "fire_rate": (sum(1 for r in rows if r.get("mem_used", 0) > 0) / n
                      if n else 0.0),
        "store_size_mean": _mean(store_sizes) if store_sizes else None,
        "store_texts_seen": texts_seen,
        "overrides": overrides,
        "bands": bands,
    }


def _paired(rows_a, rows_b, clusters, band=None, restrict_fired_b=False):
    """Paired (b - a) EM/calls deltas over ids present in both arms.

    `band` restricts to ids whose sidecar position falls in that band;
    `restrict_fired_b` restricts to ids where the b-arm row fired
    (mem_used > 0). Returns {"n", "d_em", "d_calls", "ids"}.
    """
    a = {r.get("id"): r for r in dedupe_rows(rows_a)
         if not r.get("failed", False)}
    b = {r.get("id"): r for r in dedupe_rows(rows_b)
         if not r.get("failed", False)}
    ids = []
    for qid in b:
        if qid not in a:
            continue
        if restrict_fired_b and not b[qid].get("mem_used", 0) > 0:
            continue
        if band is not None:
            pos = (clusters.get(qid, {}) or {}).get("position")
            if band_of(pos) != band:
                continue
        ids.append(qid)
    if not ids:
        return {"n": 0, "d_em": None, "d_calls": None, "ids": []}
    d_em = float(np.mean([b[q].get("em", 0.0) - a[q].get("em", 0.0)
                          for q in ids]))
    d_calls = float(np.mean([b[q].get("llm_calls", 0)
                             - a[q].get("llm_calls", 0) for q in ids]))
    return {"n": len(ids), "d_em": d_em, "d_calls": d_calls, "ids": ids}


def paired_delta(nomem_rows, mem_rows, clusters):
    """Paired mem-vs-nomem deltas overall and WITHIN each position band."""
    out = {"overall": _paired(nomem_rows, mem_rows, clusters),
           "bands": {}}
    for name, _, _ in BANDS:
        out["bands"][name] = _paired(nomem_rows, mem_rows, clusters,
                                     band=name)
    return out


def fired_row_paired(nomem_rows, mem_rows, clusters):
    """Paired mem-vs-nomem deltas restricted to rows where mem fired."""
    res = _paired(nomem_rows, mem_rows, clusters, restrict_fired_b=True)
    return {"n_fired": res["n"], "d_em": res["d_em"],
            "d_calls": res["d_calls"], "ids": res["ids"]}


def _norm_text(s):
    import re
    return re.sub(r"[^a-z0-9 ]+", " ", str(s).lower()).strip()


def planted_stats(planted_rows, plant_defs):
    """Override rate among retrieved planted beliefs + false-claim check.

    A planted belief counts as retrieved if it was returned as a memory
    passage (appears in some row's mem_texts) or was overridden (an
    override event means it was retrieved, then deleted). A planted-arm
    final answer counts as a false claim if its normalized text is a
    planted belief's normalized text, or a substring of it (length >= 3,
    so short answers like "no" cannot false-positive) — EXCEPT when the
    answer is the target entity itself: an answer naming the entity
    ("Paul Hindemith") does not assert the false detail, so answers
    that are a substring of the belief's target_entity are skipped.
    "unknown" answers are skipped. Returns the counts plus the
    offending rows, if any.
    """
    planted_texts = [d.get("text", "") for d in plant_defs]
    planted_set = set(planted_texts)
    entities = {d.get("text", ""): _norm_text(d.get("target_entity", ""))
                for d in plant_defs}
    retrieved = set()
    overridden = set()
    for r in dedupe_rows(planted_rows):
        if r.get("failed", False):
            continue
        for ev in r.get("mem_events", []):
            if ev.get("event") == "overridden" and ev.get("belief"):
                overridden.add(ev["belief"])
                retrieved.add(ev["belief"])
        for t in r.get("mem_texts", []) or []:
            if t in planted_set:
                retrieved.add(t)
    overridden_planted = sorted(b for b in overridden if b in planted_set)
    false_claim_answers = []
    for r in dedupe_rows(planted_rows):
        if r.get("failed", False):
            continue
        ans = _norm_text(r.get("answer", ""))
        if not ans or ans == "unknown" or len(ans) < 3:
            continue
        for belief in planted_texts:
            bnorm = _norm_text(belief)
            if ans == bnorm or ans in bnorm:
                # Naming the entity is not asserting the false detail.
                entity = entities.get(belief, "")
                if entity and (ans == entity or ans in entity):
                    continue
                false_claim_answers.append(
                    {"id": r.get("id"), "answer": r.get("answer"),
                     "belief": belief})
                break
    n_retrieved = len(retrieved)
    return {
        "n_planted": len(plant_defs),
        "n_retrieved": n_retrieved,
        "n_overridden": len(overridden_planted),
        "overridden_beliefs": overridden_planted,
        "override_rate_retrieved": (
            len(overridden_planted) / n_retrieved if n_retrieved else None),
        "override_rate_planted": (
            len(overridden_planted) / len(plant_defs) if plant_defs else None),
        "false_claim_answers": false_claim_answers,
    }


def position_section(nomem_path, mem_path, planted_path, clusters,
                     plant_def_path="data/manifests/planted.json"):
    """--position section: print the report and return the numbers.

    `clusters` is either the sidecar dict or its path. Returns a dict
    with per-arm metrics, per-band splits, paired deltas, fired-row
    paired deltas, fired qids, and planted stats (for tests and for
    the gate), and prints the same numbers for the record.
    """
    if isinstance(clusters, str):
        clusters = load_clusters(clusters)
    nomem = load_run(nomem_path)
    mem = load_run(mem_path)
    planted = load_run(planted_path)
    plant_defs = []
    if plant_def_path and os.path.exists(plant_def_path):
        with open(plant_def_path, "r", encoding="utf-8") as f:
            plant_defs = json.load(f)

    m_nomem = arm_metrics(nomem, clusters)
    m_mem = arm_metrics(mem, clusters)
    m_planted = arm_metrics(planted, clusters) if planted else None
    paired = paired_delta(nomem, mem, clusters)
    fired = fired_row_paired(nomem, mem, clusters)
    fired_qids = fired["ids"]
    pstats = planted_stats(planted, plant_defs) if planted else None
    bands = {}
    for name, _, _ in BANDS:
        bands[name] = {
            "n": m_nomem["bands"][name]["n"],
            "nomem_em": m_nomem["bands"][name]["em"],
            "nomem_calls": m_nomem["bands"][name]["calls"],
            "mem_em": m_mem["bands"][name]["em"],
            "mem_calls": m_mem["bands"][name]["calls"],
            "d_em": paired["bands"][name]["d_em"],
            "d_calls": paired["bands"][name]["d_calls"],
        }

    print("=" * 70)
    print("MEMORY EFFECTIVENESS BY POSITION (--position, step 6)")
    print("=" * 70)
    for label, m in (("nomem", m_nomem), ("mem", m_mem)):
        print(f"\n[{label}] n={m['n']} EM={_fmt(m['em'])} F1={_fmt(m['f1'])} "
              f"calls/Q={_fmt(m['calls'], 2)} live calls/Q="
              f"{_fmt(m['live_calls'], 2)} cache_hits/Q="
              f"{_fmt(m['cache_hits'], 2)} retrievals/Q="
              f"{_fmt(m['retrievals'], 2)} fired={m['fired']} "
              f"({m['fire_rate'] * 100:.1f}%) store_size="
              f"{_fmt(m['store_size_mean'], 2)} overrides={m['overrides']}")
        if m["calls"] and (m["live_calls"] or 0) < 0.05 * m["calls"]:
            print(f"   [!] TRIPWIRE: {label} live calls/Q is ~0 while "
                  f"calls/Q is {m['calls']:.2f} — this arm replayed "
                  f"from cache; discard it, do not analyze it.")
    if m_planted is not None:
        print(f"\n[planted] n={m_planted['n']} EM={_fmt(m_planted['em'])} "
              f"F1={_fmt(m_planted['f1'])} calls/Q="
              f"{_fmt(m_planted['calls'], 2)} live calls/Q="
              f"{_fmt(m_planted['live_calls'], 2)} cache_hits/Q="
              f"{_fmt(m_planted['cache_hits'], 2)} fired="
              f"{m_planted['fired']} overrides={m_planted['overrides']}")
        if m_planted["calls"] and (m_planted["live_calls"] or 0) < \
                0.05 * m_planted["calls"]:
            print("   [!] TRIPWIRE: planted live calls/Q is ~0 — "
                  "this arm replayed from cache; discard it, "
                  "do not analyze it.")
    print("\nPosition split (paired mem-vs-nomem WITHIN each band):")
    for name, _, _ in BANDS:
        b = bands[name]
        print(f"   {name:5s} n={b['n']:2d} nomem EM={_fmt(b['nomem_em'])} "
              f"calls={_fmt(b['nomem_calls'], 2)} | mem EM="
              f"{_fmt(b['mem_em'])} calls={_fmt(b['mem_calls'], 2)} | "
              f"dEM={_fmt(b['d_em'])} dCalls={_fmt(b['d_calls'], 2)}")
    print(f"\nFired-row paired difference (mem fired on {fired['n_fired']} rows): "
          f"dEM={_fmt(fired['d_em'])} dCalls={_fmt(fired['d_calls'], 2)}")
    if pstats is not None:
        print(f"\nPlanted override (Gate 3): {pstats['n_overridden']} unique "
              f"beliefs overridden / {pstats['n_planted']} planted; "
              f"{pstats['n_retrieved']} retrieved; override rate among "
              f"retrieved = "
              f"{_fmt(pstats['override_rate_retrieved'], 2)}")
        for b in pstats["overridden_beliefs"]:
            print(f"   [-] Purged: \"{b}\"")
        if pstats["false_claim_answers"]:
            print("   [!] FALSE-CLAIM ANSWERS (planted-arm final answer "
                  "equals a planted false claim):")
            for v in pstats["false_claim_answers"]:
                print(f"       {v['id']}: {v['answer']!r} in "
                      f"{v['belief']!r}")
        else:
            print("   False-claim-in-answer check: 0 violations.")
    print("=" * 70)
    return {
        "nomem": m_nomem, "mem": m_mem, "planted": m_planted,
        "bands": bands, "paired": paired, "fired_paired": fired,
        "fired_qids": fired_qids, "planted_stats": pstats,
    }


def _main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Analyze Verified-Belief Episodic Memory (E5 / step 6)")
    ap.add_argument("--position", action="store_true",
                    help="print the --position section (step 6)")
    ap.add_argument("--nomem", default="results/stream_nomem.jsonl",
                    help="nomem arm run file")
    ap.add_argument("--mem", default="results/stream_mem.jsonl",
                    help="mem arm run file")
    ap.add_argument("--planted", default="results/stream_planted.jsonl",
                    help="planted arm run file")
    ap.add_argument("--clusters",
                    default="data/manifests/stream_clusters.json",
                    help="sidecar {qid: {cluster, cluster_index, position}}")
    ap.add_argument("--plant-defs", default="data/manifests/planted.json",
                    help="planted belief definitions (JSON array)")
    args = ap.parse_args()
    if args.position:
        position_section(args.nomem, args.mem, args.planted,
                         args.clusters, args.plant_defs)
    else:
        analyze_memory()



if __name__ == "__main__":
    _main()
