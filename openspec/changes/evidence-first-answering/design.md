# Design: H18 — Evidence-first answering

## Mechanism

In `run_erag()` (`src/systems/erag.py`), when
`erag.evidence_first` is true, the hop body is reordered. The
current hop is: draft (Step 2) → SC (Step 3) → claims from the draft
(Steps 4–7) → graph → gaps / Fast Path. The inverted hop is:

1. **Extract passage claims.** `extract_evidence_claims(llm, q, pool,
   tracker, max_claims)` — one LLM call, `EVIDENCE_CLAIM_SYSTEM`,
   Context only, no Answer input. Reuses `_parse()` with
   `default_source="question"`. Full re-extraction every hop: the
   `incremental` reuse of `prev_claims` and the `single_atomic`
   strategy are skipped on the evidence-first path, and the H13
   second pass does not run (passage extraction already covers
   context claims).
2. **Verify first.** `build_graph(claims, pool + mem_passages, nli,
   c0=1.0, ...)` — the provisional graph uses the 1.0 prior, the same
   prior the Fast-Path gate already uses for its provisional graph
   (see Step 3). No draft exists yet, so there is nothing for SC to
   score.
3. **Compose the draft from verified claims only.** If supported
   claims exist, `msgs = compose_answer_messages(q, top_supported)`
   where `top_supported` = supported claims sorted by `eff` desc,
   capped at `erag.max_claims`; one LLM call, temperature 0.0. If no
   supported claim exists, the compose call is skipped and the draft
   is "unknown" (no call spent). The composed answer becomes `draft`
   for the rest of the hop, exactly as the reader's draft is today.
4. **SC on the composed draft.** `_run_sc(llm, q, pool, draft, ...)`
   runs as today (it takes the draft as an argument; the composed
   draft substitutes directly). The graph is then rebuilt with the
   real c0, exactly as the deferred-SC path already rebuilds it.
   `c0_source` stays `"sc"`; the continuation policy receives the
   composed draft as `hop0_draft`, unchanged.

Steps 8–12 then run unchanged: gaps / Fast Path / learned policy,
targeted retrieval, the final re-reads (`ground_final_read` with the
H12 contested trigger on — H15 support-ranked is NOT in the frozen
improved config, so it stays off in both arms and the comparison
tests one variable only), and Step 12 abstention on `ans.eff <
theta_abs`. The re-read triggers will rarely fire, because the draft
is already claim-composed; that is expected, not a bug. If H18
passes, the final system for the Test-400 confirmation is improved +
H15 + H18, judged as a combination there.

`initial_draft` is the hop-0 composed answer; `loop_draft` comparisons
and `trace["answer"]` behave as today. `claim_fallbacks` counts the
same way; a failed passage extraction (empty parse) falls back to a
single atomic claim only if a composed draft exists to state — when
there is no draft, an empty extraction yields no claims and the hop
proceeds with an empty graph (gaps drive retrieval; the row ends
"unknown" if nothing is ever supported).

## Prompts

`EVIDENCE_CLAIM_SYSTEM` (`src/epistemic/claims.py`):

> "List the short factual claims from the Context that answer the
> Question. Each claim is one self-contained sentence that names its
> entities (no pronouns). Mark exactly one claim that states the final
> answer with "answer": true. "depends_on" lists the 0-based indexes
> of EARLIER claims it relies on. Use full names exactly as written
> in the Context. Use at most {n} claims. Return only JSON:
> {{"claims": [{{"text": "...", "answer": false, "depends_on": [],
> "source": "question"}}]}}"

`COMPOSE_SYSTEM` (`src/llm/prompts.py`):

> "Answer only from the verified claims below. Reply with only the
> short answer, no explanation. If none of the claims supports an
> answer, reply exactly: unknown"

`compose_answer_messages(question, claims)` builds the user message
as a "Verified claims:" numbered block + the question. There is
deliberately NO context block — the same restriction as
`extractive_answer_messages()` — but this is the answer path, not a
re-read: the composed answer is the draft the rest of the pipeline
works with.

## Flag-off identity

`erag.evidence_first` defaults to false. When false, the hop body
runs exactly as today, no `evidence_first` field is written, and no
extra LLM call is made — flag-off runs are byte-identical to the
improved system. The `evidence_first` row field is written only when
the flag is on.

## A/B

- Baseline arm: frozen improved config
  (`configs/erag_trueadaptive_improved.yaml`), namespace
  `dev_p27_h18_base_bm25`, run.name `erag_p27_h18_base_dev`.
- Evidence-first arm: same + `erag.evidence_first=true`, namespace
  `dev_p27_h18_evidence_bm25`, run.name
  `erag_p27_h18_evidence_dev`.
- Both arms re-run fresh, Dev-100 BM25, one `--set` per invocation.
  The baseline is re-run fresh (as for H15/H19) — do not reuse an
  older baseline file, the paired comparison must be same-day.
- Verdict: `scripts/phase26_h18_verdict.py` (paired EM/F1/calls +
  McNemar + bootstrap CIs + wrong-answer rate + gold-in-claims rate
  on the evidence-first arm + fixed/broke on rows where the two arms'
  answers differ). Gate: dEM ≥ +0.02 AND wrong-answer rate not up
  AND dcalls ≤ +0.5.
