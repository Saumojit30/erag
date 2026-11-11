# H19 — Extractive final read (Phase 2.7, first mechanism)

## Why

The codebase analysis (`docs/architecture-analysis-hallucination.md`,
2026-11-11) shows the pipeline is draft-first: the draft is written
before any verification exists, claims are extracted FROM the draft, and
verification is advisory — it can veto (abstain) or trigger a narrow
re-read, never construct the answer. The measured failure: 53
gold-in-claims full-recall wrong rows on the tuned Test-400 run, 34/53
with the final answer inside a WRONG supported claim, answered at mean
confidence 0.94. The draft chooses the answer and the machinery defends
it.

H15 (support-ranked re-read) is the patch version of the fix: it
re-reads grounded on the top-3 supported claims, but only when its
trigger fires, and its prompt still includes the full context block —
so the reader can still answer from raw context, not from the claims.
This change is the architectural version: the final answer comes ONLY
from verified claims.

## What Changes

- New flag `erag.extractive_final_read` (default false). When on (and
  `ground_final_read` is on), the final read is a claims-only re-read:
  the reader sees the supported claims sorted by `eff` (cap
  `max_claims`) and NO context block. It replaces the other re-read
  triggers (unknown / disagree / contested / support-ranked) for that
  row — one final read, not two.
- New prompt `EXTRACTIVE_SYSTEM` + `extractive_answer_messages()` in
  `src/llm/prompts.py`: "Answer only from the verified claims below",
  claims block only, no context.
- Row field `extractive` (bool) recorded only when the flag is on.
  Flag-off runs are byte-identical to the improved system.
- No change to retrieval, SC, the continuation policy, abstention, or
  the NLI verifier. The cost is at most +1 LLM call per row (the
  re-read), same as the other re-reads.

## H19 (pre-registered 2026-11-11, before any new run)

On Dev-100 BM25, the extractive arm raises EM ≥ +0.02 vs the
improved-system baseline at ≤ +0.5 calls/Q AND does not raise the
wrong-answer rate. Exploratory. Gate = all three legs. If the gate
fails, the mechanism stays OFF and the round moves to H18 (the full
inversion), which this test informs either way.

## Threats to validity

- The claims-only re-read can only pick among claims the extractor
  produced. If the gold answer was never extracted as a claim (the 33
  never-claimed rows on Test-400), the extractive read cannot recover
  it — it can only stop the system answering from a wrong claim. EM
  gains therefore come from fixing wrong answers, not from recovering
  unextracted ones; the wrong-answer-rate leg is the more sensitive
  measure here.
- The extractor's claims are sentences, not entities. The re-read
  must still compose a short answer from a claim sentence; a claim
  that states the answer in words the reader cannot reduce to the
  gold entity will not fix the row. This is a property of the
  mechanism, measured by the A/B, not assumed away.
- Dev-100 (N=100) is a smoke test, not a verdict: the gate is
  directional (dEM ≥ +0.02, fixes > breaks on triggered rows). The
  Test-400 confirmation judges the mechanism as part of the final
  system, never alone.
