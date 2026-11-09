# Tasks: Tune-Theta-Abs (tuning step 4)

Drafted 2026-11-09 from `docs/tuning-master-plan.md` (§3.4) and the
abstention diagnosis in proposal.md (Why). Branch `trueadaptive`.
Nothing is pushed. Do not start the build until the proposal is
approved — the user approves by saying go (or by tapping the offer);
the build then follows this file. Step 4 is the FIRST threshold step:
its baseline is the step-2 tuned dev file. Steps 5 and 6 run AFTER
this step; their A/B baselines are this step's, whatever they are.

## 0. OpenSpec change (before any code)

- [x] 0.1 Create `openspec/changes/tune-theta-abs/` with `proposal.md`,
  `design.md`, `tasks.md` (this file), `specs/theta-abs/spec.md`.
- [ ] 0.2 Validate with the local CLI:
  `~/workspace/tools/openspec/node_modules/.bin/openspec validate --all`
  and `.../openspec validate tune-theta-abs` — must be 0 failed before
  any further work.

## A. Measurement first (no production change yet)

- [ ] A.1 Extend `scripts/analyze_trueadaptive_test400.py` with a
  `--theta` section (section 13) reporting, for the `--ta-dev` file:
  N (deduped), failed count, EM, F1, selective EM (correct / answered),
  wrong-answer rate among answered, wrong answers among all rows,
  coverage, mean `llm_calls`/Q, mean `cache_hits`/Q, mean live calls/Q
  (`llm_calls − cache_hits`), abstained count, and model-unknown count
  — plus the counterfactual table at t = 0.40, 0.45, 0.50, 0.55, 0.60,
  0.65, 0.70, 0.75, 0.80 (EM, selective EM, wrong-answer rate,
  coverage), computed the same way as §4 (abstained rows stay
  abstained; model-unknown rows stay unknown; answered rows with
  `answer_conf < t` become abstained). Classify the two unknown
  populations by DRAFT TEXT (`draft == "unknown"`), not by the
  `abstained` flag — at higher thresholds a model-unknown row can flip
  `abstained=True` while its answer stays "unknown" (design.md).
  Verify it reproduces the known stored-file numbers BEFORE any live
  run (design.md correction note): on
  `results/trueadaptive/erag_trueadaptive_bm25_dev_claims.jsonl` it must
  report EM 0.5400, selective EM 0.6353, wrong-answer rate 0.3647,
  coverage 0.850, 4.65 calls/Q, 2.53 cache_hits/Q; counterfactual
  t=0.50: EM 0.5100, selective EM 0.6456, wrong 0.3544, coverage 0.790;
  t=0.65 identical to 0.50; t=0.75: EM 0.4700, selective EM 0.6351,
  wrong 0.3649, coverage 0.740. Population counts by DRAFT TEXT are 8
  model-unknown, 7 system-abstained (flag counts are 7/8 — one row
  swaps: an abstained row whose draft is literally "unknown",
  `answer_conf` 0.258; the answered set is the same 85 rows either
  way, so no gate number depends on the labeling). If it cannot reproduce these, stop and
  fix the measurement — do not run and report zeros. The section reads
  only fields the runner already writes (`answer_conf`, `abstained`,
  `unknown`, `draft`, `em`, `gold`, `llm_calls`, `cache_hits`,
  `failed`); no new trace field is needed.
- [ ] A.2 Run the fast test suite (cache, config, metrics, erag,
  retrieval, claims, prompts). All green before any live run. No `src/`
  change is expected in this change; if A.1 forces one, stop and amend
  the change first.

## B. Implementation

- [ ] B.1 None expected: the threshold is the existing `erag.theta_abs`
  config value, set to `0.50` (candidate A) and `0.65` (candidate B) in
  the A/Bs' `--set` flags. Verify by grep that `theta_abs` is read only
  at the abstention rule in `src/systems/erag.py` (line 346) and in
  `scripts/profile_efficiency.py` (profiling script, not the experiment
  path). Do NOT edit `configs/erag_trueadaptive.yaml` (frozen v1 config
  — step-3 lesson) or `configs/base.yaml`; the chosen value is recorded
  for the frozen tuned config at end of Phase 1.

## C. Live A/Bs (Dev-100 BM25, tuned system)

- [ ] C.1 Candidate A (`theta_abs=0.50`). Detached, sequential after
  nothing (this is the first of the two runs), Groq key transiently in
  `env` (never saved), with `HF_HUB_DISABLE_XET=1` and both `NO_PROXY`
  and lowercase `no_proxy` set to `localhost,127.0.0.1` (VM quirk —
  uppercase alone fails). Single `--set` (repeated `--set` flags
  overwrite; only the last survives):
  `.venv/bin/python scripts/run_experiment.py --config configs/base.yaml configs/erag_trueadaptive.yaml --set retrieval.retriever_type=bm25 run.cache_namespace=dev_trueadaptive_v1_bm25 run.name=erag_trueadaptive_bm25_dev_theta_a erag.ground_final_read=true erag.max_claims=8 erag.unknown_prompt=base erag.theta_abs=0.5`
  Output: `results/trueadaptive/erag_trueadaptive_bm25_dev_theta_a.jsonl`.
  Expect N=100 deduped, 0 failed. Check `cache_hits`/Q before believing
  the comparison (step-1 lesson); a ~0-live-call run is a replay —
  discard it, do not analyze it.
- [ ] C.2 Candidate B (`theta_abs=0.65`). Same setup, after C.1
  finishes (sequential, same namespace, same key handling):
  `.venv/bin/python scripts/run_experiment.py --config configs/base.yaml configs/erag_trueadaptive.yaml --set retrieval.retriever_type=bm25 run.cache_namespace=dev_trueadaptive_v1_bm25 run.name=erag_trueadaptive_bm25_dev_theta_b erag.ground_final_read=true erag.max_claims=8 erag.unknown_prompt=base erag.theta_abs=0.65`
  Output: `results/trueadaptive/erag_trueadaptive_bm25_dev_theta_b.jsonl`.
  Expect N=100 deduped, 0 failed.

## D. Gate (per candidate, pre-registered in design.md)

- [ ] D.1 For each candidate file, run the `--theta` section and check
  ALL of: (1) selective EM strictly above the step-2 tuned dev baseline
  (0.6353); (2) wrong-answer rate among answered strictly below baseline
  (0.3647); (3) EM ≥ 0.51 (baseline 0.54 minus the pre-registered 0.03
  bound); (4) mean calls/Q within 0.2 of baseline 4.65 (sanity — the
  threshold costs no calls; a larger move means something else changed,
  investigate before passing). Coverage reported, not gated. N=100
  deduped, 0 failed, else the gate does not pass.
- [ ] D.2 Apply the selection rule: if both pass, the one with the
  larger wrong-answer-rate fall proceeds; tie → candidate A
  (`theta_abs=0.50`). If exactly one passes, it proceeds. If neither
  passes, `theta_abs` stays 0.4 — record as a negative result, NO third
  value inside this change. Report both candidates regardless of outcome.
  Record the chosen value (if any) and the coverage at that value for
  the frozen tuned config.

## E. Commit + archive

- [ ] E.1 Commit the build (analyzer `--theta` section), both A/B
  result files, and the gate verdict — separate from the archive commit.
  Do NOT commit `results/cache.sqlite` or `results/nli_memo.pkl`
  (run artifacts, deliberately uncommitted).
- [ ] E.2 Archive with `-y` (the no-TTY lesson — without it the command
  blocks forever on its confirmation prompt):
  `openspec archive tune-theta-abs -y`; then commit the archive.
  Validate `--all` after archiving (0 failed). Update the master plan
  (§3.4 outcome) and MEMORY.md in the same commit round.
- [ ] E.3 Report the verdict to the user: per-candidate gate table,
  the chosen value (or "stays 0.4"), and the next step (step 5's A/B
  baseline is this step's post-step-4 tuned dev file). Do NOT push
  without the user saying so; pushing needs a fresh GitHub token,
  transiently.
