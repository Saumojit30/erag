# Proposal: Tune-Unknown-Prompt — Reader prompt experiment for model refusals (tuning step 3)

## Status

Draft — prepared 2026-11-09 from `docs/trueadaptive-test400-error-analysis.md`
(§2, §5) plus fresh counts of the unknown rows on the step-2 tuned dev file.
Branch `trueadaptive`. No code written yet. Third of five tuning changes; one
OpenSpec change per tuning step ("for each step use openspec along the way",
user 2026-11-09). Steps 1 (reader grounding) and 2 (claim extraction) are
built, gated, and archived.

**Decisions — resolved (user, 2026-11-09):**
1. Tuning order: (1) reader/graph — done, (2) claim extraction — done,
   (3) model-unknown prompt experiment — THIS change, (4) theta_abs,
   (5) hop-2 SC cap.
2. Tune on Dev-100 only (BM25, k=3, distractor). One Test-400 confirmation run
   at the END of tuning, not after this step.
3. This change is a prompt-only experiment on the reader. No retriever,
   threshold, belief-graph, NLI, or re-read change. No LLM fine-tune, no new
   dataset, no BGE.

## Why

The Test-400 BM25 error analysis found 77 unknown rows, in two populations
that must not be conflated. The 40 model-unknown rows are the target of this
change: the reader's draft is literally "unknown" (row flag `unknown`, not
abstained — the draft-unknown total is 47, of which 7 are also abstained and
belong to the other population). Their profile:

- `answer_conf` median 0.875, `c0` median 1.000 — the reader is confidently
  refusing. `theta_abs` cannot touch these rows (that is step 4's population,
  the 37 system abstentions with `answer_conf` median 0.214).
- Only 3/40 had any hop produce a real answer (trace `answer` field) — the
  reader refuses from hop 0 and the hops do not rescue it. This is a prompt
  problem, not a retrieval or threshold problem.
- 16/40 had recall == 1.0 — the evidence was in the pool and the reader
  still refused.
- Value if it works: even 50% recovery of these 40 rows is ≈ +5 pts EM on
  Test-400 (20/400), unmeasured until a live run.

Dev is a weak instrument for this step, stated up front: the step-2 tuned
dev file has 7 model-unknown rows (step-1 dev had 3), 1 with recall == 1.0,
`answer_conf` median 0.875, `c0` median 1.000, EM 0.0 on those rows.
Recovering half of 7 rows is +3–4 rows of EM — inside the ±3-row live-call
noise band. So the dev gate for this step is about the unknown count and the
accuracy of the recovered rows, with EM as a guardrail, not the verdict.
Test-400 is the judge.

The current prompt is `ANSWER_SYSTEM` in `src/llm/prompts.py`:
"Answer the question using only the context. Reply with only the short
answer, no explanation. If the context does not contain the answer, reply
exactly: unknown". It gives the model one refusal door ("the context does
not contain the answer") and the model walks through it whenever it is
uncertain — including when the context does contain relevant evidence but
not a cleanly stated answer. The two variants below each close that door
differently.

## What Changes — step 3

**A prompt-only experiment on the reader, two pre-registered variants, each
its own Dev-100 BM25 A/B, behind a flag.** `erag.unknown_prompt` selects
the reader system prompt: `"base"` (current `ANSWER_SYSTEM`, default),
`"best_guess"`, or `"cite_first"`. `answer_messages()` takes the variant;
`GROUNDED_ANSWER_SYSTEM` (the step-1 re-read) is untouched. Each variant
runs as its own A/B on top of the step-2 tuned system
(`ground_final_read=true`, `max_claims=8` stay on); each is reported;
the variant that proceeds is decided by the pre-registered selection rule
in design.md, written before any run.

**Variant A — "best_guess" (separate "not in context" from "uncertain"):**
"Answer the question using only the context. Reply with only the short
answer, no explanation. If the context contains evidence relevant to the
question, give your best short answer from that evidence even if you are
not certain. Reply exactly 'unknown' only if the context contains nothing
relevant to the question."

**Variant B — "cite_first" (evidence-first):** "Answer the question using
only the context. First identify the single sentence in the context most
relevant to the question, then reply with only the short answer from that
sentence, no explanation. If no sentence in the context is relevant to the
question, reply exactly: unknown"

**The key risk, stated before running:** these rows refuse with HIGH
confidence (`c0` = 1.0 — all SC samples agree on "unknown"). If a variant
makes the model guess, the guess will likely also be high-confidence
(SC agreement), so the abstention rule (`theta_abs`) will NOT withhold bad
guesses — it is not a safety net here. Reducing the unknown count is only
good if the recovered answers are right. That is why the gate checks
recovered-row accuracy, not just the unknown count.

## Considered alternatives

- **Variant C — presupposition ("The answer is in the context. Find it.").**
  Documented, not run. It would force guesses where retrieval missed gold
  (26/133 wrong Test-400 rows had recall < 1.0) — confident wrong answers
  instead of unknowns. If both A and B fail, C is the next variant to try
  as its own change, with the recovered-row accuracy gate watching it.
- **Changing `theta_abs` to recover these rows.** Wrong tool: these rows
  have `answer_conf` ≈ 0.875, far above any plausible threshold. That is
  step 4's population (system abstentions), not this one.
- **Changing the re-read to recover them.** The re-read triggers on
  'unknown' drafts and re-reads with claims — but if the draft is unknown
  because the reader refused, the re-read (same reader, claims-first)
  usually refuses too. Out of scope; the re-read is untouched.
- **Few-shot examples in the prompt.** Not used: examples would have to
  come from dev/test questions and risk gold leakage into the prompt.

## Non-goals (step-3 scope guard)

- Not a retriever, threshold, graph, NLI, or re-read change. The abstention
  rule stays the arbiter of whether an answer is withheld.
- Not a change to what "unknown" means in the stored rows, and not a change
  to the SC or Fast-Path logic. If a variant makes the model guess
  differently across SC samples, `c0` drops and SC runs more samples —
  that is measured (calls), not tuned here.
- The prompt must not contain the gold answer or any test/dev label — it
  contains only the question and the pool, as today. No few-shot examples.

## Impact

- **Code:** `src/llm/prompts.py` only for the prompt text (two new system
  strings + variant selection in `answer_messages`), plus the flag plumbing
  at the `run_erag` call site (`erag.unknown_prompt`, default `"base"`) and
  the config default. `tests/test_prompts.py` (mocked-LLM tests first).
- **Cache:** new prompt text means new cache keys for the draft calls — the
  dev A/Bs are live-vs-live, NOT replays. The namespace is reused
  deliberately (as in step 2); expect ~±3 EM rows of live-call noise. The
  clean measures are within-run: unknown count and recovered-row accuracy
  from the tuned file itself.
- **Evaluation:** two Dev-100 BM25 A/Bs (one per variant), on top of the
  step-2 tuned system. Gate (per variant, pre-registered): unknown count
  falls by ≥3 rows on dev (7 → ≤4); among rows that change from unknown to
  answered, at least half are correct (recovered-row EM ≥ 0.5); EM not
  below the step-2 tuned dev (0.54); mean calls rise by ≤ 0.5/Q.
  Test-400 is NOT run for this step.
- **Branches:** work on branch `trueadaptive`. Nothing is pushed.

## Follow-up changes (one per tuning step)

- `tune-theta-abs` (step 4) — abstention threshold, dev-selected only.
- `tune-hop2-sc-cap` (step 5) — call-tail cap, cost lever.
- Possible step-3 follow-up if both variants fail: `tune-unknown-prompt-c`
  (Variant C, presupposition).

## References

- Error analysis: `docs/trueadaptive-test400-error-analysis.md` (§2, §5)
- Step-2 change (archived): `openspec/changes/archive/2026-11-09-tune-claim-extraction/`
  — its A/B found the cache-reuse assumption wrong (namespace reuse means
  only changed-prompt calls are live) and its within-run measures are the
  model for this change's within-run measures.
- Reader prompt: `src/llm/prompts.py` (`ANSWER_SYSTEM`, `answer_messages`,
  `GROUNDED_ANSWER_SYSTEM`); call site `src/systems/erag.py` (draft calls).
- Baselines: step-2 tuned dev EM 0.54 / F1 0.6391 / 4.65 calls, 7
  model-unknown rows; step-1 dev EM 0.56, 3 model-unknown rows; Test-400
  BM25 TrueAdaptive v1 EM 0.4750, 40 model-unknown rows.
