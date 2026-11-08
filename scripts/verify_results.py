"""Verify ERag headline results by recomputation from the raw files.

Recomputes every headline number from the raw results files, checks the
data-manifest SHAs, and checks the LLM cache has no empty-text rows.
Writes a human-readable report (default docs/verification-report.md) and
exits non-zero on any mismatch.

Usage:
    .venv/bin/python scripts/verify_results.py [--report PATH]

No key, no network, read-only (the cache is opened read-only). Run it after
any change to results files, benchmark CSVs, or the manifest.
"""

import argparse
import csv
import hashlib
import json
import math
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from statistics import mean

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Groq rates for openai/gpt-oss-20b, the actual generator (audit H1).
# $0.10 input / $0.20 output per 1M tokens.
RATE_IN_PER_1M = 0.10
RATE_OUT_PER_1M = 0.20

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def dedupe_keep_last(rows):
    """Collapse resume duplicates: keep the last row per question id."""
    seen = {}
    for r in rows:
        seen[r["id"]] = r
    return list(seen.values())


def mean_or_nan(values):
    return float(mean(values)) if values else float("nan")


def close(got, want, tol):
    return abs(got - want) <= tol


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit():
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True, cwd=ROOT,
        ).stdout.strip()
    except Exception:
        return "untracked"


# ---------------------------------------------------------------------------
# checks: each returns (name, passed, detail)
# ---------------------------------------------------------------------------

# (system label in CSV, retriever label in CSV, enriched results file)
PHASE5_CELLS = [
    ("Standard RAG", "BGE-base-en-v1.5 (Dense)", "standard_bge_test.jsonl"),
    ("Standard RAG", "BM25 (Sparse)", "standard_bm25_test.jsonl"),
    ("Standard RAG", "E5-base-v2 (Dense)", "standard_e5_test.jsonl"),
    ("Standard RAG", "MiniLM (Dense)", "standard_minilm_test.jsonl"),
    ("IRCoT", "BGE-base-en-v1.5 (Dense)", "ircot_bge_test.jsonl"),
    ("IRCoT", "BM25 (Sparse)", "ircot_bm25_test.jsonl"),
    ("IRCoT", "E5-base-v2 (Dense)", "ircot_e5_test.jsonl"),
    ("IRCoT", "MiniLM (Dense)", "ircot_minilm_test.jsonl"),
    ("E-RAG-Balanced", "BGE-base-en-v1.5 (Dense)", "erag_balanced_bge_test.jsonl"),
    ("E-RAG-Balanced", "BM25 (Sparse)", "erag_balanced_bm25_test.jsonl"),
    ("E-RAG-Balanced", "E5-base-v2 (Dense)", "erag_balanced_e5_test.jsonl"),
    ("E-RAG-Balanced", "MiniLM (Dense)", "erag_balanced_minilm_test.jsonl"),
]


def check_phase5_cells():
    """The 12 Phase 5 benchmark cells vs four_retriever_benchmark.csv."""
    csv_path = os.path.join(ROOT, "research/retrievers/four_retriever_benchmark.csv")
    with open(csv_path, newline="", encoding="utf-8") as f:
        claimed = {(r["System"], r["Retriever"]): r for r in csv.DictReader(f)}

    failures = []
    for system, retriever, fname in PHASE5_CELLS:
        rows = load_jsonl(os.path.join(ROOT, "results/enriched", fname))
        ok = [r for r in rows if not r.get("failed", False)]
        ans = [r for r in ok if not r.get("unknown", False)]
        got = {
            "N": len(rows),
            "Exact Match": mean_or_nan([r["em"] for r in ok]),
            "Token F1": mean_or_nan([r["f1"] for r in ok]),
            "Gold Para Recall": mean_or_nan(
                [r["recall"] for r in ok if r.get("recall") is not None]),
            "All-Gold Rate": mean_or_nan(
                [r["all_gold"] for r in ok if r.get("all_gold") is not None]),
            "Mean Docs": mean_or_nan([len(r.get("pool_titles", [])) for r in ok]),
            "Coverage": len(ans) / max(len(rows), 1),
            "Selective EM": mean_or_nan([r["em"] for r in ans]),
            "Mean Calls": mean_or_nan([r["llm_calls"] for r in ok]),
            "Mean Tokens": mean_or_nan(
                [r["in_tokens"] + r["out_tokens"] for r in ok]),
            "Cost / 1k USD": (
                mean_or_nan([r["in_tokens"] for r in ok]) * RATE_IN_PER_1M
                + mean_or_nan([r["out_tokens"] for r in ok]) * RATE_OUT_PER_1M
            ) / 1000.0,
            "Live Calls/Q": mean_or_nan(
                [r["llm_calls"] - r.get("cache_hits", 0) for r in ok]),
        }
        want = claimed.get((system, retriever))
        if want is None:
            failures.append(f"{system}/{retriever}: no row in benchmark CSV")
            continue
        tol = {
            "N": 0, "Exact Match": 0.001, "Token F1": 0.001,
            "Gold Para Recall": 0.001, "All-Gold Rate": 0.001,
            "Mean Docs": 0.05, "Coverage": 0.001, "Selective EM": 0.001,
            "Mean Calls": 0.01, "Mean Tokens": 0.15, "Cost / 1k USD": 0.001,
            "Live Calls/Q": 0.01,
        }
        for col, t in tol.items():
            w = float(want[col])
            if not close(got[col], w, t):
                failures.append(
                    f"{system}/{retriever} {col}: recomputed {got[col]:.4f} "
                    f"!= claimed {w:.4f}")
    detail = "12 cells recomputed from results/enriched/*_test.jsonl"
    if failures:
        detail += "; MISMATCHES: " + "; ".join(failures)
    return ("Phase 5 benchmark cells (12)", not failures, detail)


def check_trueadaptive_dev():
    """TrueAdaptive Dev-100 MiniLM + BM25 vs the audit's headline numbers."""
    cases = [
        ("MiniLM", "results/trueadaptive/erag_trueadaptive_dev.jsonl",
         0.50, 0.6018, 4.91),
        ("BM25", "results/trueadaptive/erag_trueadaptive_bm25_dev.jsonl",
         0.56, 0.6495, 4.58),
    ]
    failures = []
    for name, path, em, f1, calls in cases:
        rows = load_jsonl(os.path.join(ROOT, path))
        ok = [r for r in rows if not r.get("failed", False)]
        got_em = mean_or_nan([r["em"] for r in ok])
        got_f1 = mean_or_nan([r["f1"] for r in ok])
        got_calls = mean_or_nan([r["llm_calls"] for r in ok])
        got_hits = mean_or_nan([r.get("cache_hits", 0) for r in ok])
        if len(rows) != 100 or len(ok) != 100:
            failures.append(f"{name}: n={len(rows)} ok={len(ok)}, want 100/100")
        if not close(got_em, em, 0.001):
            failures.append(f"{name}: EM {got_em:.4f} != {em}")
        if not close(got_f1, f1, 0.001):
            failures.append(f"{name}: F1 {got_f1:.4f} != {f1}")
        if not close(got_calls, calls, 0.01):
            failures.append(f"{name}: calls {got_calls:.2f} != {calls}")
        if got_hits != 0:
            failures.append(f"{name}: mean cache_hits {got_hits} != 0 (not all live)")
    detail = "Dev-100 MiniLM EM 0.50/F1 0.6018/4.91 calls; BM25 EM 0.56/F1 0.6495/4.58 calls"
    if failures:
        detail += "; MISMATCHES: " + "; ".join(failures)
    return ("TrueAdaptive Dev-100 (MiniLM + BM25)", not failures, detail)


def check_test400_head_to_head():
    """TrueAdaptive Test-400 BM25 vs IRCoT, with McNemar (audit H3)."""
    ta_raw = load_jsonl(os.path.join(
        ROOT, "results/trueadaptive/erag_trueadaptive_test_bm25.jsonl"))
    ta = dedupe_keep_last(ta_raw)
    ir = load_jsonl(os.path.join(ROOT, "results/ircot_test_bm25.jsonl"))
    failures = []
    if len(ta_raw) != len(ta):
        # Resume duplicate: the stale failed row must be the only extra line.
        extra = len(ta_raw) - len(ta)
        stale = [r for r in ta_raw if r.get("failed", False)]
        if extra != 1 or len(stale) != 1:
            failures.append(
                f"TA file has {len(ta_raw)} rows for {len(ta)} unique ids "
                f"({extra} extra, {len(stale)} failed rows) — expected 1 stale failed row")
    if len(ta) != 400 or len(ir) != 400:
        failures.append(f"n: TA={len(ta)} IR={len(ir)}, want 400/400")
        return ("TrueAdaptive Test-400 BM25 vs IRCoT", False,
                "; ".join(failures))
    ta_by_id = {r["id"]: r for r in ta}
    ir_by_id = {r["id"]: r for r in ir}
    if set(ta_by_id) != set(ir_by_id):
        failures.append("question id sets differ between TA and IRCoT files")
        return ("TrueAdaptive Test-400 BM25 vs IRCoT", False,
                "; ".join(failures))
    ta_em = mean_or_nan([r["em"] for r in ta])
    ir_em = mean_or_nan([r["em"] for r in ir])
    ta_calls = mean_or_nan([r["llm_calls"] for r in ta])
    ir_calls = mean_or_nan([r["llm_calls"] for r in ir])
    ta_hits = mean_or_nan([r.get("cache_hits", 0) for r in ta])
    ir_hits = mean_or_nan([r.get("cache_hits", 0) for r in ir])
    b = sum(1 for i in ta_by_id
            if ta_by_id[i]["em"] == 1 and ir_by_id[i]["em"] == 0)
    c = sum(1 for i in ta_by_id
            if ta_by_id[i]["em"] == 0 and ir_by_id[i]["em"] == 1)
    n_d = b + c
    chi2 = (abs(b - c) - 1) ** 2 / n_d if n_d else 0.0
    p_cc = math.erfc(math.sqrt(chi2 / 2)) if n_d else 1.0
    checks = [
        (ta_em, 0.4750, 0.001, f"TA EM {ta_em:.4f} != 0.4750"),
        (ir_em, 0.4200, 0.001, f"IR EM {ir_em:.4f} != 0.4200"),
        (ta_calls, 4.775, 0.01, f"TA calls {ta_calls:.3f} != 4.775"),
        (ir_calls, 2.545, 0.01, f"IR calls {ir_calls:.3f} != 2.545"),
        (p_cc, 0.0043, 0.0005, f"McNemar p {p_cc:.4f} != 0.0043"),
    ]
    for got, want, tol, msg in checks:
        if not close(got, want, tol):
            failures.append(msg)
    if ta_hits != 0 or ir_hits != 0:
        failures.append(
            f"cache hits not zero (TA {ta_hits}, IR {ir_hits}) — not all live")
    detail = (f"TA EM {ta_em:.4f} vs IR EM {ir_em:.4f} "
              f"({ta_calls:.2f} vs {ir_calls:.2f} calls/Q); "
              f"McNemar b={b} c={c} p={p_cc:.4f} (exact "
              f"{sum(math.comb(n_d, k) for k in range(0, min(b, c) + 1)) * 2 / (2 ** n_d):.4f})")
    return ("TrueAdaptive Test-400 BM25 vs IRCoT (McNemar)", not failures, detail)


def check_call_reduction():
    """Corrected Reference->Balanced call reduction: -39.8% (not -45.4%)."""
    ref = load_jsonl(os.path.join(ROOT, "results/erag_active_test.jsonl"))
    bal = load_jsonl(os.path.join(ROOT, "results/cost_opt/erag_balanced_test.jsonl"))
    ref_calls = mean_or_nan([r["llm_calls"] for r in ref if not r.get("failed", False)])
    bal_calls = mean_or_nan([r["llm_calls"] for r in bal if not r.get("failed", False)])
    reduction = (bal_calls - ref_calls) / ref_calls * 100
    failures = []
    if not close(ref_calls, 14.22, 0.01):
        failures.append(f"Reference mean calls {ref_calls:.2f} != 14.22")
    if not close(bal_calls, 8.56, 0.01):
        failures.append(f"Balanced mean calls {bal_calls:.2f} != 8.56")
    if not close(reduction, -39.8, 0.15):
        failures.append(f"reduction {reduction:.1f}% != -39.8%")
    detail = (f"Reference {ref_calls:.2f} -> Balanced {bal_calls:.2f} calls/Q "
              f"= {reduction:.1f}% (Test-400 MiniLM)")
    return ("Call reduction Reference->Balanced (-39.8%)", not failures, detail)


def check_manifest():
    """data/manifests/manifest.json SHAs match the actual files."""
    manifest_path = os.path.join(ROOT, "data/manifests/manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    failures = []
    notes = []
    for split in ("debug", "dev", "test"):
        path = os.path.join(ROOT, "data/manifests", f"{split}.jsonl")
        actual = sha256_file(path)
        recorded = manifest[split]["sha256"]
        if actual != recorded:
            failures.append(
                f"{split}: recorded {recorded[:12]}… != actual {actual[:12]}…")
        rows = load_jsonl(path)
        if len(rows) != manifest[split]["n"]:
            failures.append(
                f"{split}: n={len(rows)} != manifest n={manifest[split]['n']}")
    raw_candidates = [
        os.path.join(ROOT, "data/hotpot_dev_distractor_v1.json"),
        os.path.join(ROOT, "data/raw/hotpot_dev_distractor_v1.json"),
    ]
    raw_path = next((p for p in raw_candidates if os.path.exists(p)), None)
    if raw_path is None:
        notes.append("raw file hotpot_dev_distractor_v1.json not in repo; "
                     "raw_sha256 not checked")
    else:
        actual = sha256_file(raw_path)
        if actual != manifest["raw_sha256"]:
            failures.append("raw_sha256 mismatch")
    detail = "manifest SHAs match debug/dev/test files" + (
        "; " + "; ".join(notes) if notes else "")
    if failures:
        detail += "; MISMATCHES: " + "; ".join(failures)
    return ("Manifest SHAs", not failures, detail)


def check_cache():
    """results/cache.sqlite: zero empty-text rows, integrity ok."""
    db_path = os.path.join(ROOT, "results/cache.sqlite")
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        total = db.execute("SELECT COUNT(*) FROM c").fetchone()[0]
        empty = sum(
            1 for (v,) in db.execute("SELECT v FROM c")
            if not json.loads(v).get("text"))
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        db.close()
    failures = []
    if empty != 0:
        failures.append(f"{empty} empty-text rows in cache")
    if integrity != "ok":
        failures.append(f"integrity_check = {integrity}")
    detail = f"{total} rows, {empty} empty-text rows, integrity_check={integrity}"
    return ("Cache integrity (zero empty rows)", not failures, detail)


def check_h1_text():
    """Phase 5 report names the right generator (audit H1)."""
    path = os.path.join(
        ROOT, "research/retrievers/four_retriever_analysis_report.md")
    text = open(path, encoding="utf-8").read()
    failures = []
    if text.count("openai/gpt-oss-20b") < 3:
        failures.append("generator openai/gpt-oss-20b named < 3 times")
    if "Correction" not in text:
        failures.append("no visible correction note in the report")
    # The old wrong name may only survive inside the correction note itself.
    bad_lines = [ln for ln in text.splitlines()
                 if "llama-3.3-70b" in ln and "Correction" not in ln
                 and "corrected" not in ln.lower()
                 and "was" not in ln.lower() and "wrong" not in ln.lower()]
    if bad_lines:
        failures.append(
            f"llama-3.3-70b still stated as the generator in: {bad_lines[0][:100]}")
    detail = "generator openai/gpt-oss-20b named " \
        f"{text.count('openai/gpt-oss-20b')} times; correction note present"
    return ("Phase 5 report generator name (H1)", not failures, detail)


def check_phase5_report_matrix():
    """Phase 5 report Heading A matrix agrees with the benchmark CSV.

    The CSV is verified against the raw files by check_phase5_cells, so
    report-vs-CSV agreement is sufficient here. Catches drift like the
    BGE rows, whose Coverage/Selective EM/Mean Tokens (and IRCoT Mean
    Docs/Mean Calls) once disagreed with the CSV.
    """
    report_path = os.path.join(
        ROOT, "research/retrievers/four_retriever_analysis_report.md")
    lines = open(report_path, encoding="utf-8").read().splitlines()
    hdr_idx = next(i for i, ln in enumerate(lines)
                   if ln.startswith("| Paradigm | Retriever"))
    header = [c.strip() for c in lines[hdr_idx].strip("|").split("|")]
    rows = []
    for ln in lines[hdr_idx + 2:]:
        if not ln.startswith("|"):
            break
        rows.append(dict(zip(
            header, [c.strip().strip("*") for c in ln.strip("|").split("|")])))
    csv_path = os.path.join(ROOT, "research/retrievers/four_retriever_benchmark.csv")
    with open(csv_path, newline="", encoding="utf-8") as f:
        claimed = {(r["System"], r["Retriever"].split(" (")[0]): r
                   for r in csv.DictReader(f)}
    colmap = {"Exact Match (EM)": "Exact Match", "Token F1": "Token F1",
              "Gold Para Recall": "Gold Para Recall",
              "All-Gold Rate": "All-Gold Rate", "Mean Docs": "Mean Docs",
              "Coverage": "Coverage", "Selective EM": "Selective EM",
              "ECE": "ECE", "Brier Score": "Brier", "AUROC": "AUROC",
              "Mean Calls": "Mean Calls", "Mean Tokens": "Mean Tokens",
              "Cost / 1k ($)": "Cost / 1k USD"}
    sysmap = {"Standard RAG": "Standard RAG",
              "IRCoT-Controlled": "IRCoT", "E-RAG-Balanced": "E-RAG-Balanced"}
    failures = []
    if len(rows) != 12:
        failures.append(f"report matrix has {len(rows)} rows, want 12")
    for r in rows:
        key = (sysmap[r["Paradigm"]],
               r["Retriever Architecture"].split(" (")[0])
        want = claimed.get(key)
        if want is None:
            failures.append(f"{key}: no row in benchmark CSV")
            continue
        for rcol, ccol in colmap.items():
            tol = 0.15 if rcol == "Mean Tokens" else 0.0015
            if not close(float(r[rcol]), float(want[ccol]), tol):
                failures.append(
                    f"{key[0]}/{key[1]} {rcol}: report {r[rcol]} "
                    f"!= CSV {want[ccol]}")
    detail = "report Heading A matrix matches four_retriever_benchmark.csv (12 rows)"
    if failures:
        detail += "; MISMATCHES: " + "; ".join(failures)
    return ("Phase 5 report matrix vs benchmark CSV", not failures, detail)


def check_h3_labels():
    """Head-to-head CSV labels re-thresholdings as post-hoc (audit H3)."""
    path = os.path.join(
        ROOT, "results/erag_vs_ircot_study/head_to_head_comparisons.csv")
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    failures = []
    if "Notes" not in rows[0]:
        failures.append("no Notes column in head_to_head_comparisons.csv")
    else:
        for r in rows:
            if "Matched" in r["System Comparison"] or "Uninhibited" in r["System Comparison"]:
                if "POST-HOC" not in r.get("Notes", ""):
                    failures.append(
                        f"{r['System Comparison']} not labelled post-hoc")
    detail = "Matched/Uninhibited labelled POST-HOC re-thresholdings"
    return ("Head-to-head CSV post-hoc labels (H3)", not failures, detail)


CHECKS = [
    check_phase5_cells,
    check_phase5_report_matrix,
    check_trueadaptive_dev,
    check_test400_head_to_head,
    check_call_reduction,
    check_manifest,
    check_cache,
    check_h1_text,
    check_h3_labels,
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", default=os.path.join(ROOT, "docs/verification-report.md"))
    args = ap.parse_args()

    results = []
    for fn in CHECKS:
        try:
            results.append(fn())
        except Exception as ex:  # noqa: BLE001 — report, don't crash
            results.append((fn.__name__, False, f"ERROR: {ex!r}"))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Verification report — ERag headline results",
        "",
        f"Generated: {now} by `scripts/verify_results.py` (commit `{git_commit()}`).",
        "Every figure below is recomputed from the raw results files; nothing is",
        "copied from a report. A FAIL means the stored record disagrees with its",
        "own raw data and must be fixed, not re-run.",
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
    ]
    for name, passed, detail in results:
        lines.append(f"| {name} | {'PASS' if passed else 'FAIL'} | {detail} |")
    lines += [
        "",
        "## Not covered by this script",
        "",
        "- ECE / Brier / AUROC columns of the Phase 5 benchmark (calibration",
        "  metrics — need the confidence fields, not just row aggregates).",
        "- The `raw_sha256` manifest entry when the raw HotpotQA file is not in",
        "  the repo (noted in the manifest check when skipped).",
        "- MLflow provenance (local `mlflow.db`, gitignored): see",
        "  `docs/cache-namespaces.md` for the L4 note.",
        "",
    ]
    report = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as f:
        f.write(report)

    failed = [r for r in results if not r[1]]
    for name, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'}  {name}: {detail}")
    print(f"\nWrote {args.report}")
    if failed:
        print(f"\n{len(failed)} check(s) FAILED")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
