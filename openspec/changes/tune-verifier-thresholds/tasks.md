# Tasks: Phase 2.6 H16 — Verifier threshold sweep

## 0. OpenSpec change (before any code)

- [x] 0.1 Create `openspec/changes/tune-verifier-thresholds/` with
  `proposal.md`, `design.md`, `tasks.md` (this file) — drafted
  2026-11-11 from `docs/phase26-beat-ircot-plan.md`. H16 pre-registered
  2026-11-11; the eval is built from stored Dev-100 traces, no live
  calls, no Test-400 involvement.
- [x] 0.2 Validate with the local CLI:
  `~/workspace/tools/openspec/node_modules/.bin/openspec validate --all`
  — must pass before the A/B. Validated 2026-11-11: 15/15 passed.

## A. Sweep (offline analysis, no production change)

- [x] A.1 Write `scripts/sweep_nli_thresholds.py`: claims from the H14
  baseline Dev-100 file, passages reconstructed from the dev manifest,
  proxy labels by gold-fact containment, 70/30 row split, grid
  theta_s {0.30–0.60} x theta_c {0.40–0.70} via the exact production
  `NLI.verify` call, 60-pair H2 set as a second check. Output
  `results/nli_threshold_sweep.json`.
- [ ] A.2 Run the sweep; record the winning pair (if any clears binary
  macro-F1 ≥ 0.70 AND supported recall ≥ 0.70 on held-out claims),
  the held-out numbers, and the 60-pair check numbers. If no pair
  clears the bar, H16 is NOT SUPPORTED on the eval leg and the A/B
  does not run.

## B. A/B (only if the eval leg passes; needs Groq key)

- [ ] B.1 Dev-100 BM25 A/B: baseline = improved system (frozen
  config), fresh namespace `dev_p26_h16_base_bm25`; thresholds arm =
  same + `nli.theta_s` / `nli.theta_c` overrides, fresh namespace
  `dev_p26_h16_thresh_bm25`. One `--set` per invocation. Gate:
  dEM ≥ 0 at ≤ +0.2 calls/Q.
- [ ] B.2 Record in master plan §12 + assumptions-vs-outcomes +
  hypotheses status (H16 verdict). If the gate fails, the thresholds
  stay at 0.5/0.5 — no further tuning on dev.

## C. Close-out

- [ ] C.1 Commit on `trueadaptive` (proper message, author
  Saumojit30). Do not push (PAT pending — separate blocked item).
- [ ] C.2 Archive the change (`openspec archive -y`) and re-validate.
