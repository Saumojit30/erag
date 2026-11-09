# Tasks: Tune-Unknown-Prompt (tuning step 3)

Drafted 2026-11-09 from `docs/trueadaptive-test400-error-analysis.md` (§2, §5)
and fresh counts of the unknown rows on the step-2 tuned dev file (proposal.md,
Why). Branch `trueadaptive`. Nothing is pushed. Do not start the build until
the proposal is approved — the user approves by saying go (or by tapping the
offer); the build then follows this file.

## 0. OpenSpec change (before any code)

- [x] 0.1 Create `openspec/changes/tune-unknown-prompt/` with `proposal.md`,
  `design.md`, `tasks.md` (this file), `specs/unknown-prompt/spec.md`.
- [ ] 0.2 Validate with the local CLI:
  `~/workspace/tools/openspec/node_modules/.bin/openspec validate --all`
  and `.../openspec validate tune-unknown-prompt` — must be 0 failed before
  any code change.

## A. Tests first (mocked LLM, no production change yet)

- [ ] A.1 In `tests/test_prompts.py` (new file if none exists), add mocked-LLM
  tests: `answer_messages` with variant `"base"` returns the current
  `ANSWER_SYSTEM` text; `"best_guess"` returns the best-guess text
  (contains "best short answer" and "'unknown' only if"); `"cite_first"`
  returns the cite-first text (contains "single sentence" and "most
  relevant"); an unknown variant name falls back to `"base"`; the default
  (no variant passed) is `"base"`. The grounded re-read prompt is unchanged.
- [ ] A.2 Extend `scripts/analyze_trueadaptive_test400.py` with an
  `--unknown` summary for a TA dev file: unknown count (flag `unknown`,
  not abstained), system-abstained count, and — when given a second file
  (`--unknown-baseline`) — for rows that were unknown in the baseline file
  and are answered in this file, their EM (recovered-row accuracy). Verify
  it reproduces the step-2 tuned dev baseline (7 model-unknown, 8
  system-abstained) when run on
  `results/trueadaptive/erag_trueadaptive_bm25_dev_claims.jsonl`. Verify
  the measurement path BEFORE any live run (design.md correction note):
  the flags the analyzer reads must be fields the runner actually writes.

## B. Implementation

- [ ] B.1 Add the two variant system strings to `src/llm/prompts.py` and
  variant selection in `answer_messages(question, paras, variant="base")`.
  Unknown variant falls back to `"base"`. No change to
  `GROUNDED_ANSWER_SYSTEM`, `grounded_answer_messages`, or
  `CLOSED_BOOK_SYSTEM`.
- [ ] B.2 Plumb the flag: the `run_erag` draft calls pass
  `cfg["erag"].get("unknown_prompt", "base")`; config default `"base"`
  (no behavior change unless the flag is set). No change to any other file.
- [ ] B.3 Run the fast test suite (cache, config, metrics, erag, retrieval,
  claims, prompts) and the new A.1 tests. All green before any live run.

## C. Dev-100 BM25 A/Bs (live — needs a Groq key, transiently, none saved)

- [ ] C.1 Variant A (`best_guess`): run Dev-100 BM25 on top of the step-2
  tuned system (`ground_final_read=true`, `max_claims=8` stay on). Single
  `--set` with all overrides (step-1 lesson: repeated `--set` flags
  overwrite; only the last survives). Output to a new file (do not
  overwrite any v1, step-1, or step-2 dev file). Prepared command (verify
  against `run_experiment.py` before running; needs a Groq key transiently,
  none saved):
  `HF_HUB_DISABLE_XET=1 NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 GROQ_API_KEY=<transient> .venv/bin/python scripts/run_experiment.py --config configs/base.yaml configs/erag_trueadaptive.yaml --set retrieval.retriever_type=bm25 run.cache_namespace=dev_trueadaptive_v1_bm25 run.name=erag_trueadaptive_bm25_dev_unknown_a erag.ground_final_read=true erag.max_claims=8 erag.unknown_prompt=best_guess`
  Then analyze with: `.venv/bin/python scripts/analyze_trueadaptive_test400.py --unknown --unknown-baseline results/trueadaptive/erag_trueadaptive_bm25_dev_claims.jsonl --ta-dev results/trueadaptive/erag_trueadaptive_bm25_dev_unknown_a.jsonl`
- [ ] C.2 Variant B (`cite_first`): same command with
  `run.name=erag_trueadaptive_bm25_dev_unknown_b` and
  `erag.unknown_prompt=cite_first`; analyze the same way. Each variant is
  its own A/B; both are reported even if one fails.
- [ ] C.3 Compare each variant against the step-2 tuned dev file (EM 0.54,
  F1 0.6391, 4.65 calls/Q, 7 model-unknown, 8 system-abstained).

## D. Gate (per variant, pre-registered)

- [ ] D.1 A variant proceeds only if: unknown count falls by ≥3 rows on dev
  (7 → ≤4); among rows that change from unknown to answered, at least half
  are correct (recovered-row EM ≥ 0.5); EM not below the step-2 tuned dev
  (0.54); mean calls rise by ≤ 0.5/Q. If a variant fails, record the result
  and do not tune the prompt to compensate. Selection between passing
  variants follows the pre-registered rule in design.md (larger unknown
  reduction; tie → `best_guess`). If neither passes, record the negative
  result and drop the mechanism — no third variant inside this change.
- [ ] D.2 Commit the change (code + tests + dev results) on `trueadaptive`.
  If a variant passes, record the tuned `erag.unknown_prompt` value in the
  frozen-config note (the tuned config file itself is written at the end
  of Phase 1, not here). Do NOT run Test-400 for this step — the
  confirmation run comes once, after all tuning steps.

## E. Archive + next step

- [ ] E.1 Mark this change complete, archive it
  (`openspec archive tune-unknown-prompt -y`), and start the next change
  (`tune-theta-abs`, step 4) the same way: proposal first, code second.
  Step 4 needs the user's theta_abs goal decision (selective answering vs
  max EM) before its proposal is written — if undecided, skip it.
