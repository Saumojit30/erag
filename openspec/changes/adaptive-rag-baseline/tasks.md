# Tasks: Adaptive-RAG routing baseline (Phase 2 addition)

Drafted 2026-11-10 from `docs/publication-ready-plan.md` (§3.3, D3),
the Adaptive-RAG paper (`~/workspace/user/files/Adaptive-RAG.pdf`),
and the user's 2026-11-10 decision to add the baseline alongside
IRCoT, with planning and execution delegated to the assistant.
Branch `trueadaptive`. Nothing is pushed.

## 0. OpenSpec change (before any code)

- [ ] 0.1 Create `openspec/changes/adaptive-rag-baseline/` with
  `proposal.md`, `design.md`, `tasks.md` (this file),
  `specs/adaptive-rag-baseline/spec.md`.
- [ ] 0.2 Validate with the local CLI:
  `~/workspace/tools/openspec/node_modules/.bin/openspec validate --all`
  and `.../openspec validate adaptive-rag-baseline` — must be 0
  failed before any code change. (Spec format: `## ADDED
  Requirements` + `### Requirement:` + `#### Scenario:` blocks, as
  in the step-7 change.)

## A. Training set (no LLM calls, no `src/` change)

- [ ] A.1 Build `data/adaptive_rag_training.jsonl`: one row per
  question with `question`, `label` (A/B/C), `source`. Labels from
  dataset properties only — HotpotQA dev (`data/manifests/dev.jsonl`,
  N=100, class C); a SQuAD v1 train sample (class B); class A by the
  construction decided and recorded here *before* training
  (candidates: a TriviaQA sample, or SQuAD questions the closed-book
  system answers correctly on a small labeled sample — record the
  choice, its definition, and its counts in this task when done).
  Target ~3,000 questions, roughly balanced. Reserve a 20% held-out
  split (never trained on) and record the split. Record before any
  training: sources, class counts (A/B/C), the majority-class rate
  on the held-out split (the AR-1 floor). The build script asserts
  no Test-400 row enters the file (assert on the input paths —
  test files are never valid input here). No Groq key needed.
- [ ] A.2 Download the classifier base model (`distilbert-base-uncased`)
  from the HF hub with `HF_HUB_DISABLE_XET=1` (the same quirk as
  MiniLM). If the download fails, record the failure and switch to
  the fallback in design.md (sklearn logistic regression on cached
  MiniLM embeddings — no download needed) — and record which
  classifier ran, in the artifact, the commit, and the paper. No
  third classifier.

## B. Classifier training + Gate AR-1 (offline, no Groq key)

- [ ] B.1 Training script `scripts/train_adaptive_rag_router.py`:
  fine-tunes DistilBERT (or the fallback) on the A.1 training set,
  evaluates on the 20% held-out split, and writes the classifier
  artifact (model files + `configs/adaptive_rag_classifier/`
  metadata: model type, training file, N, class counts, date,
  held-out accuracy, majority-class rate). Tests first: mocked
  tests proving the script refuses test files, and that the router
  loads the artifact and returns a valid (route, probability) pair
  for a sample question.
- [ ] B.2 Gate AR-1 (pre-registered, design.md): held-out routing
  accuracy strictly above the majority-class rate, AND the Dev-100
  route distribution non-degenerate (no single route above 90% of
  questions — compute the distribution by classifying the 100 dev
  questions offline, no LLM calls). If it fails, stop — no wiring,
  no live run; record the accuracy and close the change as a
  negative result.

## C. Router wiring + analyzer (only if Gate AR-1 passes)

- [x] C.1 New module `src/systems/adaptive_rag.py` with
  `run_adaptive_rag(item, retriever, llm, cfg, tracker)` (design.md
  §The router): classify, dispatch to the existing strategy
  functions, return their result + `route` + `route_p`. Add the
  `system == "adaptive_rag"` branch to `dispatch()` in
  `scripts/run_experiment.py`. Classifier loaded once per process;
  missing file is a loud startup error, never a silent fall-through.
  No changes to `run_standard`, `run_closed_book`, `run_ircot`, or
  the frozen TrueAdaptive config. Tests first: mocked-LLM tests in
  `tests/test_adaptive_rag.py` proving each route dispatches to the
  right strategy (mock the classifier to force A, B, and C in turn),
  that `route`/`route_p` are recorded, and that a missing
  classifier file fails loudly.
- [x] C.2 Analyzer section: add a `--adaptive-rag` section to
  `scripts/analyze_trueadaptive_test400.py` (new section number
  after 15; flags `--adaptive-rag` + `--adaptive-rag-baseline
  <ta_file>` + `--adaptive-rag-ircot <ircot_file>`). It reports, for
  the Adaptive-RAG run file: N (deduped), failed, EM, F1, mean
  `llm_calls`/Q, route distribution (counts + EM + calls/Q per
  route), and the H8 paired comparison vs the tuned TrueAdaptive
  file and vs IRCoT (McNemar exact two-sided, ΔEM with 95% paired
  bootstrap CI). Tests first in a new
  `tests/test_analyzer_adaptive_rag.py`; verification: on the
  existing IRCoT Test-400 file it reproduces EM 0.4200, 2.545
  calls/Q. Do NOT break the existing sections.
- [x] C.3 Fast suite green after C.1–C.2. The known pre-existing
  failure (`test_retry_exhaustion_raises_runtime_error`) stays
  untouched.

## D. Dev-100 sanity run (only if Gate AR-1 passed; needs a Groq key, transiently, none saved)

- [x] D.1 One run: system `adaptive_rag`, Dev-100 BM25, fresh
  namespace `dev_adaptive_rag_v1_bm25`, output
  `results/adaptive_rag/adaptive_rag_dev_bm25.jsonl`. Single
  `--set` with `retrieval.retriever_type=bm25`. Then analyze with
  the C.2 section: route distribution, EM, F1, calls/Q. This run
  is a sanity check only (the dev questions are class-C training
  rows, so the distribution is expected to skew to C) — it is not
  a gate and its numbers are not the verdict.
  DONE 2026-11-10: 100/100, 0 failed, 1:52 wall, all-live
  (cache_hits/Q 0.00). Routes A0/B45/C55 — EXACTLY the offline
  distribution. EM 0.5000, F1 0.6018, 1.78 calls/Q, coverage 0.780.
  Route B (n=45): EM 0.6667, 1.00 calls/Q. Route C (n=55): EM
  0.3636, 2.42 calls/Q. Section 16: vs tuned TA (dev) dEM +0.0000
  (McNemar 3/3, p=1); vs IRCoT (dev) dEM +0.0600 (p=0.3075).
  Sanity PASSES — the router works end-to-end. The change stays
  ACTIVE: E.1 (Test-400) runs after the Phase 2 tuned file exists,
  then F.1/F.2/F.3 close it.

## E. Test-400 run + Gate AR-2 (needs a Groq key, transiently, none saved)

- [ ] E.1 One run: system `adaptive_rag`, Test-400 BM25 k=3,
  distractor, fresh namespace `test_adaptive_rag_v1_bm25`, output
  `results/adaptive_rag/adaptive_rag_test_bm25.jsonl`. Detached,
  checkpoint resume. Then analyze with the C.2 section against the
  Phase 2 tuned TrueAdaptive Test-400 file and the fresh IRCoT
  Test-400 file.
- [ ] E.2 Gate AR-2 / H8 verdict (pre-registered, design.md): N=400
  deduped, 0 failed; H8 judged by paired McNemar TA vs
  Adaptive-RAG, α=0.05, primary EM, with calls/Q reported
  alongside. Record the verdict (H8 supported / not supported)
  with the numbers, whether or not it favors TrueAdaptive — a
  baseline that beats the tuned system is a result, not a failure
  to hide.

## F. Commit + archive + record

- [ ] F.1 Commit the change (training set + training script +
  classifier artifact + router + tests + analyzer section + dev and
  test result files) on `trueadaptive`, with the AR-1/AR-2 verdicts
  and per-route numbers in the commit message. Do NOT commit
  `results/cache.sqlite` or `results/nli_memo.pkl`.
- [ ] F.2 Archive the change with `openspec archive
  adaptive-rag-baseline -y` (always `-y` in this environment).
  Re-validate: `openspec validate --all` must be 0 failed.
- [ ] F.3 Update the record the same day: master plan §4 (dated
  amendment adding the baseline to the Phase 2 run list — write
  this amendment *before* the E.1 run), §12 log entry,
  `docs/hypotheses-current-status.md` (new H8 entry with the
  verdict), `docs/retrospective-changelog.md` (§2 entry),
  `docs/assumptions-vs-outcomes.md` (assumed vs actual for AR-1,
  AR-2, and H8).
