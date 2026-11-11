# Tasks: Phase 2.5 H13 — Extraction recall, second pass

## 0. OpenSpec change (before any code)

- [x] 0.1 Create `openspec/changes/improve-extraction-recall/` with
  `proposal.md`, `design.md`, `tasks.md` (this file) — drafted
  2026-11-11 from `docs/phase25-improvement-diagnosis.md` plus a
  stored-data diagnosis the same day (cap binds 2/33, fallbacks 0/33,
  no conditional trigger identifies the never-claimed rows). H13
  pre-registered 2026-11-11; baseline rate clarified to the fresh
  paired baseline (0.619, not the stale 0.333).
- [x] 0.2 Validate with the local CLI:
  `~/workspace/tools/openspec/node_modules/.bin/openspec validate --all`
  — must pass before the A/B.

## A. Tests first (no production change yet)

- [x] A.1 In a new `tests/test_extraction_recall.py`, add pure-function
  tests for `merge_claims`: duplicate normalized text dropped;
  new claim appended in order; empty additional list is a no-op;
  article/punctuation differences count as duplicates.
- [x] A.2 Add a prompt-builder test: the second-pass messages list the
  existing claims, ask for additional uncovered claims, and carry the
  question + context.
- [x] A.3 Add a mocked-LLM test: hop-0 extraction returns 1 claim,
  second pass returns 1 new claim + 1 duplicate → graph gets 2
  claims, `second_pass_added == 1`, exactly +1 LLM call vs flag-off;
  flag off → no extra call, no new fields.

## B. Implementation

- [x] B.1 Add `SECOND_PASS_SYSTEM`, `extract_claims_second_pass()`
  and `merge_claims()` to `src/epistemic/claims.py` (reuse `_parse`).
- [x] B.2 Wire the hop-0 second pass into `run_erag` in
  `src/systems/erag.py` behind `erag.second_extraction` (default
  False); record `second_pass_added` / `second_extraction` on the
  row when the flag is on.
- [x] B.3 Full suite: `tests/` must stay 176 passed / 1 known
  pre-existing failure (`test_retry_exhaustion_raises_runtime_error`)
  — measured 176/1 at commit 8f215e0 (+8 H13 tests on the 168/1
  H12 count).

## C. Dev-100 A/B (gate = smoke test)

- [x] C.1 Baseline: frozen tuned config +
  `erag.contested_resolution=true`, Dev-100 BM25, fresh namespace
  `dev_p25_h13_base_bm25`, output
  `results/trueadaptive/erag_p25_h13_base_dev.jsonl`.
- [x] C.2 H13 arm: same + `erag.second_extraction=true`, fresh
  namespace `dev_p25_h13_second_bm25`, output
  `results/trueadaptive/erag_p25_h13_second_dev.jsonl`. One
  `--set` per invocation (repeated `--set` overwrites).
- [x] C.3 Verify `cache_hits` on both files; compute EM/F1/calls-Q
  paired (McNemar) + gold-in-claims rate among full-recall wrong
  rows + median `second_pass_added`. Gate: rate rises, EM does not
  fall, calls/Q rise ≤ +1.0.
- [x] C.4 Record in master plan §12 + assumptions-vs-outcomes +
  hypotheses status (H13 verdict). If the gate fails, the mechanism
  is dropped — no further tuning on dev.

## D. Close-out

- [x] D.1 Commit on `trueadaptive` (proper message, author
  Saumojit30). Do not push (PAT pending — separate blocked item).
- [x] D.2 Archive the change (`openspec archive -y`) and re-validate.
