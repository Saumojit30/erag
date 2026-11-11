# Design: Phase 2.5 H12 — Contested-claim resolution

## Mechanism

At the end of `run_erag` (after the hop loop, in the step-1 re-read
block in `src/systems/erag.py`), the existing triggers run first:

1. `unknown` — draft is "unknown" or empty.
2. `disagree` — draft is not contained in the answer claim's text.

If neither fires, and `erag.contested_resolution` is true, check the new
trigger. If it fires, run one contested re-read and replace the draft
when the re-read returns a non-"unknown" answer. At most one extra LLM
call per question, and only when a trigger fires.

## Trigger (pure function, no LLM)

`find_contested(claims, draft)` — `claims` are belief-graph claim dicts
(the `trace` JSON shape: `text`, `status`, `source`, `answer_bearing`,
`eff`); `draft` is the loop draft string. Normalization is the repo
`normalize_answer` (lowercase, strip articles/punctuation) plus the
analyzer's `[^a-z0-9 ]` collapse used in the stored-data check, so the
trigger the code computes matches the trigger the diagnosis measured.

- Returns `None` when the draft normalizes to empty/"unknown".
- *Agreeing* claims: `status == "supported"`, `source == "draft"`, and
  the normalized draft is a substring of the normalized claim text.
- *Disagreeing* claims: `status == "supported"`,
  `source == "question"`, and the normalized draft is NOT a substring
  of the normalized claim text.
- Contested iff both lists are non-empty. Returns
  `(agreeing, disagreeing)` sorted by `eff` descending.

Design note: the disagreeing claims are question-sourced by
construction (step 2's extractor lists context claims that answer the
question, including ones that disagree with the draft). T5 was measured
and rejected: requiring the disagreeing claim to be answer-bearing
covers 0/53 target rows.

## Prompt

New builder `contested_answer_messages(question, agreeing, disagreeing,
paras)` in `src/llm/prompts.py`, with system prompt
`CONTESTED_ANSWER_SYSTEM`: the verified claims disagree — some support
one answer, others a different one — decide which answer is best
supported by the context, reply with only the short answer, or exactly
`unknown` if neither is supported. The user message lists the two sides
under separate headings ("Claims supporting the current answer" /
"Claims supporting a different answer"), then the context block, then
the question. The grounded set is agreeing + disagreeing claims, capped
at `max_claims` (8 in the tuned config), agreeing side first, each side
ordered by `eff` descending.

## Wiring and row fields

- Flag: `erag.contested_resolution`, default `False` (code default via
  `.get("contested_resolution", False)`; no base-config change needed —
  the flag is off unless an experiment config sets it).
- In the final-read block, after the existing trigger computation:
  `elif e.get("contested_resolution", False): contested =
  find_contested(graph.to_json(), draft)`; if contested, run the
  contested re-read through the same `llm.chat(..., temperature=0.0)`
  path, set `reread_trigger = "contested"`, `grounded_reread = True`,
  `reread_answer = <reply>`, and replace the draft when the reply is
  not "unknown"/empty.
- Output fields (only when `ground_final_read` is on, same as step 1):
  `grounded_reread`, `reread_trigger`, `reread_answer`, plus new
  `contested` (bool) — so the analyzer's `--reread` section and a
  trigger-rate count can read it off stored rows. Flag-off runs produce
  byte-identical records to the tuned system (no new fields, no new
  calls).

## A/B (gate, smoke test)

- Baseline: frozen tuned config, Dev-100 BM25, fresh namespace
  `dev_p25_h12_base_bm25`.
- Contested arm: same config + `erag.contested_resolution=true`, fresh
  namespace `dev_p25_h12_contested_bm25`.
- Gate: EM gain ≥ +0.02 at ≤ +0.5 calls/Q vs baseline; on triggered
  rows, fixes > breaks. Both arms re-run fresh (no comparison against
  the Nov-9 policy file). Verify `cache_hits` before believing the
  paired comparison.
