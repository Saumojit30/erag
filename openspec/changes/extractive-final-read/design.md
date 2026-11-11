# Design: H19 — Extractive final read

## Mechanism

In `run_erag()`'s final-read block (`src/systems/erag.py`), the
extractive branch is checked FIRST, before the unknown/disagree/
contested/support-ranked triggers. When `erag.extractive_final_read`
is true (and `ground_final_read` is true, and supported claims exist):

- `reread_trigger = "extractive"`, `extractive = True`.
- `msgs = extractive_answer_messages(q, top_supported)` where
  `top_supported` = supported claims sorted by `eff` desc, capped at
  `erag.max_claims` (default 5 in the frozen configs; 8 in the improved
  config — the cap follows the config, no new knob).
- The shared single re-read call runs (`llm.chat(..., temperature=0.0)`);
  the draft is replaced only on a non-unknown reply, exactly as the
  other re-reads behave.

The other triggers must not also fire on the same row. The existing
chain is guarded so that:

- the grounded-messages branch (`if reread_trigger is not None:`)
  becomes `if reread_trigger is not None and msgs is None:` — the
  extractive branch already set `msgs`, so it is not overwritten;
- the contested branch becomes `elif reread_trigger is None and
  e.get("contested_resolution", False):` — it cannot overwrite the
  extractive messages;
- the H15 independent check already guards on `reread_trigger is None`.

## Prompt

`EXTRACTIVE_SYSTEM` (`src/llm/prompts.py`):

> "Answer only from the verified claims below. Reply with only the
> short answer, no explanation. If none of the claims supports an
> answer, reply exactly: unknown"

`extractive_answer_messages(question, claims)` builds the user
message as a "Verified claims:" numbered block + the question. There
is deliberately NO context block — that is the difference from
`support_ranked_answer_messages()`, whose message includes the full
context. The restriction is the mechanism: the reader cannot fall back
to raw context.

## Flag-off identity

`erag.extractive_final_read` defaults to false. When false, the new
branch is never entered, `msgs` stays None until the existing chain
sets it, and no `extractive` field is written — flag-off runs are
byte-identical to the improved system. The `extractive` row field is
written only when the flag is on.

## A/B

- Baseline arm: frozen improved config
  (`configs/erag_trueadaptive_improved.yaml`), namespace
  `dev_p27_h19_base_bm25`, run.name `erag_p27_h19_base_dev`.
- Extractive arm: same + `erag.extractive_final_read=true`, namespace
  `dev_p27_h19_extractive_bm25`, run.name
  `erag_p27_h19_extractive_dev`.
- Both arms re-run fresh, Dev-100 BM25, one `--set` per invocation.
- Verdict: `scripts/phase26_h19_verdict.py` (paired EM/F1/calls +
  McNemar + bootstrap CIs + wrong-answer rate + trigger rate).
  Gate: dEM ≥ +0.02 AND wrong-answer rate not up AND dcalls ≤ +0.5.
