# Proposal: Verifier threshold sweep (Phase 2.6 H16)

## Why

The NLI verifier's thresholds (theta_s / theta_c, both 0.5) have never
been tuned. H2 showed the consequence: on the 60-pair labelled set the
verifier's macro-F1 is 0.6825 < 0.70, and its weakness is supported
recall 0.60 — it is too conservative, so true claims stay out of the
supported set. That starves every downstream mechanism: H12's contested
re-read and H15's support-ranked re-read both read the supported set,
and gold claims that are never marked supported can never be chosen.

The stored dev traces let us tune the thresholds without any new LLM
calls: the verifier is a local cross-encoder, and the claim-passage
scores are memoized, so a sweep over threshold pairs is pure
re-computation on stored claims.

## What

Build a claim-level eval from the improved system's Dev-100 traces
(H14 baseline file, tuned + contested, all-live): ~546 claims across
hops, labelled SUPPORTED iff the claim text matches a gold supporting
fact from the manifest (normalized containment either way), else
NOT-SUPPORTED. Sweep (theta_s, theta_c) over a grid, select thresholds
on 70 rows, judge on the held-out 30 rows. The 60-pair H2 set is a
second check for the contradicted class (which the manifest cannot
label), not the gate. The winning thresholds then go into a Dev-100
BM25 A/B against the improved-system baseline.

## H16 (pre-registered 2026-11-11, before any new run)

A threshold pair exists with binary macro-F1 ≥ 0.70 AND supported
recall ≥ 0.70 on held-out dev-trace claims — the same bar H2 missed —
and the Dev-100 BM25 A/B with those thresholds does not lower EM vs
the improved-system baseline (dEM ≥ 0) at ≤ +0.2 calls/Q (thresholds
cost no extra calls, so the cost leg is a guardrail). Exploratory.

## Scope

- One OpenSpec change; the sweep is an offline analysis script, not a
  change to `src/` — the only production change is the two threshold
  values in config if the gate passes.
- No Test-400 involvement anywhere in selection: thresholds are chosen
  on dev traces and judged on held-out dev traces; the Test-400
  confirmation judges the system as a whole at the end of Phase 2.6.
