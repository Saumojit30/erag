# Design: Tune-Claim-Extraction (tuning step 2)

Source: `docs/trueadaptive-test400-error-analysis.md` (§2, §5) and the
2026-11-09 diagnosis of the 37 never-claimed rows (proposal.md, Why). This
design records exactly one mechanism (Variant A). Variants B/C/D are recorded
as considered alternatives, not built.

## Mechanism 1 — Question-grounded claims in the single extraction call (THIS CHANGE)

- **Location:** `src/epistemic/claims.py` only — `CLAIM_SYSTEM` and `_parse`.
  No change to `run_erag`, the runner, configs, or the reader.
- **Prompt revision:** the system prompt keeps "list the short factual claims
  that must be true for an answer to be correct" and adds a second
  instruction: after the draft-supporting claims, list claims from the
  Context that answer the Question, including any that disagree with the
  given Answer or give a different name, date, or value — using full names
  exactly as written in the Context. The user message is unchanged
  (Question / Answer / Context / JSON:). The JSON schema gains an optional
  `"source"` per claim (`"draft"` or `"question"`).
- **Parsing:** `_parse` preserves `"source"` when present and valid, defaulting
  to `"draft"` when absent (backward compatible with old mock JSON and any
  stored response). The fallback single-atomic claim gets
  `"source": "draft"`. The "exactly one answer-bearing claim" rule is
  unchanged: if no claim is marked, the LAST claim becomes answer-bearing,
  as today. `depends_on` validation is unchanged.
- **Cap:** `max_claims` 5 → 8 in the dev A/B via `--set erag.max_claims=8`
  (config override, no code change), so both claim kinds fit. The code
  default stays 5; the frozen config is updated only if the gate passes
  (tasks.md D.2). NLI verification is local, so extra claims cost no LLM
  calls; the graph grows by at most 3 nodes per hop.
- **Cost:** zero new LLM calls by design. The extraction call already exists
  once per (non-reused) hop; its prompt is longer by one sentence.
- **Logging (per record, for measurement):** no new run_erag fields are
  needed — the claims (with `"source"`) are already in every hop's
  `trace[].graph[]`, and the analysis script reads them from the output file.
  The `--claims` section (tasks.md A.2) reports, for the dev file:
  gold-in-claims rate among full-recall wrong rows (gate measure), the
  share of claims with `source == "question"`, and how many gold-bearing
  claims are question-sourced.
- **Interaction with step 1:** the re-read grounds on supported claims
  (answer-bearing first, then by `eff`) — question-claims that are supported
  enter the re-read prompt unchanged. The re-read trigger (draft vs answer
  claim) is untouched. A question-claim that contradicts the draft's answer
  claim creates a gap through the normal NLI path, which drives retrieval —
  that is the intended effect, not a side effect to suppress.

## Mechanism 2 — Separate draft-free second pass (Variant B) — DEFERRED

- **Status:** NOT built in this change. Recorded so the follow-up starts from
  a written design if Variant A underperforms.
- **Design (kept):** after the normal extraction, if the answer claim is
  contradicted or unresolved — or unconditionally, since no trigger separates
  the rows (proposal.md, Why) — run a second `extract_claims` call with the
  draft replaced by an instruction to answer from the context alone
  (`answer=""` is not enough; the prompt needs a draft-free variant),
  merge both claim lists (dedupe by normalized text), rebuild the graph.
  Cost +1 LLM call per question where it runs. Behind
  `erag.question_claims_second_pass` (default false). Only build if the dev
  A/B shows Variant A does not raise the gold-in-claims rate — i.e. the
  model still anchors on the draft inside one call.

## Mechanism 3 — Fix the incremental freeze (Variant C) — DEFERRED

- **Status:** NOT built in this change.
- **Design (kept):** in `run_erag`, when `claim_strategy == "incremental"`
  and the draft is unchanged but the pool gained new passages since the last
  extraction, re-extract instead of reusing `prev_claims` (or extract from
  the new passages only and merge). Targets the 9/37 freeze rows. Cost: the
  extraction calls that are currently skipped now run (+1 per affected hop).
  Only build as its own change, with its own A/B, so its effect is
  attributable.

## Guardrails

- The revised prompt must not name, hint at, or smuggle the gold answer —
  it asks for context-grounded alternatives in general, the same way the
  current prompt asks for draft-supporting claims in general.
- The `"source"` field is advisory metadata for measurement. Nothing in
  `build_graph`, the gap logic, or abstention may branch on it in this
  change — all claims are verified by NLI identically. (If a later change
  wants to weight question-claims differently, that is a new change.)
- The answer-bearing claim must still be exactly one and must still come
  from the draft-supporting set in the normal case: if the model marks a
  question-claim as the answer claim, `_parse`'s existing fallback (last
  claim) does not correct it — the dev A/B reports how often the
  answer-bearing claim is question-sourced, and the gate fails if it exceeds
  10% of rows (that would mean the extraction is no longer answering the
  draft, and the graph's meaning changes).
- Cache: the extraction prompt is new text (new keys). The dev A/B is
  live-vs-live; the proposal's Impact section records the noise this
  implies (~±3 EM rows at N=100). Do not claim a clean paired comparison.
- No threshold, retriever, graph, NLI, or reader change in this change.
