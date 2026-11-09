# Tasks: Tune-Hop2-SC-Cap (tuning step 5)

Drafted 2026-11-09 from `docs/trueadaptive-test400-error-analysis.md` (§5)
and the hop-2 diagnosis in proposal.md (Why). Branch `trueadaptive`.
Nothing is pushed. Do not start the build until the proposal is approved —
the user approves by saying go (or by tapping the offer); the build then
follows this file. Step 4 (`tune-theta-abs`) runs BEFORE this step's A/B;
if step 4 is skipped, the baseline is the step-2 tuned dev file.

## 0. OpenSpec change (before any code)

- [x] 0.1 Create `openspec/changes/tune-hop2-sc-cap/` with `proposal.md`,
  `design.md`, `tasks.md` (this file), `specs/hop2-sc-cap/spec.md`.
- [ ] 0.2 Validate with the local CLI:
  `~/workspace/tools/openspec/node_modules/.bin/openspec validate --all`
  and `.../openspec validate tune-hop2-sc-cap` — must be 0 failed before
  any further work.

## A. Tests first (mocked LLM, no production change yet)

- [ ] A.1 In `tests/test_erag.py`, add a mocked-LLM test proving the cap
  binds: `run_erag` with `erag.max_hops=1` never reaches hop 2. Mock
  the NLI to return `unresolved` (so gaps exist and the loop wants to
  continue) and the retriever to return novel passages at hop 0, so the
  run reaches hop 1; then assert `out["hops"] == 1` and that the LLM was
  never called for a hop-2 draft (bound `llm.chat.call_count` — the
  hop-2 draft + extraction calls must not happen). A test that only
  reaches hop 0 (e.g. all claims supported → Fast Path) does NOT prove
  the cap binds; it must enter hop 1 and stop there. Run the test
  against `max_hops=2` as a control: the same mocks must reach hop 2.
- [ ] A.2 Extend `scripts/analyze_trueadaptive_test400.py` with a
  `--hopcap` section (section 13) reporting, for the `--ta-dev` file:
  N (deduped), failed count, EM, F1, mean `llm_calls`/Q, mean
  `cache_hits`/Q, mean live calls/Q (`llm_calls − cache_hits`), the hops
  distribution (n, mean calls, EM per hops value), hop-2 row count and
  hop-2 calls, and tail rows (≥7 calls) with their call share. When
  given `--hopcap-baseline <file>`, print the same measures for the
  baseline file and the deltas (calls/Q, live calls/Q, EM). Verify it
  reproduces the known stored-file numbers BEFORE any live run
  (design.md correction note): on
  `results/trueadaptive/erag_trueadaptive_bm25_dev_claims.jsonl` it must
  report EM 0.5400, 4.65 calls/Q, 10 hop-2 rows, 78 hop-2 calls; on
  `results/trueadaptive/erag_trueadaptive_test_bm25.jsonl` it must report
  42 hop-2 rows, 334 hop-2 calls, tail 54 rows / 422 calls. If it cannot
  reproduce these, stop and fix the measurement — do not run and report
  zeros. The section reads only fields the runner already writes
  (`llm_calls`, `cache_hits`, `hops`, `trace[i].answer`, `em`, `gold`,
  `failed`); no new trace field is needed.
- [ ] A.3 Run the fast test suite (cache, config, metrics, erag,
  retrieval, claims, prompts). All green before any live run. No `src/`
  change is expected in this change; if A.1–A.2 force one, stop and
  amend the change first.

## B. Implementation

- [ ] B.1 None expected: the cap is the existing `erag.max_hops` config
  value, set to `1` in the A/B's `--set` flags. Verify by grep that
  `max_hops` is read only at the loop stop in `src/systems/erag.py`
  (line 240) and in `scripts/profile_efficiency.py` (profiling script,
  not the experiment path). Do NOT edit
  `configs/erag_trueadaptive.yaml` (frozen v1 config) and do NOT add a
  new flag — if either looks necessary, stop and amend the change.

## C. Dev-100 BM25 A/B (live — needs a Groq key, transiently, none saved)

- [ ] C.1 One A/B: the tuned system with `erag.max_hops=1`, on top of
  the post-step-4 tuned system. The `--set` MUST be verified against
  the step-4 change's frozen values before running (step 4 may have set
  `theta_abs` or other tuned values — carry them all forward; if step 4
  was skipped, the tuned values are `ground_final_read=true` and
  `max_claims=8` from steps 1–2). Single `--set` with all overrides
  (step-1 lesson: repeated `--set` flags overwrite; only the last
  survives). Output to a new file (do not overwrite any v1, step-1,
  step-2, step-3, or step-4 dev file). Prepared command (verify against
  `run_experiment.py` and the step-4 change before running; needs a
  Groq key transiently, none saved):
  `HF_HUB_DISABLE_XET=1 NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 GROQ_API_KEY=<transient> .venv/bin/python scripts/run_experiment.py --config configs/base.yaml configs/erag_trueadaptive.yaml --set retrieval.retriever_type=bm25 run.cache_namespace=dev_trueadaptive_v1_bm25 run.name=erag_trueadaptive_bm25_dev_hopcap erag.ground_final_read=true erag.max_claims=8 erag.max_hops=1 [plus step-4 tuned values, if any]`
  Then analyze with: `.venv/bin/python scripts/analyze_trueadaptive_test400.py --hopcap --hopcap-baseline <post-step-4 tuned dev file> --ta-dev results/trueadaptive/erag_trueadaptive_bm25_dev_hopcap.jsonl`
- [ ] C.2 Compare against the post-step-4 tuned dev baseline file (EM,
  calls/Q, live calls/Q, hops distribution, hop-2 rows). If step 4 was
  skipped, the baseline is the step-2 tuned dev file (EM 0.5400,
  F1 0.6391, 4.65 calls/Q, 10 hop-2 rows, 78 hop-2 calls). Record the
  baseline file path and its numbers in the commit message — never
  compare against step-2's 0.54 when step 4 ran.

## D. Gate (pre-registered)

- [ ] D.1 The cap proceeds only if ALL of: mean `llm_calls`/Q is
  strictly below the post-step-4 tuned dev baseline; mean live
  calls/Q (`llm_calls − cache_hits`) is also below the baseline;
  EM is not below the baseline EM by more than 1 pt (EM ≥ baseline −
  0.01); N=100 deduped, 0 failed rows. Expected (not gated): dev
  saving ≈ 0.15 calls/Q. If the gate fails, record the result and do
  not narrow the cap to compensate — the tuned system keeps
  `max_hops: 2`.
- [ ] D.2 Commit the change (tests + analyzer + dev result) on
  `trueadaptive`. If the gate passes, record `erag.max_hops: 1` in the
  frozen-config note (the tuned config file itself is written at the
  end of Phase 1, not here). Do NOT run Test-400 for this step — the
  confirmation run comes once, after all tuning steps.

## E. Archive + next step

- [ ] E.1 Mark this change complete, archive it
  (`openspec archive tune-hop2-sc-cap -y`), and start the next change
  (`tune-memory-effectiveness`, step 6) the same way: proposal first,
  code second. Step 6 is a component test on the tuned system using the
  E5 stream instrument (Dev-100 cannot test memory — see master plan
  §3.6); its change is drafted when step 5 closes.
