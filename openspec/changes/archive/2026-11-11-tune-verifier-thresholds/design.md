# Design: Verifier threshold sweep (Phase 2.6 H16)

## Eval construction (`scripts/sweep_nli_thresholds.py`)

1. **Claims.** From `results/trueadaptive/erag_p25_h14_base_dev.jsonl`
   (tuned + contested Dev-100, all-live): every graph claim across all
   hops, deduplicated by normalized text per row (~546 claims). The
   H14 baseline file is the improved system minus eager SC; eager SC
   changes sampling, not claim extraction or verification, and the
   thresholds are a property of the verifier — the A/B then judges them
   on the full improved system. Recorded here so the choice is auditable.
2. **Passages.** Each claim is re-verified against its hop's pool:
   `trace[i]['pool']` titles resolved to sentences via the dev manifest
   `data/manifests/dev.jsonl` (`context` [[title, [sentences]]]). The
   pool is the question's own distractor context, so titles resolve;
   any title that does not resolve is skipped and counted.
3. **Labels (proxy).** SUPPORTED iff the normalized claim text matches
   a gold supporting fact sentence — `supporting_facts` [title, idx]
   into the manifest context — by normalized containment either way
   (claim in fact, or fact in claim), minimum normalized claim length
   10 chars. Else NOT-SUPPORTED. The proxy UNDER-labels support
   (claims are often paraphrases, not verbatim), so the reported
   supported recall is a lower bound — the sweep compares thresholds
   on the same proxy, which is what selection needs.
4. **Contradicted class.** The manifest cannot label it, so the sweep's
   gate is binary (supported vs not-supported). The 60-pair H2 set
   (`data/nli_eval_pairs.jsonl`, human labels incl. contradicted) is
   run at each grid point as a second check — 3-class macro-F1 and
   contradicted recall reported alongside, never used for selection
   (reusing the H2 set for selection would overfit the set H2 was
   judged on).
5. **Split.** Rows in file order: first 70 for selection, last 30
   held out. Thresholds are chosen on selection only, judged on the
   held-out 30. The split is recorded in the output JSON.
6. **Scoring.** Each claim is re-verified by calling
   `NLI.verify(claim, passages, theta_s, theta_c, pre_filter=True)` —
   the exact production call (same pre-filter, same
   mentions-subject gate) — over the grid theta_s in
   {0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60} x theta_c in
   {0.40, 0.50, 0.60, 0.70}. `verify` calls the memoized `best()`, so
   after the first grid point the remaining 27 are pure Python.
   Metrics per combo: supported recall, supported precision,
   F1-supported, binary macro-F1, fraction predicted supported.

## Threats to validity

- **Proxy-label noise.** Paraphrased true claims are labelled
  NOT-SUPPORTED, which depresses precision and the macro-F1 ceiling.
  The gate bar (0.70) is therefore harder on this eval than on clean
  labels; if no combo clears it, the verdict is "no threshold clears
  the bar on this proxy", not "the verifier cannot be tuned" — and the
  60-pair check arbitrates. Selection among combos is still valid
  because the noise is threshold-independent.
- **Selection on 70 rows, ~380 claims.** The selection set is small;
  the held-out 30 rows (~160 claims) are the judge. A combo that wins
  selection by a hair and fails held-out is a failed gate, reported as
  such.
- **Thresholds interact with the system.** Better recall changes which
  claims are supported, which changes the re-reads and abstention. That
  is why the eval bar alone does not adopt the thresholds — the Dev-100
  A/B (dEM ≥ 0) is the second leg.
- **Memo reuse.** The sweep reads `results/nli_memo.pkl` (the same
  cache the system uses) and may add entries for pairs the system
  would compute anyway. It writes no result files the system reads.
