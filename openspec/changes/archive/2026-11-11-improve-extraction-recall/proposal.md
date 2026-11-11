# Proposal: Phase 2.5 H13 — Extraction recall, second pass over the hop-0 pool

## Status

Draft — prepared 2026-11-11 from `docs/phase25-improvement-diagnosis.md`
and a stored-data diagnosis the same day (no live calls yet). Phase 2.5,
second of three mechanisms (H12 GATE PASS 2026-11-11; H14 eager SC
follows). User decision 2026-11-11: improve first, then Phase 3.

## Why

The tuned system's second diagnosed failure population is 33 Test-400
rows where the gold answer was retrieved at hop 0 (hop-0 recall 1.0 on
27/33) but never became a claim. A stored-data check (2026-11-11) rules
out the easy explanations: the max_claims=8 cap binds on only 2/33 rows
at hop 0, and extraction never fails to parse (claim_fallbacks 0/33).
The extractor produces 2–8 claims, including question-sourced ones, and
simply skips the gold sentence. It is a coverage failure, not a capacity
failure — so the fix must change *what* the extractor produces, not how
much room it has.

## What changes

One second extraction pass at hop 0 only, behind
`erag.second_extraction` (default false): after the first extraction,
a coverage-driven prompt — given the question, the draft, and the claims
already extracted, list additional factual claims from the Context that
bear on the question and are NOT already covered, especially claims
stating a name, date, or value that could be the answer — runs one more
LLM call, and the new claims are merged into the claim set (deduped by
normalized text) before the belief graph is built. At most +1 LLM call
per question, hop 0 only.

## Dated clarification to H13 (before the affected run, Rule 2)

H13 as pre-registered judges the gold-in-claims rate "vs the tuned dev
baseline (0.333 on the step-2 dev set)". That 0.333 is the step-2-era v1
dev file. The current tuned dev baseline, measured on the fresh H12
base file (`results/trueadaptive/erag_p25_h12_base_dev.jsonl`, N=100),
is **0.619** (13/21 full-recall wrong rows; 8 never-claimed). The H13
A/B is judged against the **fresh paired baseline** run alongside it,
not the stale 0.333. The criterion itself is unchanged: the rate rises
and EM does not fall. A cost guardrail is added for the gate (not a
criterion change): calls/Q rise ≤ +1.0, the cost of the second pass.

## Trigger decision (measured before the run)

No conditional trigger identifies the never-claimed rows in stored
data: "draft not in any claim" covers 3/33; "no question-sourced claim"
8/33 at 23% false-trigger on correct rows; "answer-bearing claim
contradicted/unresolved" 12/33 at 44% false-trigger. The second pass
therefore runs **unconditionally at hop 0**. The cost is measured
directly in the A/B (+1 call/Q maximum).

## Threats to validity

- **Dev-100 is small (N=100).** The never-claimed population on dev is
  8 rows (H12 base file). Moving 1–2 of 8 moves the rate by 0.05–0.10 —
  inside noise. The gate is a smoke test, not a verdict; the mechanism
  must also raise the rate without lowering EM, and the final word is
  the one Test-400 confirmation of the improved system.
- **The second pass may duplicate the first.** The coverage instruction
  plus dedupe by normalized text is the guard; `second_pass_added`
  (recorded per row) shows how many genuinely new claims each pass
  adds. If the median added is 0, the mechanism is dropped.
- **More claims, more NLI.** Merged claims are verified by the local NLI
  (not LLM calls), so the LLM cost is exactly +1 call/Q maximum; the
  NLI cost is local compute, not billed calls.
- **Cache / drift.** Both A/B arms re-run fresh with fresh namespaces;
  verify `cache_hits` before believing the paired comparison.

## Out of scope

- H14 (eager SC) — separate change, after H13.
- Any theta_abs change; any Test-400 selection (Test-400 rows above
  are diagnosis only).
