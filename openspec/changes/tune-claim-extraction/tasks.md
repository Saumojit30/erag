# Tasks: Tune-Claim-Extraction (tuning step 2)

Drafted 2026-11-09 from `docs/trueadaptive-test400-error-analysis.md` (§2, §5)
and the fresh diagnosis of the 37 never-claimed rows (proposal.md, Why).
Branch `trueadaptive`. Nothing is pushed. Do not start the build until the
proposal is approved — it is approved (user: "for each step use openspec
along the way", 2026-11-09; step 2 authorized by the user's "ok" to the
step-1 report, 2026-11-09).

## 0. OpenSpec change (before any code)

- [x] 0.1 Create `openspec/changes/tune-claim-extraction/` with `proposal.md`,
  `design.md`, `tasks.md` (this file), `specs/claim-extraction/spec.md`.
- [ ] 0.2 Validate with the local CLI:
  `~/workspace/tools/openspec/node_modules/.bin/openspec validate --all`
  and `.../openspec validate tune-claim-extraction` — must be 0 failed before
  any code change.

## A. Tests first (mocked LLM, no production change yet)

- [ ] A.1 In `tests/test_claims.py` (new file if none exists), add mocked-LLM
  tests for the revised extraction: a response with draft- and
  question-sourced claims parses both with their `"source"` preserved;
  a response without `"source"` defaults every claim to `"draft"`;
  the fallback single-atomic claim carries `"source": "draft"`; the
  exactly-one-answer-bearing rule is unchanged; the revised `CLAIM_SYSTEM`
  contains the question-grounded instruction and the full-names instruction.
- [ ] A.2 Extend `scripts/analyze_trueadaptive_test400.py` with a `--claims`
  summary for the TA dev file: gold-in-claims rate among full-recall wrong
  rows (gate measure), share of claims with `source == "question"`, how many
  gold-bearing claims are question-sourced, and how often the answer-bearing
  claim is question-sourced. Verify it reproduces the v1 dev baseline
  (gold-in-claims rate 0.333, 12/18 never claimed) when run on the v1 dev
  file with `--claims --ta-dev results/trueadaptive/erag_trueadaptive_bm25_dev.jsonl`.

## B. Implementation

- [ ] B.1 Revise `CLAIM_SYSTEM` in `src/epistemic/claims.py` per `design.md`
  (question-grounded claims after the draft-supporting claims, full names
  exactly as in the context, `"source"` per claim in the JSON schema).
- [ ] B.2 Extend `_parse` to preserve `"source"` (`"draft"` default) and set
  `"source": "draft"` on the fallback claim. No change to `extract_claims`
  signature, `run_erag`, or any other file.
- [ ] B.3 Run the fast test suite (cache, config, metrics, erag, retrieval,
  claims) and the new A.1 tests. All green before any live run.

## C. Dev-100 BM25 A/B (live — needs a Groq key, transiently, none saved)

- [ ] C.1 Run Dev-100 BM25 with the revised extraction and
  `--set erag.max_claims=8`, on top of the step-1 tuned system
  (`ground_final_read=true` stays on — the A/B measures step 2's marginal
  effect on the tuned system). Single `--set` with all overrides
  (step-1 lesson: repeated `--set` flags overwrite; only the last survives).
  Output to a new file (do not overwrite any v1 or step-1 dev file).
  Prepared command (verify against `run_experiment.py` before running;
  needs a Groq key transiently, none saved):
  `HF_HUB_DISABLE_XET=1 NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 GROQ_API_KEY=<transient> .venv/bin/python scripts/run_experiment.py --config configs/base.yaml configs/erag_trueadaptive.yaml --set retrieval.retriever_type=bm25 run.cache_namespace=dev_trueadaptive_v1_bm25 run.name=erag_trueadaptive_bm25_dev_claims erag.ground_final_read=true erag.max_claims=8`
  NOTE: the cache namespace is reused deliberately, but the extraction
  prompt is new text, so this run is live-vs-live against the step-1 dev
  file — expect ~±3 EM rows of live-call noise (step-1 finding). The clean
  measures are within-run (`--claims`).
  Then analyze with: `.venv/bin/python scripts/analyze_trueadaptive_test400.py --claims --reread --ta-dev results/trueadaptive/erag_trueadaptive_bm25_dev_claims.jsonl`
- [ ] C.2 Analyze with the script from A.2: EM, F1, mean calls, and the
  `--claims` section. Compare against the step-1 tuned dev file (EM 0.56,
  4.75 calls/Q) and the v1 dev baseline (gold-in-claims rate 0.333).

## D. Gate

- [ ] D.1 Proceed only if: EM is not below the step-1 tuned dev (0.56);
  gold-in-claims rate among full-recall wrong dev rows improves on 0.333;
  mean calls rise by ≤ 0.5/Q (design adds zero calls); the answer-bearing
  claim is question-sourced in ≤ 10% of rows. If the gate fails, record the
  result, do not tune the thresholds to compensate, and either try Variant B
  (design.md, Mechanism 2) as its own change or drop the mechanism.
- [ ] D.2 Commit the change (code + tests + config note + dev results) on
  `trueadaptive`. If the gate passes, record the tuned `max_claims: 8` in
  the frozen config note (a new tuned config file, not an edit to the v1
  frozen config). Do NOT run Test-400 for this step — the confirmation run
  comes once, after all tuning steps.

## E. Archive + next step

- [ ] E.1 Mark this change complete, archive it
  (`openspec archive tune-claim-extraction`), and start the next change
  (`tune-unknown-prompt`, step 3) the same way: proposal first, code second.
