# Proposal: Learned continuation policy (tuning step 7)

Drafted 2026-11-09 from `docs/tuning-master-plan.md` (§3.7), the H1–H6
assessment, the step-4/5 findings, and fresh recomputation from the
stored post-step-4 dev traces. Branch `trueadaptive`. Nothing is
pushed. Do not start the build until the proposal is approved — the
user approves by saying go (or by tapping the offer); the build then
follows `tasks.md`.

## Why

The user asked (2026-11-09): is this system properly adaptive, or
just static values? The honest answer given: the *structure* is
adaptive (per-question effort varies 2→9 calls, and the H6 result
shows the extra work lands exactly where retrieval was incomplete),
but the *decision boundaries* are hand-set constants (theta_fast 0.8,
theta_gap 0.6, theta_abs 0.5, the ΔH<0.05 SC stop, max_hops). Steps
1–6 calibrated those constants; none of them made the system more
adaptive. This change does: it replaces the fixed hop-boundary
decision with a learned one.

## What (v1 scope, tight)

A learned draft-correctness model decides, at the hop-0 boundary,
whether to STOP (answer the hop-0 draft now, no retrieval) or
CONTINUE (enter the retrieval loop). The model is a logistic
regression on hop-0 features the system already produces (c0, claim
verification statuses, hop-0 recall, question type, draft-unknown
flag). It predicts P(hop-0 draft is correct); CONTINUE iff P < τ,
with τ chosen by cross-validation on dev. It subsumes the fixed
theta_fast fast-path rule and the first gap-continuation rule at hop
0. It does NOT touch: EIG gap *selection* (which gap to retrieve
once continuing), the SC procedure itself, abstention (theta_abs
stays 0.5 from step 4), or the max_hops=2 ceiling (a safety bound,
not a decision).

Out of scope for v1: a hop-1 continuation decision (only 55 dev rows
reach hop 1, and hop 2 helped 4 / broke 2 of the 10 that went there —
too thin to learn from); a pre-hoc question-text router (weakest
signal, biggest build — considered and set aside in the user's
2026-11-09 choice); any test-time training.

## Training data (dev only, never test)

The model trains ONLY on the post-step-4 tuned dev traces
(`results/trueadaptive/erag_trueadaptive_bm25_dev_theta_a.jsonl`,
N=100): hop-0 features from each row's stored trace, label = the
hop-0 draft was correct (repo `exact_match`). Test-400 rows are never
used for training, feature selection, or threshold choice — Phase 2
is the judge, and anything learned from test would contaminate it.
The label is near-balanced (48/100 drafts correct), which is what
makes this learnable at N=100; the alternative framing (predict
"continuing helps") has only 6 positives and is not learnable here.

## How it is judged

Two gates, both pre-registered in `design.md` before any code:
(A) an offline counterfactual simulation on dev (no LLM calls — the
stored traces already contain every hop's draft, so the policy's
path can be simulated from them), then (B) a live Dev-100 A/B with
the policy wired in, confirming the live numbers match the
simulation. Both gates are the step-5 shape: calls/Q below the
post-step-4 tuned dev baseline (4.65) with EM not below baseline
− 0.01 (0.5000). Test-400 judges the frozen system at Phase 2, as
always.

## Interaction with step 5 (hop-2 SC cap)

Step 5 asked the same question this change answers, with a static
cap (`max_hops=1`): its A/B finished 2026-11-09 (EM 0.5100
unchanged, calls/Q 4.49 vs 4.65, live calls/Q 0.06 vs 0.04 — the
pre-registered gate fails on the live-calls measure only, by 2 calls
of replay noise). The user chose the learned policy instead of
deciding that gate. Step 5 therefore closes as SUPERSEDED: the
hop-depth decision is the policy's job now, `max_hops` stays 2 as a
ceiling, and the step-5 A/B result file is kept as record. The
step-5 change is archived with that verdict (tasks.md D.1), not
passed and not failed.
