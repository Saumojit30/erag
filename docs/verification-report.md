# Verification report — ERag headline results

Generated: 2026-11-08 21:16 UTC by `scripts/verify_results.py` (commit `394cc88`).
Every figure below is recomputed from the raw results files; nothing is
copied from a report. A FAIL means the stored record disagrees with its
own raw data and must be fixed, not re-run.

| Check | Result | Detail |
|---|---|---|
| Phase 5 benchmark cells (12) | PASS | 12 cells recomputed from results/enriched/*_test.jsonl |
| TrueAdaptive Dev-100 (MiniLM + BM25) | PASS | Dev-100 MiniLM EM 0.50/F1 0.6018/4.91 calls; BM25 EM 0.56/F1 0.6495/4.58 calls |
| TrueAdaptive Test-400 BM25 vs IRCoT (McNemar) | PASS | TA EM 0.4750 vs IR EM 0.4200 (4.78 vs 2.54 calls/Q); McNemar b=38 c=16 p=0.0043 (exact 0.0038) |
| Call reduction Reference->Balanced (-39.8%) | PASS | Reference 14.22 -> Balanced 8.56 calls/Q = -39.8% (Test-400 MiniLM) |
| Manifest SHAs | PASS | manifest SHAs match debug/dev/test files; raw file hotpot_dev_distractor_v1.json not in repo; raw_sha256 not checked |
| Cache integrity (zero empty rows) | PASS | 26488 rows, 0 empty-text rows, integrity_check=ok |
| Phase 5 report generator name (H1) | PASS | generator openai/gpt-oss-20b named 4 times; correction note present |
| Head-to-head CSV post-hoc labels (H3) | PASS | Matched/Uninhibited labelled POST-HOC re-thresholdings |

## Not covered by this script

- ECE / Brier / AUROC columns of the Phase 5 benchmark (calibration
  metrics — need the confidence fields, not just row aggregates).
- The `raw_sha256` manifest entry when the raw HotpotQA file is not in
  the repo (noted in the manifest check when skipped).
- MLflow provenance (local `mlflow.db`, gitignored): see
  `docs/cache-namespaces.md` for the L4 note.

