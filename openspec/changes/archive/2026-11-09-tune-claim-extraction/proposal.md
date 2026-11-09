# Proposal: Tune-Claim-Extraction — Question-grounded claims in the single extraction call (tuning step 2)

## Status

Draft — prepared 2026-11-09 from `docs/trueadaptive-test400-error-analysis.md`
(§2, §5) plus a fresh diagnosis of the 37 never-claimed rows (see Why).
Branch `trueadaptive`. No code written yet. Second of five tuning changes; one
OpenSpec change per tuning step ("for each step use openspec along the way",
user 2026-11-09). Step 1 (`tune-reader-grounding`) is built, validated on
Dev-100 (gate PASS, narrowly), and archived.

**Decisions — resolved (user, 2026-11-09):**
1. Tuning order: (1) reader/graph — done, (2) claim extraction — THIS change,
   (3) model-unknown prompt experiment, (4) theta_abs, (5) hop-2 SC cap.
2. Tune on Dev-100 only (BM25, k=3, distractor). One Test-400 confirmation run
   at the END of tuning, not after this step.
3. This change is a prompt + parser change in claim extraction only. No
   retriever, threshold, belief-graph, NLI, or reader change. No LLM
   fine-tune, no new dataset, no BGE.

## Why

The Test-400 BM25 error analysis found 107 wrong answers with recall == 1.0.
Of those, **37 never had the gold answer extracted as a claim** — the evidence
was in the pool and no trace claim contained it. A fresh diagnosis of those 37
rows (2026-11-09, read-only, from the stored Test-400 file):

- All 37 have a **wrong draft** (0 "unknown"). Claim extraction is conditioned
  on the draft (`extract_claims(llm, q, draft, pool, ...)`), and the claims
  decompose the wrong answer instead of asking what the context says.
- Two sub-patterns in the samples: (a) wrong-answer claims that assert the
  draft ("The descendant of the Red Setter originates from Ireland", gold
  Scotland); (b) abbreviated-name claims where the draft is a short form of
  gold ("Thon Maker" for gold "Thon Marial Maker"; "Sarah Silverman" for gold
  "Sarah Kate Silverman") — the full name is in the pool but the claim uses
  the draft's short form, so the gold string never matches.
- 9/37 had hops > 0 with a frozen draft (incremental reuse: claims are never
  re-extracted when the draft is unchanged, so later hops' new passages are
  never claimed). 11/37 hit the `max_claims: 5` cap at hop 0. 0 fallbacks.
- **No conditional trigger separates the 37.** c0 median is 1.000 for both the
  37 and correct rows (the model is confidently wrong; `c0 < 0.6` fires on
  1/37). The answer claim is SUPPORTED in 18/37 (the pool contains facts for
  the wrong answer too); "not supported" fires on 19/37 but also on 92/190
  correct rows. A conditional second pass would either miss most of the 37 or
  fire on half the correct rows.

Baselines (gold-in-claims rate among full-recall wrong rows): dev 0.333 (6/18
claimed, 12 never), test 0.654 (70/107 claimed, 37 never). The dev rate is
the gate baseline for this change.

## What Changes — step 2

**Question-grounded claims in the single extraction call (Variant A,
recommended).** Revise the claim-extraction prompt (`CLAIM_SYSTEM` in
`src/epistemic/claims.py`) so the one existing extraction call returns, in
addition to the draft-supporting claims, claims from the context that answer
the question — including ones that disagree with the draft or give a
different (fuller) name, date, or value, using full names exactly as written
in the context. Each claim carries a `"source"` field (`"draft"` or
`"question"`); `_parse` preserves it (default `"draft"` for backward
compat). The answer-bearing claim stays the draft's (exactly one, as today),
so the graph's answer claim, abstention, and the step-1 re-read trigger are
unchanged. `max_claims` goes 5 → 8 in the dev A/B (via `--set`, no code
change) so both claim kinds fit; NLI is local, so the extra claims cost no
LLM calls. **Zero new LLM calls by design** — the mechanism is a better
question to the call that already exists.

Expected value: the 37-row bucket is 9.25% of Test-400; the dev gate is the
gold-in-claims rate (0.333 → up) plus EM not falling. How the recovered
claims turn into EM: they feed the graph (contradictions create gaps →
retrieval), and step 1's re-read grounds on supported claims including them.

## Considered alternatives

- **Variant B — separate draft-free second pass.** A second extraction call
  conditioned on question + pool only, merged with the first pass. Cleaner
  separation, but +1 LLM call per question (or per trigger — and no trigger
  separates the rows, see Why). Deferred; the follow-up if Variant A
  underperforms because the model still anchors on the draft inside one call.
- **Variant C — fix the incremental freeze only.** When the pool gains new
  passages on a hop and the draft is unchanged, re-extract instead of reusing
  `prev_claims`. Targets 9/37 rows; a 3-line change, no new call type. Kept
  as a follow-up change, not bundled — bundling it here would blur the A/B
  attribution for Variant A.
- **Variant D — raise max_claims alone.** Targets the 11/37 cap rows, no
  prompt change. Folded into Variant A as the cap half (5 → 8 in the A/B);
  a cap-only ablation is a possible follow-up if the result is ambiguous.

## Non-goals (step-2 scope guard)

- Not a retriever, threshold, graph, NLI, or reader change (step 1's re-read
  is untouched; it benefits from better claims without any change of its own).
- Not the freeze fix (Variant C) or the second pass (Variant B) — both are
  recorded follow-ups, not built here.
- Not a change to what "answer-bearing" means, and not a change to the
  abstention rule. The question-claims are additional evidence; they can
  contradict the draft's answer claim (that is the point — a contradiction
  is a gap, and gaps drive retrieval), but they never replace it as the
  answer claim.
- The extraction prompt must not contain the gold answer or any test/dev
  label — it contains only the question, the draft, and the pool, as today.

## Impact

- **Code:** `src/epistemic/claims.py` only (`CLAIM_SYSTEM`, `_parse` source
  field, fallback claim gets `"source": "draft"`). No change to `run_erag`,
  `prompts.py`, configs, or the runner. `tests/test_claims.py` (mocked-LLM
  tests first) + the analysis script gains a `--claims` section.
- **Cache (step-1 lesson, applied):** the extraction prompt changes, so its
  keys change — the dev A/B is live-vs-live, NOT a replay of v1's cached
  completions. Do NOT assume cache reuse: audit M3 key versioning (v=2)
  already makes old rows unreachable, and the new prompt text makes new
  keys regardless. The A/B comparison therefore carries live-call noise
  (~±3 EM rows at N=100, as measured in step 1). The clean mechanism
  measures are within-run: gold-in-claims rate and question-claim counts
  from the tuned file itself. The eventual Test-400 confirmation (fresh
  namespace, both arms live, paired McNemar) is the judge.
- **Evaluation:** Dev-100 BM25 A/B (flag/config as in tasks.md). Gate:
  EM not below v1 dev (0.56); gold-in-claims rate among full-recall wrong
  dev rows improves on 0.333; mean calls rise by ≤ 0.5/Q (design adds zero
  calls; the cap may shift hop behavior slightly). Test-400 is NOT run for
  this step.
- **Branches:** work on branch `trueadaptive`. Nothing is pushed.

## Follow-up changes (one per tuning step)

- `tune-unknown-prompt` (step 3) — reader says "unknown" at high confidence.
- `tune-theta-abs` (step 4) — abstention threshold, dev-selected only.
- `tune-hop2-sc-cap` (step 5) — call-tail cap, cost lever.
- Possible step-2 follow-ups if Variant A underperforms: `tune-claims-second-pass`
  (Variant B), `tune-claims-refreeze` (Variant C), cap-only ablation.

## References

- Error analysis: `docs/trueadaptive-test400-error-analysis.md` (§2, §5)
- Step-1 change (re-read, archived): `openspec/changes/tune-reader-grounding/`
  — its A/B found the cache-reuse assumption wrong (see Impact) and its
  within-run section-10 estimate (fixed 2, broke 1) is the model for this
  change's within-run measures.
- Extraction: `src/epistemic/claims.py` (`CLAIM_SYSTEM`, `_parse`,
  `extract_claims`); call site `src/systems/erag.py:222`; incremental reuse
  `src/systems/erag.py` (claim_strategy "incremental").
- Baselines: v1 dev BM25 EM 0.56 / 4.58 calls; tuned (step 1) dev EM 0.56 /
  4.75 calls; Test-400 BM25 TrueAdaptive v1 EM 0.4750 / 4.78 calls.
