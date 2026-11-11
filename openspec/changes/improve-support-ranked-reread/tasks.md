# Tasks: Phase 2.6 H15 — Support-ranked final re-read

## 0. OpenSpec change (before any code)

- [x] 0.1 Create `openspec/changes/improve-support-ranked-reread/` with
  `proposal.md`, `design.md`, `tasks.md` (this file) — drafted
  2026-11-11 from `docs/phase26-beat-ircot-plan.md`. H15 pre-registered
  2026-11-11; headroom measured on stored tuned Test-400 rows (gold in
  top-3 supported claims on 48/53 target rows; trigger fires 24/53 vs
  39/180 correct rows).
- [x] 0.2 Validate with the local CLI:
  `~/workspace/tools/openspec/node_modules/.bin/openspec validate --all`
  — must pass before the A/B. Validated 2026-11-11: 14/14 passed.

## A. Tests first (no production change yet)

- [x] A.1 In a new `tests/test_support_ranked_reread.py`, add
  pure-function tests for `find_top_supported_rival`: draft in top-3 →
  None; draft absent from top-3 → returns top-3 sorted by eff desc;
  no supported claims → None; draft "unknown"/empty → None; k=5
  variant. Tests must fail before the implementation lands.
- [x] A.2 Add a prompt-builder test for
  `support_ranked_answer_messages`: only the top claims listed, question
  and context present, system prompt says answer from the claims only.
- [x] A.3 Add a mocked-LLM test: rival graph + flag on → exactly one
  extra call, `reread_trigger == "support_ranked"`, draft replaced by
  the re-read answer; flag off → no extra call, no new fields;
  re-read returns "unknown" → draft kept; draft backed by top-3 → no
  extra call.

## B. Implementation

- [x] B.1 Add `find_top_supported_rival()` to `src/systems/erag.py`
  (pure, dict-based, same normalization as H12).
- [x] B.2 Add `SUPPORT_RANKED_SYSTEM` +
  `support_ranked_answer_messages()` to `src/llm/prompts.py`.
- [x] B.3 Wire the fourth trigger into the final-read block in
  `src/systems/erag.py` behind `erag.support_ranked_reread`
  (default False, `erag.support_ranked_top_k` default 3); record
  `support_ranked` on the row when the flag is on.
- [x] B.4 Full suite 2026-11-11: 186 passed / 1 known pre-existing
  failure (`test_retry_exhaustion_raises_runtime_error`); H15 adds 10
  new tests, all passing.

## C. Dev-100 A/B (gate = smoke test; needs Groq key)

- [ ] C.1 Baseline: improved system (tuned + contested + eager SC),
  Dev-100 BM25, fresh namespace `dev_p26_h15_base_bm25`, output
  `results/trueadaptive/erag_p26_h15_base_dev.jsonl`.
- [ ] C.2 H15 arm: same + `erag.support_ranked_reread=true`, fresh
  namespace `dev_p26_h15_ranked_bm25`, output
  `results/trueadaptive/erag_p26_h15_ranked_dev.jsonl`. One `--set`
  per invocation (repeated `--set` overwrites).
- [ ] C.3 Verify `cache_hits` on both files; compute EM/F1/calls-Q
  paired (McNemar) + trigger rate + fixes/breaks on triggered rows.
  Gate: EM gain ≥ +0.02 at ≤ +0.5 calls/Q; fixes > breaks on
  triggered rows.
- [ ] C.4 Record in master plan §12 + assumptions-vs-outcomes +
  hypotheses status (H15 verdict). If the gate fails, the mechanism
  is dropped — no further tuning on dev.

## D. Close-out

- [ ] D.1 Commit on `trueadaptive` (proper message, author
  Saumojit30). Do not push (PAT pending — separate blocked item).
- [ ] D.2 Archive the change (`openspec archive -y`) and re-validate.
