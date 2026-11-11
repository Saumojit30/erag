# Design: Phase 2.5 H14 — Eager SC, dev replication

## Mechanism

Config only. The flag `erag.gate_sc_behind_fast_path` already exists in
`src/systems/erag.py` (TrueAdaptive v1): when true, self-consistency at
hop 0 is deferred until after the fast-path check, so a question whose
claims are already supported costs draft + claims only; when false,
`_run_sc` runs up front at hop 0 before the graph is built and `c0`
comes from SC on every row. The H14 arm sets the flag false on the
post-H13 improved system. No new code, no new tests — the flag is
already exercised by the existing D2 FP-leg runs and the suite.

## A/B (gate, smoke test)

- Baseline: the post-H13 improved system (frozen tuned config +
  `erag.contested_resolution=true`, plus `erag.second_extraction=true`
  only if H13 passed its gate), Dev-100 BM25, fresh namespace
  `dev_p25_h14_base_bm25`.
- H14 arm: same + `erag.gate_sc_behind_fast_path=false`, fresh
  namespace `dev_p25_h14_eager_bm25`.
- Gate: EM gain (any positive paired dEM) at ≤ +1.0 calls/Q vs the
  fresh paired baseline. A dev loss, or a cost rise above +1.0, drops
  the mechanism. Verify `cache_hits` before believing the paired
  comparison.
