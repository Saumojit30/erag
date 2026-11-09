# Design: Tune-Unknown-Prompt — Reader prompt experiment (tuning step 3)

## Variants (pre-registered; exact text)

`erag.unknown_prompt` selects the reader system prompt. Default `"base"`.

**base** (current `ANSWER_SYSTEM`, unchanged):
"Answer the question using only the context. Reply with only the short
answer, no explanation. If the context does not contain the answer, reply
exactly: unknown"

**best_guess** — separates "not in context" from "uncertain":
"Answer the question using only the context. Reply with only the short
answer, no explanation. If the context contains evidence relevant to the
question, give your best short answer from that evidence even if you are
not certain. Reply exactly 'unknown' only if the context contains nothing
relevant to the question."

**cite_first** — evidence-first:
"Answer the question using only the context. First identify the single
sentence in the context most relevant to the question, then reply with
only the short answer from that sentence, no explanation. If no sentence
in the context is relevant to the question, reply exactly: unknown"

## Mechanism

`answer_messages(question, paras, variant="base")` selects the system
prompt from a dict keyed by variant name. The `run_erag` draft calls pass
`cfg["erag"].get("unknown_prompt", "base")`. Unknown variant names fall
back to `"base"` (logged, not an error — a typo must not crash a run).
`GROUNDED_ANSWER_SYSTEM` and `grounded_answer_messages` are untouched.

Why these two: they close the refusal door differently. `best_guess`
changes the *rule* for when unknown is allowed (only when nothing is
relevant). `cite_first` changes the *procedure* (locate evidence first,
then answer) without changing the rule. If `best_guess` works and
`cite_first` does not, the rule was the problem; if the reverse, the
procedure was. If both fail, the refusal is not prompt-shaped at this
level and Variant C (presupposition) is the next thing to try, as its
own change.

## Selection rule (pre-registered, before any run)

Each variant has its own gate (tasks.md D.1). A variant proceeds only if
it passes its gate. If both pass, the one that proceeds is the one with
the larger unknown-count reduction on dev; if tied, the simpler prompt
(`best_guess`). If neither passes, the mechanism is dropped and the
change is recorded as a negative result — no third variant is tried
inside this change (Variant C is a separate change). All variants are
reported regardless of outcome.

## Guardrails

- The abstention rule (`theta_abs`, the `abstained` flag) is unchanged and
  stays the arbiter of whether an answer is withheld. Note the risk in
  the proposal: recovered guesses will likely be high-confidence (SC
  agreement), so `theta_abs` will not withhold bad ones — the gate's
  recovered-row accuracy check is the protection, not the threshold.
- The prompt must not name, hint at, or smuggle the gold answer. No
  few-shot examples. The prompt contains only the question and the pool,
  as today.
- No threshold, retriever, graph, NLI, or re-read change in this change.
- Cache: the draft prompt text changes per variant (new keys). The dev
  A/Bs are live-vs-live; the proposal's Impact section records the noise
  this implies (~±3 EM rows at N=100). Do not claim a clean paired
  comparison. The within-run measures (unknown count, recovered-row
  accuracy) are the clean ones.
- Dev has only 7 model-unknown rows: the gate is written around the
  unknown count and recovered accuracy, with EM as a guardrail — do not
  over-read a 1–2 row EM move in either direction.

## Correction note (applies the step-2 lesson)

Step 2's design assumed a field would flow into the trace graph and it
did not. For this change, verify the measurement path *before* the live
A/B: the analyzer's unknown counts come from the row flags (`unknown`,
`abstained`), which the runner already writes — no new trace field is
needed. The A/B analysis adds a small section to the analyzer reporting
unknown count and, for rows that changed from unknown (step-2 tuned dev
file) to answered (variant file), their EM. If that comparison needs a
field the rows do not carry, stop and fix the measurement before running,
do not run and report zeros.
