# Tasks: Learned continuation policy (tuning step 7)

Drafted 2026-11-09 from `docs/tuning-master-plan.md` (§3.7), the
H1–H6 assessment, the step-4/5 findings, and fresh recomputation
from the stored post-step-4 dev traces. Branch `trueadaptive`.
Nothing is pushed. Do not start the build until the proposal is
approved — the user approves by saying go (or by tapping the
offer); the build then follows this file.

## 0. OpenSpec change (before any code)

- [x] 0.1 Create `openspec/changes/learned-continuation-policy/`
  with `proposal.md`, `design.md`, `tasks.md` (this file),
  `specs/learned-continuation/spec.md`. DONE 2026-11-09 by the
  parent (drafted from the stored theta_a dev traces).
- [x] 0.2 Validate with the local CLI:
  `~/workspace/tools/openspec/node_modules/.bin/openspec validate --all`
  and `.../openspec validate learned-continuation-policy` — must be 0
  failed before any code change. DONE 2026-11-09: `validate --all`
  9 passed, 0 failed (spec format fixed: ADDED Requirements +
  Scenario blocks; two warnings cleared).

## A. Offline measurement first (no LLM calls, no `src/` change)

- [x] A.1 Extraction: new script
  `scripts/extract_continuation_training.py` (or an analyzer
  section — implementer's choice, but a standalone script is
  preferred: the training set is an artifact, not a report). It
  reads ONLY the post-step-4 tuned dev file
  (`results/trueadaptive/erag_trueadaptive_bm25_dev_theta_a.jsonl`)
  and `data/manifests/dev.jsonl`, and writes
  `data/continuation_training_dev.jsonl` — one row per dev question
  with the design.md hop-0 features (c0, c0_source, claim-status
  counts, answer-bearing claim status, mean claim conf, hop-0 recall
  recomputed from the manifest vs `trace[0]['pool']` titles,
  question type, draft-unknown flag, sc_skipped_fast_path) and the
  label (hop-0 draft correct by repo `exact_match`,
  `trace[0]['answer']` vs `gold`). It MUST refuse any file whose
  name or manifest is not dev (assert on the input path — test files
  are never valid input here). Verification (must reproduce exactly
  before any training): N=100 deduped, 0 failed; hop-0 draft EM
  0.4800, final EM 0.5100, fixed by hops 6, broke 3, hops {0:45,
  1:45, 2:10}, abstained 15, draft-unknown 6; baseline EM 0.5100,
  4.65 calls/Q. Also compute and record the oracle ceiling
  (perfect draft-correctness model: STOP on correct drafts,
  CONTINUE on wrong ones — EM and calls/Q under the call-accounting
  rule below). If the extraction does not reproduce these numbers,
  it is wrong — fix it before any training. DONE 2026-11-09,
  verified by the parent by independent re-run: all verification
  numbers reproduced exactly; oracle ceiling included 83, excluded
  17, EM 0.6506, calls/Q 4.61 (saves only 0.04/Q — 28 of the 48
  correct drafts already stop at hop 0 under the static fast path).
  RETRAIN AMENDMENT 2026-11-09 (user chose retrain): the
  `draft_unknown` feature is now the hop-0 draft
  (`trace[0]['answer']`); verification adds hop0_draft_unknown 20
  (row-draft count 6 kept as an input-file check); 1 new test
  (hop-0-unknown with real final draft → feature 1) + 1 updated
  test (row-draft unknown with real hop-0 draft → feature 0); suite
  127 passed, 1 failed (known retry mismatch).
- [x] A.2 Call accounting: the extraction (or a paired function)
  reconstructs hop-0 calls per row from the code and the stored
  rows, and verifies the invariant for EVERY row: reconstructed
  hop-0 calls + stored later-hop calls == stored `llm_calls`.
  The reconstruction rule is determined by reading
  `src/systems/erag.py` and `src/epistemic/confidence.py` (draft 1
  + extraction 1 + SC samples from `c0_source` / trace + EIG probe
  if any). If an exact reconstruction is impossible, use a
  documented conservative approximation (overestimate stopped
  rows' calls, never underestimate) and record it in the design.md
  Threats section — do not silently approximate. DONE 2026-11-09:
  EXACT, no approximation needed — invariant holds for all 100
  rows (accounting violations 0, verified by parent re-run). Rule
  recorded in design.md Threats: hop-0 = 1 draft + 1 extraction +
  SC samples (0 if Fast Path skipped, 2 if c0 == 1.0, else 3);
  later hops = 1 draft + 1 extraction iff the draft changed vs
  hop 0, +1 for a triggered re-read; EIG probes 0, resample 0.
- [x] A.3 Training + counterfactual simulation: new script
  `scripts/train_continuation_policy.py`. It loads the A.1 training
  set, fits a logistic regression (features standardized, single
  model), chooses τ by 5-fold cross-validation to maximize saved
  calls at simulated EM ≥ 0.5000, and simulates the policy on dev
  from the stored traces (STOP → hop-0 draft + hop-0 calls;
  CONTINUE → stored final answer + stored total calls), reporting
  simulated EM, F1, calls/Q, live calls/Q (for the record only),
  coverage, and the prefix-validity exclusion count (rows where the
  policy says CONTINUE but the stored trace stopped at hop 0 —
  excluded from the simulated numbers, counted and reported; if
  they exceed 10% of rows, Phase A stops here). If the
  cross-validated simulation does not beat the static baseline, try
  ONE alternative — a depth-2 decision tree — and take the better
  cross-validated result; no third model, no feature search after
  seeing results. Tests first: mocked-trace tests for the
  extraction, the accounting invariant, and the simulation (a
  hand-built 4-row trace set with known STOP/CONTINUE outcomes);
  the tests must fail before the implementation and pass after.
  DONE 2026-11-09, verified by the parent by independent re-run:
  LR, τ = 0.30, simulated EM 0.5000, F1 0.5837, calls/Q 3.98
  (saved +0.67), coverage 0.766, STOP 70 / CONTINUE 24, excluded
  6/100 (6.0%, under the 10% ceiling). No tree tried — LR passed,
  so the fallback was not triggered. OOF AUROC 0.6546 (c0 alone
  0.484 on dev). Parent's composition check: policy STOPs on 4 of
  the 6 fix-rows (loses 4 fixes) and saves 1 of 3 breaks; STOP rows
  40 correct at hop-0, CONTINUE rows 7 correct at final = 47/94;
  3 of the 6 excluded rows had correct hop-0 drafts.
- [x] A.4 Gate A (pre-registered, design.md): cross-validated
  (out-of-fold only) simulated EM ≥ 0.5000 AND simulated calls/Q
  strictly below 4.65. If it fails, stop — no wiring, no live run,
  no threshold re-picking; record the result and close the change
  as a negative result. If it passes, train the final model on all
  100 dev rows and write the policy artifact
  `configs/continuation_policy_dev.json` (model type, feature list
  in order, coefficients, intercept, τ, training provenance: file,
  N, date, cross-validated scores). VERDICT 2026-11-09 (parent):
  **PASS, exactly at the floor** — simulated EM 0.5000 ≥ 0.5000,
  calls/Q 3.98 < 4.65, OOF only, exclusion 6.0%. BUT the pass is
  zero-margin (one fewer correct row fails it), F1 (0.5837 vs
  0.5969) and coverage (0.766 vs 0.790) dip below baseline, and the
  saving is bought by stopping on wrong drafts (the oracle ceiling
  saves only 0.04 calls/Q). The user chose to proceed to B-phase
  (options-widget tap 2026-11-09). Final model trained 2026-11-09
  by the parent (`scripts/train_continuation_policy.py
  --write-artifact`, new flag, refuses to write unless Gate A
  passes): artifact `configs/continuation_policy_dev.json`, τ =
  0.30, OOF AUROC 0.6546, coefficients verified against the fitted
  pipeline to 2.2e-16 by pure-arithmetic recomputation; format
  recorded in design.md (linear-only, dependency-free inference).
  **SUPERSEDED 2026-11-09:** the B.1 subagent found `draft_unknown`
  was trained on the row draft (final draft, unavailable at hop 0);
  the parent verified 16/100 rows diverge. The user chose the
  retrain (options-widget tap 2026-11-09). Re-extraction with the
  hop-0 definition + re-training, same pre-registered gate:
  **Gate A RE-CHECK: PASS with margin** — LR, τ = 0.05, simulated
  EM 0.5152, F1 0.6238, calls/Q 3.92 (saved +0.73), coverage 0.869,
  STOP 81 / CONTINUE 18, excluded 1/100 (1.0%); OOF AUROC 0.6775;
  F1 and coverage now ABOVE baseline; composition STOP on 2/6
  fix-rows (lost 2), 2/3 broke rows (saved 2). New artifact written
  (τ = 0.05, `draft_unknown` coef −1.489), verified to 2.2e-16;
  the τ = 0.30 artifact is superseded and must not be used for
  wiring. B.1 proceeds on the retrained artifact.

- [x] A.5 Analyzer section: add a `--policy` section to
  `scripts/analyze_trueadaptive_test400.py` (new section number
  after 14; flags `--policy` + `--policy-baseline <file>` +
  `--policy-simulation <json>`). It reports, for the policy run
  file: N (deduped), failed, EM, F1, mean `llm_calls`/Q, mean
  `cache_hits`/Q, mean live calls/Q, hops distribution (n, mean
  calls, EM per hops value), policy decision counts (STOP vs
  CONTINUE — from a per-row `policy_decision` field the runner
  writes in B.1; rows without the field are reported as unknown,
  never assumed), STOP-rows' EM vs CONTINUE-rows' EM, and the
  agreement check vs the simulation JSON (ΔEM, Δcalls/Q — the
  Gate B ±0.02 / ±0.2 check). Tests first in a new
  `tests/test_analyzer_policy.py`; verification: on the theta_a
  baseline file it reproduces EM 0.5100, 4.65 calls/Q (no policy
  field → all rows unknown). Do NOT break the existing sections.
  DONE 2026-11-09, verified by the parent: section 15, 7 tests
  (failed before, pass after); on theta_a reproduces EM 0.5100,
  F1 0.5969, 4.65 calls/Q, 0.04 live, all 100 rows unknown;
  agreement vs simulation dEM +0.0100, dCalls/Q +0.67. Sections
  13/14 re-verified intact. Fast suite 126 passed, 1 failed (only
  the known pre-existing retry mismatch).

## B. Implementation (only if Gate A passes)

- [ ] B.1 Wire the policy into `run_erag` behind
  `erag.continuation_policy` (path to the artifact file; absent =
  today's static behavior, exactly). At the hop-0 boundary (after
  hop-0 draft, claims, verification — the current fast-path / first
  gap-continuation decision point), compute the hop-0 features the
  same way A.1 computes them from the stored trace (same function
  where possible — a live/stored feature mismatch breaks the
  simulation equivalence), load the artifact, and STOP or CONTINUE.
  EIG gap selection, SC, abstention (theta_abs=0.5), and max_hops=2
  are unchanged. Tests first: mocked-LLM tests in
  `tests/test_erag.py` proving the policy is consulted and its
  decision binds — a policy that says STOP ends at hop 0 with no
  retrieval even when gaps exist; a policy that says CONTINUE
  enters hop 1; with the flag absent the run behaves exactly as
  before (control test on the existing static path).
- [ ] B.2 Fast suite green after B.1 (the suite as in steps 1–6).
  The known pre-existing failure
  (`test_retry_exhaustion_raises_runtime_error`, expects "after 4
  attempts", code says 6; fails on base too) stays untouched.

## C. Live A/B (only if Gate A passed; needs a Groq key, transiently, none saved)

- [ ] C.1 One run: tuned system + policy, Dev-100 BM25, reused dev
  namespace `dev_trueadaptive_v1_bm25` (the policy changes which
  calls happen, not the prompts, so cached calls still count as
  calls and the run is fast). Single `--set` with all overrides
  (carry ALL tuned values forward: `ground_final_read=true`,
  `max_claims=8`, `theta_abs=0.5`, `max_hops=2` — the ceiling, NOT
  1; the policy is the decider now). Prepared command (verify
  against `run_experiment.py` and the step-4 change before running;
  needs a Groq key transiently, none saved):
  `HF_HUB_DISABLE_XET=1 NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 GROQ_API_KEY=<transient> .venv/bin/python scripts/run_experiment.py --config configs/base.yaml configs/erag_trueadaptive.yaml --set retrieval.retriever_type=bm25 run.cache_namespace=dev_trueadaptive_v1_bm25 run.name=erag_trueadaptive_bm25_dev_policy erag.ground_final_read=true erag.max_claims=8 erag.max_hops=2 erag.theta_abs=0.5 erag.continuation_policy=configs/continuation_policy_dev.json`
  Output: `results/trueadaptive/erag_trueadaptive_bm25_dev_policy.jsonl`.
  Then analyze with the `--policy` analyzer section (A.5): live EM,
  calls/Q, live calls/Q (recorded, NOT gated), hops distribution,
  and the agreement check vs the simulation.
- [ ] C.2 Compare against the post-step-4 tuned dev baseline
  (EM 0.5100, 4.65 calls/Q) AND against the Phase A simulation.
  Record the baseline file path and its numbers in the commit
  message.

## D. Gate B (pre-registered, design.md)

- [ ] D.1 The policy enters the frozen Test-400 system ONLY if
  ALL of: live EM ≥ 0.5000; live calls/Q strictly below 4.65; live
  numbers within ±0.02 EM / ±0.2 calls/Q of the simulation (else
  the wiring is wrong — fix the wiring, do not re-tune); N=100
  deduped, 0 failed rows. If the gate fails, record the result and
  do not re-tune the policy to compensate — the tuned system keeps
  the static hop rules. Do NOT run Test-400 for this step.
- [ ] D.2 Commit the change (extraction + training scripts +
  policy artifact + tests + analyzer section + dev result) on
  `trueadaptive`, with the gate verdict and per-arm numbers in the
  commit message. If the gate passes, record
  `erag.continuation_policy: configs/continuation_policy_dev.json`
  in the frozen-config note (the tuned config file itself is
  written at the end of Phase 1, not here). Do NOT commit
  `results/cache.sqlite` or `results/nli_memo.pkl`.

## E. Archive + next step

- [ ] E.1 Archive the change with `openspec archive
  learned-continuation-policy -y` (always `-y` in this environment
  — without it the command blocks on an interactive prompt with no
  TTY). Verify the archived change is under
  `openspec/changes/archive/2026-11-09-learned-continuation-policy/`
  and the spec merged to
  `openspec/specs/learned-continuation/`.
- [ ] E.2 Re-validate: `openspec validate --all` must be 0 failed.
  Update the master plan (§3.7 outcome + §2.1 status + §9 decision)
  and `docs/hypotheses-current-status.md` (H3 — the policy is a
  direct test of whether the confidence signal, combined, can
  drive effort better than fixed thresholds) with the result.
  After this step closes: freeze
  `configs/erag_trueadaptive_tuned.yaml` (incl. the policy on/off
  decision from this step), then Phase 2 Test-400 confirmation.
