# Proposal: Support-ranked final re-read (Phase 2.6 H15)

## Why

The Phase 2.5 diagnosis found 53 full-recall wrong rows where the gold
evidence is already in the belief graph but the final answer sits inside
a WRONG supported claim (34/53). The H15 headroom check (2026-11-11,
stored tuned Test-400 rows, `docs/phase26-beat-ircot-plan.md`) shows the
fix is reachable at the final read:

- Gold out-supports the wrong answer (max eff over supported claims) on
  24/53 rows; 25 ties, 1 wrong-higher, 3 gold in no supported claim.
- Gold is in the top-3 supported claims by eff on 48/53 rows, top-5 on
  50/53. A re-read grounded only on the top-3 claims has the gold
  evidence in front of it almost every time.
- Trigger "draft not in top-3 supported claims by eff" fires on 24/53
  target rows vs 39/180 correct rows — selective enough to bound the
  break risk. The dev A/B measures the actual break rate.

A naive pick over answer-bearing claims only fixes 4/53 (the
answer-bearing flag follows the draft; gold is in NO answer-bearing
supported claim on 32/53 rows), so the mechanism must use ALL supported
claims — and the pick must be the LLM re-read, never the top claim's
answer: the top-1 supported claim lacks gold on 100/180 correct rows.

## What

At the final read, rank supported claims by `eff` descending. If the
normalized draft appears in none of the top-3, run one extra reader
call grounded ONLY on those top-3 claims and let the reader choose the
answer from them. Behind `erag.support_ranked_reread` (default false);
flag-off runs byte-identical. Row field `support_ranked` recorded only
when the flag is on. At most one extra LLM call per question, only on
triggered rows.

## H15 (pre-registered 2026-11-11, before any new run)

When the draft is not backed by the top-3 supported claims, the
support-ranked re-read raises Dev-100 BM25 EM ≥ +0.02 vs the
improved-system baseline (tuned + contested + eager SC) at ≤ +0.5
calls/Q, and fixes more triggered rows than it breaks. Exploratory.

## Scope

- One OpenSpec change, one flag, no other behavior change.
- The re-read sits after the unknown/disagree and contested triggers
  in the final-read block (as an independent check gated on no earlier
  trigger having fired, so it stays reachable when both flags are on)
  — clean attribution in the A/B.
- Dev-100 BM25 A/B, paired fresh baseline, gate as smoke test; then the
  Phase 2.6 Test-400 confirmation judges the system as a whole.
