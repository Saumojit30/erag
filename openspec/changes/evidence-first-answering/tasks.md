# Tasks: Phase 2.7 H18 — Evidence-first answering

## 0. OpenSpec change (before any code)

- [x] 0.1 Create `openspec/changes/evidence-first-answering/` with
  `proposal.md`, `design.md`, `tasks.md` (this file) — drafted
  2026-11-11 from `docs/architecture-analysis-hallucination.md`
  mechanism A. H18 pre-registered 2026-11-11 in the master plan
  §4.7; the A/B is Dev-100 only, no Test-400 involvement.
- [x] 0.2 Validate with the local CLI:
  `~/workspace/tools/openspec/node_modules/.bin/openspec validate --all`
  — must pass before the A/B. Validated 2026-11-11: 17/17 passed.

## A. Implementation (behind a flag)

- [x] A.1 Write `tests/test_evidence_first.py` FIRST (prompt
  builders + mocked end-to-end): no draft call is made when the flag
  is on (claims come from passages, not from a draft); the composed
  draft comes only from supported claims; no compose call and draft
  "unknown" when no supported claim exists; SC runs on the composed
  draft; flag-off runs are byte-identical (no `evidence_first`
  field); hop-1 re-extracts passage claims from the enlarged pool
  (no incremental reuse on the evidence-first path). Tests must fail
  at collection (ImportError) before the implementation lands.
- [x] A.2 Implement in `src/epistemic/claims.py`:
  `EVIDENCE_CLAIM_SYSTEM` + `extract_evidence_claims(llm, question,
  pool, tracker, max_claims)` — Context only, no Answer input; reuse
  `_parse()` with `default_source="question"`.
- [x] A.3 Implement in `src/llm/prompts.py`: `COMPOSE_SYSTEM` +
  `compose_answer_messages(question, claims)` — claims block only,
  NO context block.
- [x] A.4 Wire in `src/systems/erag.py`: when
  `erag.evidence_first` is true, the hop body runs extract →
  provisional graph (c0=1.0 prior) → compose → SC → rebuild graph
  with real c0; skip the draft call, skip `single_atomic` and the
  H13 second pass on this path, force full re-extraction each hop;
  row field `evidence_first` written only when the flag is on;
  config key `erag.evidence_first` (default false). Flag-off runs
  must be byte-identical to the improved system.
- [x] A.5 Run the targeted suite + the full suite. Full suite must
  stay at the H19 close-out level (192 passed / 1 failed, known
  pre-existing retry mismatch only).

## B. A/B (needs Groq key)

- [ ] B.1 Dev-100 BM25 A/B via `~/workspace/phase26_h18_chain.sh`:
  baseline = frozen improved config, fresh namespace
  `dev_p27_h18_base_bm25`; evidence-first arm = same +
  `erag.evidence_first=true`, fresh namespace
  `dev_p27_h18_evidence_bm25`. One `--set` per invocation. The
  baseline is re-run fresh (do not reuse the H15/H19 baseline
  files). Verify the bar shows `erag:dev 0/100` right after launch.
- [ ] B.2 Run `scripts/phase26_h18_verdict.py` on the two files;
  judge the gate (dEM ≥ +0.02 AND wrong-answer rate not up AND
  dcalls ≤ +0.5). If the gate fails, the mechanism stays OFF and the
  round moves to H20/H21, not to another reader restriction.

## C. Close-out

- [ ] C.1 Write the records (master plan §12,
  assumptions-vs-outcomes, hypotheses status H18 verdict +
  scoreboard, retrospective changelog §2 + §§4/5/7, project report
  refresh).
- [ ] C.2 Commit on `trueadaptive` (proper message, author
  Saumojit30). Do not push (PAT pending — separate blocked item).
- [ ] C.3 Archive the change (`openspec archive -y`) and re-validate.
- [ ] C.4 Report the verdict to the user (H18 gate pass/fail + what
  it means for the Phase 2.7 round).
