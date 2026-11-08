# Tasks: E-RAG-TrueAdaptive (v1)

Drafted 2026-11-08 from `docs/audit-adaptive-llm-calling.md` §12, updated
to the v1/v2 split (Gap A deferred to v2) on branch `trueadaptive`
(base `9564676`, merged upstream Phase 5). Nothing is pushed.
Do not start the build until the five decisions in `proposal.md` are
answered — they are answered (see proposal.md "Decisions — resolved").

## 0. OpenSpec change (before any code)

- [x] 0.1 Create `openspec/changes/erag-trueadaptive/` with `proposal.md`,
  `design.md`, `tasks.md` (this file) — drafted 2026-11-08, untracked
- [x] 0.2 Split v1/v2: Gap A (entropy-gated retrieval) moved to v2/deferred
  in proposal/design/spec; v1 is sequential SC + gated SC only.
- [x] 0.3 Validate with the local CLI:
  `~/workspace/tools/openspec/node_modules/.bin/openspec validate --all`
  and `.../openspec validate erag-trueadaptive` — 2 passed, 0 failed,
  change valid, no warnings (2026-11-08, branch `trueadaptive`).

## A. Branch

- [x] A.1 `git checkout -b trueadaptive` from `9564676`. Keep `master`
  clean. All v1 work happens on this branch.

## B. Call-count tests first (no production change yet)

- [x] B.1 In `tests/test_erag.py`, add mocked-LLM tests asserting exact
  `tracker.llm_calls` and call order for: fast-path Reference (7),
  fast-path Balanced (5), 1-hop Balanced (7), sequential SC stops at 2 on
  agreement, SC skipped on fast path (2 calls), v1 1-hop (5 calls).
  Old-path tests passed on current code; new-path tests failed until the
  code landed (5 failed before Step C, 2 before Step E, 0 after).
- [x] B.2 Re-run `tests/test_retrieval.py` (8 tests) — **done 2026-11-08:
  8/8 passed** (MiniLM downloaded with `HF_HUB_DISABLE_XET=1`; XET
  endpoint returns 403 in this VM). Record the result; do not claim it
  passes until re-run — now done.

## C. Sequential SC (Gaps B + C) — v1

- [x] C.1 Add `sequential_consistency()` to `src/epistemic/confidence.py`
  (same return shape as `self_consistency`; entropy + ΔH < 0.05 stopping,
  M cap 3). Wire behind `erag.sc_mode` (default `fixed`).
- [x] C.2 Unit-test with mocked LLM: unanimous → stops at 2; split → goes
  to 3. Done, commit `738dd1e`.

## D. Entropy-gated retrieval (Gap A) — v2, NOT v1

- [ ] D.1 (v2) Add the closed-book probe at the top of `run_erag` behind
  `erag.parametric_gate` (default false). Log the gate decision per record.
- [ ] D.2 (v2) Validate on Dev-100: report skip rate and false-skip rate.

## E. Gate SC behind the Fast Path — v1

- [x] E.1 Restructure hop-0 order (draft → claims → graph → Fast-Path
  check → SC only if needed), with `c0 = min_eff` when SC is skipped,
  behind `erag.gate_sc_behind_fast_path` (default false). Separate commit
  from Step C so its EM effect can be A/B'd alone. Done, commit `7d5cba4`.
- [ ] E.2 A/B on Dev-100 against Step C alone, so the EM effect is isolated.
  (Live run — needs a Groq key; not run in the v1 build.)

## F. Config + Dev-100 validation

- [x] F.1 Freeze `configs/erag_trueadaptive.yaml` (sequential SC, M cap 3,
  gated SC on, parametric gate NOT set, direct EIG, incremental claims,
  never resample, saturation precheck, thresholds unchanged, **new
  `cache_namespace` dev_trueadaptive_v1**). Verified: loads via
  `load_cfg`, every key read by the code, yaml-driven mocked fast path
  costs 2 calls.
- [ ] F.2 Run Dev-100 with `scripts/run_experiment.py` (system erag, split
  dev). Report: mean calls, EM, F1, stopping-point distribution, plus
  IRCoT/MiniLM on Dev-100 as comparator. **Needs a Groq key supplied
  transiently by the user — none is saved. Not run in v1 build.**
- [ ] F.3 Gate: proceed only if EM is within tolerance of Balanced
  Dev-100 (0.5100; target EM ≥ 0.50, mean calls ≤ 6). If not, tune the
  gate/SC stopping, not the thresholds.

## G. Test-400, once — OUT OF SCOPE for v1 build

- [ ] G.1 Run E-RAG-TrueAdaptive **and** IRCoT, both MiniLM, k=3, on
  Test-400 (via `run_experiment.py`, split test; mind the write guard and
  the Windows-only lock in the Phase 4/5 scripts — do not use those).
  Single Test-400 run. Report EM/F1/recall/All-Gold/coverage/selective
  EM/ECE/Brier/AUROC/mean calls/mean tokens for both, with McNemar +
  bootstrap CIs (`src/eval/stats.py`).

## H. Archive

- [ ] H.1 Mark the OpenSpec change complete, archive it
  (`openspec archive erag-trueadaptive`), and only then discuss the next
  step (architecture tuning, second retriever, new dataset) with the user.

## Workflow follow-up

- Validate OpenSpec status via `openspec validate erag-trueadaptive`.
- Groq key is needed transiently for any live run (not saved); use
  `NO_PROXY=localhost,127.0.0.1`.
