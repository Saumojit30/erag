# Design: Phase 2.5 H13 — Extraction recall, second pass

## Mechanism

In `run_erag` (`src/systems/erag.py`), after the hop-0 claim extraction
(the `extract_claims` call in the hop loop), when
`erag.second_extraction` is true and the strategy is not
`single_atomic`: run `extract_claims_second_pass` and merge its output
into the claim list before `build_graph`. Hop 0 only — 25/33 diagnosed
never-claimed rows stayed at hop 0 (dev 7/8), and later hops already
re-extract incrementally.

## Second-pass prompt

New function `extract_claims_second_pass(llm, question, draft, paras,
existing_claims, tracker, max_claims)` in `src/epistemic/claims.py`,
with system prompt `SECOND_PASS_SYSTEM`: "You already listed claims
about this question. List ADDITIONAL short factual claims from the
Context that bear on the Question and are NOT already covered by the
claims below — especially claims stating a name, date, or value that
could be the answer. Each claim is one self-contained sentence that
names its entities (no pronouns). Mark exactly one claim that states
the final answer with \"answer\": true. Return only JSON:
{\"claims\": [{\"text\": \"...\", \"answer\": false, \"depends_on\": [],
\"source\": \"question\"}]}". The user message carries the question, the
draft, the existing claims (as a numbered list), and the context block.
Parsing reuses `_parse` (same JSON shape, same max_claims cap). New
claims carry `source: "question"` when the model omits it — the second
pass only ever adds context claims, so "question" is the correct
default; an explicit `"draft"` value from the model is kept as-is.

## Merge (pure function, no LLM)

`merge_claims(existing, additional)` in `src/epistemic/claims.py`:
dedupe by `normalize_answer(text)` — an additional claim whose
normalized text matches an existing claim is dropped. Keeps existing
order, appends new claims in returned order. No total cap beyond the
two passes' own caps (≤ 2 × max_claims). Returns the merged list.

## Wiring and row fields

- Flag: `erag.second_extraction`, default `False` (code default via
  `.get("second_extraction", False)`). The A/B config sets it true.
- In the hop loop, right after the `extract_claims` assignment (and
  only when `hop == 0`): if the flag is on, run the second pass and
  replace `claims` with the merged list; set `prev_claims` to the
  merged list so incremental reuse at hop 1+ sees the full set.
- Output fields (only when the flag is on, so flag-off runs stay
  byte-identical to the H12-improved system): `second_pass_added`
  (int, new claims merged in) and `second_extraction` (bool, the pass
  ran). Both are recorded on every row when the flag is on, including
  0-added rows.

## A/B (gate, smoke test)

- Baseline: frozen tuned config + `erag.contested_resolution=true`
  (the H12-improved system), Dev-100 BM25, fresh namespace
  `dev_p25_h13_base_bm25`. (Not the stored H12 contested file — both
  arms re-run fresh, per the paired-run discipline.)
- H13 arm: same + `erag.second_extraction=true`, fresh namespace
  `dev_p25_h13_second_bm25`.
- Gate: gold-in-claims rate among full-recall wrong rows rises vs the
  fresh paired baseline; EM does not fall; calls/Q rise ≤ +1.0.
  Verify `cache_hits` before believing the paired comparison.
