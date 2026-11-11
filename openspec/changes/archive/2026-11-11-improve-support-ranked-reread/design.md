# Design: Support-ranked final re-read (Phase 2.6 H15)

## Mechanism

1. **Pure trigger** — `find_top_supported_rival(claims, draft, k=3)` in
   `src/systems/erag.py`, dict-based on the trace-JSON claim shape
   (`text`, `status`, `eff`), same `normalize_answer` as H12. Takes
   supported claims, sorts by `eff` descending (stable sort — ties keep
   graph insertion order), returns the top-k iff the normalized draft
   appears in none of them and at least one supported claim exists.
   Draft "unknown"/empty → `None` (the unknown trigger already handles
   those rows; the guard keeps the function total).
2. **Prompt** — `SUPPORT_RANKED_SYSTEM` +
   `support_ranked_answer_messages(question, top_claims, pool)` in
   `src/llm/prompts.py`. The user message lists ONLY the top-k claims
   (numbered), then the context block, then the question. The system
   prompt says: answer only from these verified claims; reply with only
   the short answer; if none supports an answer, reply exactly `unknown`.
3. **Wiring** — in the final-read block of `run_erag`, as an
   independent check AFTER the unknown/disagree/contested `if`/`elif`
   chain, gated on `reread_trigger is None` — NOT an `elif` on the
   contested branch: that branch takes its arm whenever its flag is on
   (even when the graph is not contested), which would make this
   trigger unreachable in the H15 A/B arm where both flags are on. On
   a hit it sets `reread_trigger = "support_ranked"`,
   `support_ranked = True`, and builds the messages. The existing
   re-read call (`llm.chat(..., temperature=0.0)`) then runs once; the
   draft is replaced only on a non-unknown reply, exactly as the other
   triggers. Row field `support_ranked` (bool) is recorded only when
   the flag is on, mirroring `contested`.
4. **Config** — `erag.support_ranked_reread` (default false),
   `erag.support_ranked_top_k` (default 3). The H15 A/B arm is the
   improved config + `erag.support_ranked_reread=true`.

## Threats to validity

- **Same reader, same mistake.** The re-read is the same Groq model
  that produced the wrong draft; shown the top-3 claims it may still
  repeat the draft. The gate measures fixes vs breaks on triggered rows
  on dev — if it does not fix more than it breaks, the mechanism is
  dropped, no matter what the headroom analysis suggested.
- **Top-3 may be background claims.** The top-3 by eff can include
  claims that state background facts rather than answers. The prompt
  says to answer only from the claims; if none supports an answer the
  reply must be `unknown`, which keeps the draft. The A/B's break count
  on triggered rows catches a systematic failure here.
- **Eff ties.** Many claims share eff values (conf clusters); the stable
  sort keeps graph insertion order, so the top-3 is deterministic for a
  given graph but order-sensitive. This is a property of the existing
  eff computation, not new machinery; the dev A/B is run on the same
  deterministic ranking.
- **Substring containment.** The trigger matches the normalized draft
  as a substring of claim text. Short answers ("Paris") can false-match
  inside other words; the same normalization is used by H12 and the
  diagnosis, and the trigger's selectivity was measured on stored data
  (24/53 vs 39/180). A false trigger costs at most one extra call and
  the re-read still has to beat the draft to change anything.
- **Abstention unchanged.** The re-read replaces the draft before the
  abstention check, so a re-read answer is still subject to
  `theta_abs` — no abstention-rule change, no new way to dodge it.
- **Cache.** The re-read is a new prompt shape, so it cannot hit any
  existing cache entry; the A/B uses fresh namespaces and the verdict
  script verifies `cache_hits` before believing the comparison.
