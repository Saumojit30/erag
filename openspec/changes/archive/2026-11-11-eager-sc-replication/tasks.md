# Tasks: Phase 2.5 H14 — Eager SC, dev replication

## 0. OpenSpec change (before any run)

- [x] 0.1 Create `openspec/changes/eager-sc-replication/` with
  `proposal.md`, `design.md`, `tasks.md` (this file) — drafted
  2026-11-11 while the H13 A/B runs, from the pre-registered H14 in
  `docs/phase25-improvement-diagnosis.md` and the Test-400 D2 FP-leg
  numbers (FP-control 0.4675 vs tuned 0.4500, dEM +0.0175, p=0.2810,
  +0.70 calls/Q; circularity noted — dev is a replication check).
- [x] 0.2 Validate with the local CLI:
  `~/workspace/tools/openspec/node_modules/.bin/openspec validate --all`
  — must pass before the A/B. Passed 13/13 at draft time (2026-11-11)
  and re-checked 13/13 on 2026-11-11 while the H14 A/B awaits a key.

## A. Tests

- [x] A.1 No new tests: the flag already exists and is exercised by
  the existing suite (D2 FP-leg runs used it). Confirmed before the
  A/B: targeted subset `test_erag.py` + `test_contested_resolution.py`
  + `test_extraction_recall.py` — 51 passed, 2026-11-11. Full suite
  baseline remains 176 passed / 1 known pre-existing failure
  (measured at 8f215e0; no `src/` change since).

## B. Implementation

- [x] B.1 None — config-only change. No code. (no-op: no code by design)

## C. Dev-100 A/B (gate = smoke test)

- [x] C.1 Baseline: post-H13 improved system (tuned +
  `erag.contested_resolution=true`; `erag.second_extraction=true`
  only if H13 passed — H13 FAILED 2026-11-11, so the baseline has NO
  second extraction), Dev-100 BM25, fresh namespace
  `dev_p25_h14_base_bm25`, output
  `results/trueadaptive/erag_p25_h14_base_dev.jsonl`.
- [x] C.2 H14 arm: same + `erag.gate_sc_behind_fast_path=false`,
  fresh namespace `dev_p25_h14_eager_bm25`, output
  `results/trueadaptive/erag_p25_h14_eager_dev.jsonl`. One `--set`
  per invocation (repeated `--set` overwrites).
- [x] C.3 Verify `cache_hits` on both files; compute EM/F1/calls-Q
  paired (McNemar). Gate: EM gain at ≤ +1.0 calls/Q. A dev loss, or
  cost above +1.0, drops the mechanism.
- [x] C.4 Record in master plan §12 + assumptions-vs-outcomes +
  hypotheses status (H14 verdict). If the gate fails, the mechanism
  is dropped — no further tuning on dev.

## D. Close-out

- [x] D.1 Commit on `trueadaptive` (proper message, author
  Saumojit30). Do not push (PAT pending — separate blocked item).
- [x] D.2 Archive the change (`openspec archive -y`) and re-validate.
