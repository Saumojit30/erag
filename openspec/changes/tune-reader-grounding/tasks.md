# Tasks: Tune-Reader-Grounding (tuning step 1)

Drafted 2026-11-09 from `docs/trueadaptive-test400-error-analysis.md` (§2, §3,
§5). Branch `trueadaptive`. Nothing is pushed. Do not start the build until the
proposal is approved — it is approved (user: "for each step use openspec along
the way", 2026-11-09).

## 0. OpenSpec change (before any code)

- [x] 0.1 Create `openspec/changes/tune-reader-grounding/` with `proposal.md`,
  `design.md`, `tasks.md` (this file), `specs/reader-grounding/spec.md`.
- [x] 0.2 Validate with the local CLI:
  `~/workspace/tools/openspec/node_modules/.bin/openspec validate --all`
  and `.../openspec validate tune-reader-grounding` — must be 0 failed before
  any code change.

## A. Tests first (mocked LLM, no production change yet)

- [x] A.1 In `tests/test_erag.py`, add mocked-LLM tests for the re-read:
  draft "unknown" + supported answer-bearing claim → one extra call, draft
  replaced by the re-read answer; draft agreeing with the claim (draft is a
  substring of the claim text) → no extra call; draft disagreeing → one extra
  call; re-read returning "unknown" → original draft stands; flag off →
  byte-identical behavior to v1 (no extra call, no new record fields set).
- [x] A.2 Extend `scripts/analyze_trueadaptive_test400.py` with a `--reread`
  summary: trigger rate, re-read EM, rows fixed/broken by the re-read. Verify
  it reproduces the v1 dev buckets when run on the v1 dev file (no re-reads).

## B. Implementation

- [x] B.1 Add `grounded_answer_messages(question, claims, paras)` to
  `src/llm/prompts.py` (verified-claims block first, then the context block;
  system prompt per `design.md`).
- [x] B.2 In `run_erag` (`src/systems/erag.py`), after the hop loop and before
  Step 12, add the conditional re-read behind `erag.ground_final_read`
  (default false): trigger on draft "unknown" or draft-not-in-answer-claim;
  replace the draft only on a non-"unknown" re-read; log `grounded_reread`,
  `reread_trigger`, `reread_answer` per record. Keep the original draft in
  the trace's last hop entry.
- [x] B.3 Run the fast test suite (cache, config, metrics, erag, retrieval)
  and the new A.1 tests. All green before any live run.

## C. Dev-100 BM25 A/B (live — needs a Groq key, transiently, none saved)

- [ ] C.1 Run Dev-100 BM25 with the flag ON, reusing namespace
  `dev_trueadaptive_v1_bm25` deliberately (see proposal.md, Impact — the A/B
  isolates the re-read; all other calls replay v1's cached completions).
  Output to a new file (do not overwrite the v1 dev file).
  Prepared command (verified 2026-11-09 against `run_experiment.py`:
  out_path is `{out_dir}/{run.name}.jsonl`, `--set` takes dotted keys;
  needs a Groq key transiently, none saved):
  `HF_HUB_DISABLE_XET=1 NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 GROQ_API_KEY=<transient> .venv/bin/python scripts/run_experiment.py --config configs/base.yaml configs/erag_trueadaptive.yaml --set retrieval.retriever_type=bm25 --set run.cache_namespace=dev_trueadaptive_v1_bm25 --set run.name=erag_trueadaptive_bm25_dev_reread --set erag.ground_final_read=true`
  Then analyze with: `.venv/bin/python scripts/analyze_trueadaptive_test400.py --reread --ta-dev results/trueadaptive/erag_trueadaptive_bm25_dev_reread.jsonl`
- [ ] C.2 Analyze with the script from A.2: EM, F1, mean calls, trigger rate,
  re-read EM, rows fixed/broken, and the 70-row / 40-row buckets recomputed on
  the dev file. Compare against v1 dev (EM 0.56, 4.58 calls/Q).

## D. Gate

- [ ] D.1 Proceed only if: EM is not below v1 dev (0.56); the 70-row / 40-row
  buckets improve or do not worsen; mean calls rise by ≤ 0.5/Q; trigger rate
  ≤ 40% on dev. If the gate fails, record the result, do not tune the
  thresholds to compensate, and either try Variant B (design.md, Mechanism 2)
  as its own change or drop the mechanism.
- [ ] D.2 Commit the change (code + tests + config note + dev results) on
  `trueadaptive`. Do NOT run Test-400 for this step — the confirmation run
  comes once, after all tuning steps.

## E. Archive + next step

- [ ] E.1 Mark this change complete, archive it
  (`openspec archive tune-reader-grounding`), and start the next change
  (`tune-claim-extraction`, step 2) the same way: proposal first, code second.
