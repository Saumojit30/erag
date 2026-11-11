# Tasks: Phase 2.7 H19 — Extractive final read

## 0. OpenSpec change (before any code)

- [x] 0.1 Create `openspec/changes/extractive-final-read/` with
  `proposal.md`, `design.md`, `tasks.md` (this file) — drafted
  2026-11-11 from `docs/architecture-analysis-hallucination.md`.
  H19 pre-registered 2026-11-11 in the master plan §4.7; the A/B is
  Dev-100 only, no Test-400 involvement.
- [x] 0.2 Validate with the local CLI:
  `~/workspace/tools/openspec/node_modules/.bin/openspec validate --all`
  — must pass before the A/B. Validated 2026-11-11: 16/16 passed.

## A. Implementation (behind a flag)

- [x] A.1 Write `tests/test_extractive_final_read.py` FIRST (prompt
  builder + mocked end-to-end): extractive re-read fires and replaces
  the draft; fires even when the draft is backed (always-on, unlike
  H15); no re-read when no supported claims exist; flag-off runs are
  byte-identical (no `extractive` field); re-read "unknown" keeps the
  draft. Tests must fail at collection (ImportError) before the
  implementation lands.
- [x] A.2 Implement in `src/llm/prompts.py`: `EXTRACTIVE_SYSTEM` +
  `extractive_answer_messages(question, claims)` — claims block only,
  NO context block.
- [x] A.3 Wire in `src/systems/erag.py`: the extractive branch is
  checked first in the final-read block (guard the grounded-messages
  and contested branches so they cannot overwrite its `msgs`); row
  field `extractive` written only when the flag is on; config key
  `erag.extractive_final_read` (default false).
- [x] A.4 Run the targeted suite + the full suite. Full suite must
  stay 186 passed / 1 failed (known pre-existing retry mismatch).
  DONE 2026-11-11: 6 new H19 tests pass; full suite 192 passed / 1
  failed (known pre-existing retry mismatch only). One test needed a
  fix during the run: the no-supported-claims case runs SC (gaps exist,
  Fast Path does not skip it), so the mock serves draft, claims, then
  2 SC samples = 4 calls.

## B. A/B (needs Groq key)

- [x] B.1 Dev-100 BM25 A/B via `~/workspace/phase26_h19_chain.sh`:
  baseline = frozen improved config, fresh namespace
  `dev_p27_h19_base_bm25`; extractive arm = same +
  `erag.extractive_final_read=true`, fresh namespace
  `dev_p27_h19_extractive_bm25`. One `--set` per invocation.
  Verify the bar shows `erag:dev 0/100` right after launch.
- [x] B.2 Run `scripts/phase26_h19_verdict.py` on the two files;
  judge the gate (dEM ≥ +0.02 AND wrong-answer rate not up AND
  dcalls ≤ +0.5). If the gate fails, the mechanism stays OFF and the
  round moves to H18.

## C. Close-out

- [x] C.1 Write the records (master plan §12, assumptions-vs-outcomes,
  hypotheses status H19 verdict + scoreboard, retrospective changelog
  §2 + §§4/5/7, project report refresh).
- [x] C.2 Commit on `trueadaptive` (proper message, author
  Saumojit30). Do not push (PAT pending — separate blocked item).
- [x] C.3 Archive the change (`openspec archive -y`) and re-validate.
- [x] C.4 Report the verdict to the user (H19 gate pass/fail + what
  it means for the Phase 2.7 round).
