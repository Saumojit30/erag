# Design: Tune-Reader-Grounding (tuning step 1)

Source: `docs/trueadaptive-test400-error-analysis.md` (§2, §3, §5). This design
records exactly one mechanism (Variant A, conditional claim-grounded re-read).
Variants B/C are recorded as considered alternatives, not built.

## Mechanism 1 — Conditional claim-grounded re-read (THIS CHANGE)

- **Location:** end of `run_erag` in `src/systems/erag.py`, after the hop loop,
  before Step 12 (abstention). New prompt helper `grounded_answer_messages()`
  in `src/llm/prompts.py`. Behind `erag.ground_final_read` (default false).
- **Trigger — exactly one of:**
  1. The draft is "unknown" (normalized, case-insensitive), OR
  2. The draft disagrees with the graph's answer claim: the normalized draft is
     NOT a substring of the normalized answer-claim text. Normalization is the
     repo's `normalize_answer` (same function the loop already uses to compare
     drafts). If the graph has no claims, no re-read (defensive; does not occur
     — `answer_claim()` falls back to the final claim).
  The trigger is computed from stored values only (draft, graph) — no LLM call
  to decide.
- **Re-read prompt:** system message: answer using the verified claims first,
  then the context; reply with only the short answer, no explanation; if neither
  the claims nor the context contain the answer, reply exactly `unknown`.
  User message: a "Verified claims" block (supported claims only,
  `status == "supported"`, answer-bearing first, then by `eff` descending,
  capped at 5 — the same `max_claims` bound the extraction already uses),
  followed by the same context block and question `answer_messages` already
  builds. Temperature 0.0, same as every draft call.
- **Replacement rule:** if the re-read returns a non-"unknown" answer, it
  replaces the draft (the returned `draft` field becomes the re-read answer,
  and the original draft is kept in the trace's last hop entry for inspection).
  If the re-read returns "unknown", the original draft stands. The re-read
  never changes the pool, the graph, or `c0`.
- **Abstention interaction:** unchanged. Step 12 still withholds the answer iff
  `ans.eff < theta_abs` (0.4), where `ans` is `graph.answer_claim()` as today.
  The re-read replaces draft text only; `answer_conf` is recomputed from the
  graph as today. A re-read answer that the graph does not support can still be
  abstained on — that is the existing safety net doing its job.
- **Logging (per record, for measurement):** `grounded_reread: bool`,
  `reread_trigger: "unknown" | "disagree" | null`, `reread_answer: str | null`.
  The analysis script (`scripts/analyze_trueadaptive_test400.py`) recomputes
  the 70-row and 40-row buckets from the output file; no new analysis tooling
  is needed, but the script should gain a `--reread` summary (trigger rate,
  re-read EM, rows fixed/broken by the re-read) — small addition, same file.
- **Cost:** +1 LLM call per triggered row, 0 otherwise. Expected trigger rate
  ~27% on Test-400 (70 + 40 of 400) → ~+0.27 calls/Q. Measured exactly on dev.
- **Flag:** `erag.ground_final_read: bool`, default false. The frozen
  `configs/erag_trueadaptive.yaml` does NOT set it (v1 behavior preserved);
  the dev A/B turns it on via `--set erag.ground_final_read=true`.

## Mechanism 2 — Claims in every draft prompt (Variant B) — DEFERRED

- **Status:** NOT built in this change. Recorded so step 1's follow-up starts
  from a written design if Variant A underperforms.
- **Design (kept):** pass the previous hop's supported claims into each draft
  call's prompt (same "Verified claims" block as Mechanism 1). Hop 0 has no
  graph yet and stays pool-only. Expected effect: same grounding benefit, but
  applied to every hop instead of once at the end — more calls affected, harder
  to attribute. Only build if the dev A/B shows Variant A recovering < 1/3 of
  the 70-row bucket.

## Mechanism 3 — Prefer claim text directly (Variant C) — REJECTED

- Claim text is a sentence, not a short answer; using it directly would break
  the short-answer format and the EM comparison, and extracting a short answer
  from it is itself a reader call. No saving over Mechanism 1. Not built.

## Guardrails

- The re-read prompt must not contain the gold answer or any test/dev label —
  it contains only the question, the graph's own claims, and the pool. Same
  information the system already had; only the presentation changes.
- The trigger rule must be deterministic and logged; a re-read that fires on
  every row is a bug, not a feature — the dev A/B reports the trigger rate and
  the gate fails if it exceeds 40% on dev.
- Cache: re-read prompts are new text (new keys). Dev A/B reuses namespace
  `dev_trueadaptive_v1_bm25` deliberately (see proposal.md, Impact) so the A/B
  isolates the re-read. Test-400 confirmation (after all tuning steps) uses a
  fresh namespace.
- No threshold, retriever, graph, or NLI change in this change. If the dev A/B
  shows the re-read helps only via the unknown rows, that is still a pass —
  the mechanism is one change with two buckets, and the buckets are reported
  separately.
