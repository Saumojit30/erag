# H18 — Evidence-first answering (Phase 2.7, the full inversion)

## Why

The codebase analysis (`docs/architecture-analysis-hallucination.md`,
2026-11-11) shows the pipeline is draft-first: the draft is written
before any verification exists, claims are extracted FROM the draft,
and verification is advisory — it can veto (abstain) or trigger a
narrow re-read, never construct the answer. The measured failure: 53
gold-in-claims full-recall wrong rows on the tuned Test-400 run, 34/53
with the final answer inside a WRONG supported claim, answered at mean
confidence 0.94. The draft chooses the answer and the machinery defends
it.

H19 tested the cheap version of the fix — restrict the final reader to
verified claims — and it FAILED (dEM −0.0100, dcalls +0.60, fixed 3
broke 5): the reader still composes from claim sentences, and when the
gold claim is not ranked first the re-read picks a wrong supported
claim. H19's lesson is that the bottleneck is what gets extracted and
verified, not what the reader is allowed to see. This change is the
architectural version: remove the draft entirely. Claims are extracted
FROM THE PASSAGES, verified, and the answer is composed ONLY from
verified claims. There is no draft to defend.

H15 (support-ranked re-read) is the patch version of the same idea: it
re-reads grounded on the top-3 supported claims, but only when its
trigger fires (9/100 rows on dev) and only at the end. H18 applies the
idea to every row, from the first hop.

## What Changes

- New flag `erag.evidence_first` (default false). When on, each hop
  is inverted: NO draft call. Instead, candidate answer-bearing claims
  are extracted from the passages (`extract_evidence_claims()`), the
  graph is built and verified exactly as today, and the hop's draft is
  composed from the supported claims only (`compose_answer_messages()`),
  with NO context block. If no supported claim answers the question,
  the composed draft is "unknown" and the loop continues on gaps as
  today. SC, the continuation policy, the Fast Path, abstention, and
  the final re-reads all run unchanged on the composed draft.
- New prompt `EVIDENCE_CLAIM_SYSTEM` + `extract_evidence_claims()` in
  `src/epistemic/claims.py`: list short factual claims from the
  Context that answer the Question, each self-contained, naming its
  entities, exactly one marked as the answer claim. No Answer input —
  there is no draft to anchor on. Reuses the existing `_parse()`
  with `default_source="question"`.
- New prompt `COMPOSE_SYSTEM` + `compose_answer_messages()` in
  `src/llm/prompts.py`: "Answer only from the verified claims below",
  claims block only, no context — the same restriction as
  `EXTRACTIVE_SYSTEM`, but as the answer path, not a re-read.
- Row field `evidence_first` (bool) recorded only when the flag is on.
  Flag-off runs are byte-identical to the improved system.
- Evidence-first forces full re-extraction of passage claims each hop
  (the `incremental` claim-reuse optimisation is draft-anchored and
  does not apply: new pool passages must be able to contribute answer
  claims). `single_atomic` and the H13 second pass do not run when
  evidence-first is on — the passage extraction already covers
  context claims.
- No change to retrieval, SC, the continuation policy, abstention
  thresholds, or the NLI verifier. Per hop, the draft call (1) + the
  claims call (1) are replaced by a passage-claims call (1) + a
  compose call (1): the LLM-call count per hop is unchanged by
  construction, so any dcalls comes from different continuation
  decisions, not from the mechanism itself.

## H18 (pre-registered 2026-11-11, before any new run; decision set amended 2026-11-13, before the run)

On Dev-300 BM25, the evidence-first arm raises EM ≥ +0.02 vs the
improved-system baseline at ≤ +0.5 calls/Q AND does not raise the
wrong-answer rate. Exploratory. Gate = all three legs. Extend rule
(pre-registered 2026-11-13, before the run): if dEM lands in
[+0.01, +0.04] with the 95% CI straddling 0, the verdict is
AMBIGUOUS and the A/B extends to the full Dev-500 instead of calling
it. If the gate fails, the mechanism stays OFF and the round moves
to H20/H21 (joint verification / reranking — the ranking of the
supported set, which H19 showed is the bottleneck, is what those
attack), not to another reader restriction.

## Threats to validity

- The passage-claim extractor may miss the gold sentence. The 33
  never-claimed Test-400 rows are exactly this failure, and in
  evidence-first mode there is no draft to fall back on — extractor
  coverage IS the mechanism, measured by the A/B (gold-in-claims rate
  on the evidence-first arm is reported alongside EM).
- The `max_claims` cap (8 in the improved config) binds harder here:
  the extractor must spend its budget on answer-bearing claims, not
  on background facts. A cap miss loses the gold claim for the row.
- The compose step can still pick a wrong supported claim (H19's
  lesson). H18 changes what claims exist, not their ranking; if the
  top supported claim is wrong, the composed answer inherits it. The
  verdict script reports fixed/broke on rows where the two arms'
  answers differ, so this shows up directly.
- Abstention may rise: when no supported claim answers the question
  the system says "unknown" instead of guessing. That is correct
  behaviour for the hallucination objective and costs EM on rows the
  current system guesses right — the wrong-answer-rate leg is the
  more sensitive measure here, and the gate requires EM up as well.
- Dev-300 (N=300) is a decision set, not a verdict: the gate is
  directional (dEM ≥ +0.02) and the extend rule applies — if dEM
  lands in [+0.01, +0.04] with the 95% CI straddling 0, the A/B
  extends to the full Dev-500 instead of calling it. Dev-100 (N=100)
  was the original decision set; it was abandoned 2026-11-13, before
  the run, because its CI (±0.04–0.07) cannot resolve a +0.02 effect.
  The Test-400 confirmation judges the mechanism as part of the final
  system, never alone.
