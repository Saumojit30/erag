# Proposal: Tune-Reader-Grounding — Claim-grounded final read (tuning step 1)

## Status

Draft — prepared 2026-11-09 from `docs/trueadaptive-test400-error-analysis.md`
(committed as `ed154d7`). Branch `trueadaptive`. No code written yet. This is the
first of five tuning changes; each tuning step gets its own OpenSpec change
("for each step use openspec along the way", user 2026-11-09).

**Decisions — resolved (user, 2026-11-09):**
1. Tuning order (from the error analysis): (1) reader/graph, (2) claim
   extraction, (3) model-unknown prompt experiment, (4) theta_abs, (5) hop-2 SC
   cap. This change is step 1 only.
2. Tune on Dev-100 only (BM25, k=3, distractor — the same fixed retriever as the
   Test-400 validation). One Test-400 confirmation run at the END of tuning,
   not after this step.
3. This change is a prompt + post-loop mechanism only. No retriever, threshold,
   belief-graph, or NLI change. No LLM fine-tune, no new dataset, no BGE.

## Why

The Test-400 BM25 error analysis (400 questions, TrueAdaptive v1 EM 0.4750)
found the bottleneck is reasoning, not retrieval:

- 107 of 133 wrong answers had **recall = 1.0** — all gold paragraphs were in the
  pool and the answer was still wrong. Only 26 were retrieval misses.
- Of those 107, **70 had the gold answer inside some trace claim** — the evidence
  was extracted as a verified claim and then the final answer still missed it.
- The final answer is the last `draft` from `llm.chat(answer_messages(q, pool))`
  (`src/systems/erag.py`, Step 2). The reader sees only the raw pool paragraphs
  (up to 12); the belief graph's verified claims are **never passed to the
  reader**. The graph knows the answer (`answer_claim()`), the draft does not.
- Separately, 40 rows end with the draft literally "unknown" while the graph is
  confident (`answer_conf` median 0.875, `c0` median 1.000) — the reader refuses
  from hop 0. A claim-grounded re-read is the only mechanism in this change that
  can also reach those rows.

Expected value: the 70-row bucket is 17.5% of Test-400; recovering even a third
of it is ~+5 pts EM. The 40-row unknown bucket is a second, smaller upside of
the same mechanism.

## What Changes — step 1

**Conditional claim-grounded re-read (Variant A, recommended).** After the hop
loop, before abstention, if the draft is "unknown" OR the draft disagrees with
the graph's answer claim, do ONE extra reader call grounded on the graph's
supported claims (answer-bearing first) plus the pool. If the re-read returns a
non-"unknown" answer it replaces the draft; otherwise the draft stands. The
re-read is recorded per row (`grounded_reread`, trigger reason) so its effect is
measurable from the output file alone. Behind `erag.ground_final_read`
(default false), so v1 behavior is preserved and the A/B is clean.

Disagreement rule (implementable, no new LLM call to decide): the draft agrees
with the answer claim when the normalized draft is a substring of the normalized
claim text (claim text is a sentence, the draft a short answer — e.g. draft "5th
generation" inside claim "The BMW 5 Series is currently in its 5th generation.").
Otherwise they disagree. If there is no answer claim (empty graph — does not
occur in practice; `answer_claim()` falls back to the final claim), no re-read.

Expected cost: +1 call only on triggered rows. Trigger rate on Test-400 would
have been ~27% (70 + 40 of 400) → ~+0.27 calls/Q. Measured on dev in the A/B.

## Considered alternatives

- **Variant B — claims in every draft prompt.** Pass supported claims into each
  hop's draft call. Bigger change, touches every draft, harder to isolate its
  effect from the re-read's. Deferred; revisit only if Variant A underperforms.
- **Variant C — prefer the claim text directly, no extra call.** Use the answer
  claim's text as the answer when it disagrees with the draft. Rejected for now:
  claim text is a sentence, not a short answer, and would need an extraction step
  that is itself a reader call. No saving over Variant A, worse format.
- **Variant D — no change / tune thresholds instead.** Rejected: thresholds
  cannot fix a reader that never sees the claims, and the dev theta_abs sweep
  shows only +1–2 pts (inside noise).

## Non-goals (step-1 scope guard)

- Not a retriever change, not a threshold change (`theta_fast` 0.8, `theta_gap`
  0.6, `theta_abs` 0.4 stay), not a belief-graph or NLI change, not a claim
  extraction change (that is step 2, its own change), not the model-unknown
  prompt experiment (step 3, its own change), not the closed-book gate (v2,
  deferred — the analysis says retrieval is not the bottleneck).
- The re-read must not change the abstention rule: abstention still uses
  `ans.eff < theta_abs` on the (possibly replaced) answer claim. The re-read
  replaces the draft text only; `answer_conf` is recomputed from the graph as
  today. If the re-read answer is "unknown", the draft stands.

## Impact

- **Code:** `src/llm/prompts.py` (new `grounded_answer_messages`), `src/systems/erag.py`
  (post-loop re-read, flagged), `configs/erag_trueadaptive.yaml` (new flag, default
  off in the frozen config — the A/B turns it on via `--set`), `tests/test_erag.py`
  (mocked-LLM tests first).
- **Cache:** the re-read prompt is new text, so its keys cannot collide with any
  existing row. For the dev A/B, the namespace is deliberately **reused**
  (`dev_trueadaptive_v1_bm25`): all non-reread calls are identical prompts, so
  they replay the v1 dev run's cached completions and the A/B isolates exactly
  the re-read's effect (and costs ~27% of a full dev run in new calls). This is a
  reasoned, documented exception to the namespace-rotation rule (Phase C, M3):
  reuse is safe here because the downstream use of the reused completions is
  unchanged — only an additional call is added. The eventual Test-400
  confirmation run uses a FRESH namespace.
- **Evaluation:** Dev-100 BM25 A/B (flag off = v1 file, flag on = tuned file).
  Gate: EM not below v1 dev (0.56) and the 70-row / 40-row buckets (recomputed by
  `scripts/analyze_trueadaptive_test400.py` on the dev file) improve or do not
  worsen; mean calls rise by ≤ 0.5/Q. Test-400 is NOT run for this step.
- **Branches:** work on branch `trueadaptive`. Nothing is pushed.

## Follow-up changes (one per tuning step, created as each step starts)

- `tune-claim-extraction` (step 2) — gold retrieved, never claimed (37 rows).
- `tune-unknown-prompt` (step 3) — reader says "unknown" at high confidence (40 rows).
- `tune-theta-abs` (step 4) — abstention threshold, dev-selected only.
- `tune-hop2-sc-cap` (step 5) — call-tail cap, cost lever.

## References

- Error analysis: `docs/trueadaptive-test400-error-analysis.md` (§2, §3, §5)
- Analysis script: `scripts/analyze_trueadaptive_test400.py`
- Baselines (Test-400, BM25, frozen): TrueAdaptive v1 EM 0.4750 / 4.78 calls;
  IRCoT 0.4200 / 2.54; Balanced 0.4450 / 8.95. Dev-100 BM25 v1: EM 0.56 / 4.58.
- Reader prompt: `src/llm/prompts.py` (`ANSWER_SYSTEM`, `answer_messages`);
  loop: `src/systems/erag.py` (`run_erag`, Steps 2 and 12);
  graph: `src/epistemic/belief_graph.py` (`answer_claim()`).
