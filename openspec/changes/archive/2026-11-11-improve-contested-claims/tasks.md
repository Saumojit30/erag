# Tasks: Phase 2.5 H12 — Contested-claim resolution

## 0. OpenSpec change (before any code)

- [x] 0.1 Create `openspec/changes/improve-contested-claims/` with
  `proposal.md`, `design.md`, `tasks.md` (this file) — drafted
  2026-11-11 from `docs/phase25-improvement-diagnosis.md`. H12
  pre-registered 2026-11-11; trigger redefined T1 → T2 by dated
  clarification in the proposal (T1 covers 2/53 target rows on
  stored data).
- [x] 0.2 Validate with the local CLI:
  `~/workspace/tools/openspec/node_modules/.bin/openspec validate --all`
  — must pass before the A/B.

## A. Tests first (no production change yet)

- [x] A.1 In `tests/test_erag.py` (or a new
  `tests/test_contested_resolution.py`), add pure-function tests for
  `find_contested`: contested graph (draft-supported agrees +
  question-supported disagrees) → returns both sides sorted by eff;
  draft "unknown"/empty → None; no agreeing claim → None; no
  disagreeing claim → None; agreeing claim unresolved (not
  supported) → None. Tests must fail before the implementation
  lands.
- [x] A.2 Add a prompt-builder test for `contested_answer_messages`:
  both sides listed under separate headings, question and context
  present.
- [x] A.3 Add a mocked-LLM test: contested graph + flag on → exactly
  one extra call, `reread_trigger == "contested"`, draft replaced by
  the re-read answer; flag off → no extra call, no new fields;
  re-read returns "unknown" → draft kept.

## B. Implementation

- [x] B.1 Add `find_contested()` to `src/systems/erag.py` (pure,
  dict-based, same normalization as the diagnosis script).
- [x] B.2 Add `CONTESTED_ANSWER_SYSTEM` +
  `contested_answer_messages()` to `src/llm/prompts.py`.
- [x] B.3 Wire the third trigger into the final-read block in
  `src/systems/erag.py` behind `erag.contested_resolution`
  (default False); record `contested` on the row when the flag is on.
- [x] B.4 Full suite: `tests/` must stay 159 passed / 1 known
  pre-existing failure (`test_retry_exhaustion_raises_runtime_error`).

## C. Dev-100 A/B (gate = smoke test)

- [x] C.1 Baseline: frozen tuned config, Dev-100 BM25, fresh
  namespace `dev_p25_h12_base_bm25`, output
  `results/trueadaptive/erag_p25_h12_base_dev.jsonl`.
- [x] C.2 Contested arm: same + `erag.contested_resolution=true`,
  fresh namespace `dev_p25_h12_contested_bm25`, output
  `results/trueadaptive/erag_p25_h12_contested_dev.jsonl`. One
  `--set` per invocation (repeated `--set` overwrites).
- [x] C.3 Verify `cache_hits` on both files; compute EM/F1/calls-Q
  paired (McNemar) + trigger rate + fixes/breaks on triggered rows.
  Gate: EM gain ≥ +0.02 at ≤ +0.5 calls/Q; fixes > breaks on
  triggered rows.
- [x] C.4 Record in master plan §12 + assumptions-vs-outcomes +
  hypotheses status (H12 verdict). If the gate fails, the mechanism
  is dropped — no further tuning on dev.

## D. Close-out

- [x] D.1 Commit on `trueadaptive` (proper message, author
  Saumojit30). Do not push (PAT pending — separate blocked item).
- [ ] D.2 Archive the change (`openspec archive -y`) and re-validate.
