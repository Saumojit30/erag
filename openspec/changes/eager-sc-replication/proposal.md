# Proposal: Phase 2.5 H14 — Eager SC, dev replication of the FP-control direction

## Status

Draft — prepared 2026-11-11 from the pre-registered H14 in
`docs/phase25-improvement-diagnosis.md` and the Test-400 D2 FP-leg
numbers. Phase 2.5, third of three mechanisms (H12 GATE PASS
2026-11-11; H13 A/B running). User decision 2026-11-11: improve first,
then Phase 3. **This change is drafted while H13 runs; its A/B starts
only after the H13 verdict, on the post-H13 improved system.**

## Why

On Test-400 the FP-control arm — the tuned system with
`erag.gate_sc_behind_fast_path=false`, i.e. self-consistency run up
front at hop 0 instead of deferred behind the fast-path check — scored
EM 0.4675 vs the tuned 0.4500 (dEM +0.0175, 95% CI [−0.0100, +0.0450],
p=0.2810) at +0.70 calls/Q, and 0.4675 vs FP-off 0.4500 (dEM +0.0175,
p=0.2100). Directional only, inside noise, and the diagnosis found the
effect is symmetric churn of the answer/abstain boundary (19 gains /
12 losses, net +7). The question is whether the direction is real
enough to keep: does eager SC reproduce its Test-400 direction on
Dev-100, where it was never measured?

## Circularity note (recorded in the pre-registration, repeated here)

The direction was observed on Test-400 first, so dev is a REPLICATION
check, not a discovery. The Test-400 FP-control number cannot be
re-judged; if the direction replicates on dev, the mechanism enters the
improved system, judged fresh as a whole on its one Test-400
confirmation. If it does not replicate, the gate is dropped and the
Test-400 direction is reported as noise.

## What changes

Config only — no code. The H14 arm runs the post-H13 improved system
with `erag.gate_sc_behind_fast_path=false`. Everything else (learned
continuation policy, theta_abs=0.50, max_hops=2, contested resolution,
second extraction if H13 passed) is unchanged. Note the policy still
decides STOP/CONTINUE at hop 0; the flag only changes WHEN
self-consistency runs (up front, always at hop 0, instead of deferred
behind the fast-path check).

## Threats to validity

- **Dev-100 is small (N=100).** The Test-400 direction (+0.0175) is
  ~2 rows on dev. The gate is a smoke test: any EM gain at ≤ +1.0
  calls/Q counts as replication of the direction. A dev loss kills the
  mechanism outright.
- **Circularity.** See the note above — the dev result is a replication
  check, and the mechanism's final word is the one Test-400
  confirmation of the improved system, not this A/B.
- **Cost.** Eager SC costs up to +0.70 calls/Q on Test-400; the gate
  bounds it at ≤ +1.0 on dev. If the cost exceeds the bound, the
  mechanism is dropped even with an EM gain.
- **Cache / drift.** Both A/B arms re-run fresh with fresh namespaces;
  verify `cache_hits` before believing the paired comparison.

## Out of scope

- Any theta_abs change; any Test-400 selection (Test-400 rows above
  are diagnosis only); any change to the continuation policy itself.
