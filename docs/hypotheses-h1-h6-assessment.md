# H1–H6 hypothesis assessment (2026-11-09)

Assessment of the six hypotheses from the Nov 4, 2026 report
(`~/workspace/user/files/ERAG_Human_Style_Research_Report_FULL_ONE.pdf`),
computed from stored results only — no live calls.
Script: `scripts/analyze_hypotheses_h1_h6.py` (repo helpers
`src/eval/metrics.py`, `src/eval/stats.py`; bootstrap seed 0, n=10,000;
AUROC CI n=2,000). Machine-readable results:
`results/hypotheses_h1_h6.json`.

Conventions: result rows deduped by id keeping the LAST row (resume-retried
questions leave a stale failed row); paired comparisons use identical id
ordering; EM/F1 are the stored per-row values (repo `exact_match`).

## Verdicts at a glance

| ID | Verdict | One line |
|----|---------|----------|
| H1 | **SUPPORTED** (interim, v1 system) | TA beats Standard-BM25: dEM +0.0725, 95% CI [0.0350, 0.1125]; dF1 +0.0730, CI [0.0351, 0.1114]; McNemar p=0.00034 |
| H2 | **PENDING** | No labelled NLI evaluation existed; pair set (60 pairs) being built and run separately |
| H3 | **SUPPORTED, but weaker for TrueAdaptive** | TA AUROC(c0) 0.5915, CI [0.5421, 0.6391] — excludes 0.5, but below Reference 0.6519 / Balanced 0.6279 |
| H4 | **NOT TESTED on Test-400; dev interim inconclusive** | Dev dF1 +0.0304, CI [-0.0607, 0.1211] (includes 0); Test-400 ablation not run (needs a Groq key) |
| H5 | **NOT SUPPORTED on retrieval reduction** | E5: identical EM (0.4000), 0 calls saved; override 1/1 retrieved false beliefs, 1/5 planted |
| H6 | **SUPPORTED, strongly** | All of TA's gain over IRCoT is in the hop-0-incomplete subset: dEM +0.1146, CI [0.0521, 0.1823]; zero gain where retrieval was complete |

## H1 — E-RAG beats Standard RAG (confirmatory)

- **Criterion:** 95% paired-bootstrap CI of ΔF1/ΔEM excludes 0 in E-RAG's favour.
- **Method:** TrueAdaptive Test-400 (BM25, N=400, deduped from 401 lines)
  vs Standard-BM25 Test-400 (`results/bm25/standard_bm25_test.jsonl`,
  N=400), paired by question id (400/400 overlap).
- **Result:** TA EM 0.4750 vs Standard 0.4025; TA F1 0.6192 vs Standard
  0.5461. dEM +0.0725, 95% CI [0.0350, 0.1125]; dF1 +0.0730, 95% CI
  [0.0351, 0.1114]. McNemar exact: TA-only correct 46, Standard-only
  correct 17, p=0.00034.
- **Context:** Balanced-BM25 vs Standard-BM25: dEM +0.0425, CI [0.0025,
  0.0850]; dF1 +0.0351, CI [-0.0059, 0.0775] — the F1 CI includes 0, so the
  older system does not clear H1 on F1. TrueAdaptive does, on both metrics.
- **Verdict: SUPPORTED (interim).** Two qualifications. (1) This is the v1
  TrueAdaptive system, not the final tuned system: the confirmatory H1
  should be re-run on the frozen tuned system at Phase 2. (2) Holm
  correction across H1/H4 is pending H4's Test-400 p-value (no Test-400
  ablation run exists yet); H1's raw p is reported here.
- **Caveat:** Standard-BM25 rows carry no row-level `retriever` field
  (pre-provenance file); BM25 is established by the file's location in
  `results/bm25/` and the audit record. Standard's answers are 1-call
  reader outputs, so the EM comparison is valid; the provenance is muddy,
  not the numbers.

## H2 — NLI verifier separates supported / contradicted / unresolved

- **Criterion:** macro-F1 and contradicted-class recall both ≥ 0.70
  (proposed threshold, never confirmed — see note).
- **Method:** none existed. A search of the repo found no labelled NLI
  evaluation anywhere: no pair-set results, no per-class precision/recall,
  and the planted 1998-vs-1999 conflict test never ran. The only related
  evidence is the no-NLI dev ablation (EM 0.47 without NLI vs 0.39 with
  all modules on — removing NLI *improved* dev EM in that old run, which
  is either N=100 noise or a sign the verifier was hurting; it is not the
  H2 test either way).
- **Status: PENDING.** A 60-pair labelled set (20 per class, dev questions
  only, strict construction rules: no hypothesis verbatim from the premise;
  contradicted pairs flip exactly one checkable fact; unresolved pairs
  concern entities absent from the premise) is being built and run against
  the repo's own NLI (`cross-encoder/nli-deberta-v3-base`, cached locally).
  Outputs: `data/nli_eval_pairs.jsonl`, `results/nli_eval_h2.jsonl`.
- **Note:** the 0.70 threshold was "proposed, confirm on Day 2" in the
  report and was never confirmed. Before the H2 result is judged, the
  threshold needs a dated confirmation (or a stated reason for keeping
  0.70) — recorded here as an amendment to make, not a rewrite.

## H3 — Higher self-consistency goes with correct answers

- **Criterion:** AUROC CI excludes 0.5.
- **Method:** AUROC of initial self-consistency confidence (c0) vs
  correctness (em), Test-400, with bootstrap CI. H3 is about
  *self-consistency*, so c0 is the correct field — not `answer_conf`
  (final confidence).
- **Result:** TrueAdaptive AUROC(c0) 0.5915, 95% CI [0.5421, 0.6391] —
  excludes 0.5. Reference 0.6519 [0.6033, 0.6995]; Balanced 0.6279
  [0.5837, 0.6717]. TA's ECE 0.4539 / Brier 0.4296 are worse than
  Reference (0.3868 / 0.2796).
- **Verdict: SUPPORTED, but weaker for TrueAdaptive.** The criterion is
  met, yet TA's confidence is markedly less discriminative than the older
  systems'. The likely cause is the adaptivity itself: the Fast-Path gate
  sets c0 = min_eff on skipped rows (many rows share one value), and
  sequential SC (M=1→3) gives coarser confidence granularity than fixed
  5-sample SC. Fewer samples bought efficiency at the price of signal
  quality — the same warning Adaptive-RAG's oracle gap carries.
- **Discrepancy explained:** the older cost CSV reported Reference AUROC
  0.7368. That used `answer_conf` (final confidence), not c0. Recomputed
  here: AUROC(answer_conf) Reference 0.7368 (matches the CSV exactly),
  Balanced 0.7290, TA 0.6286. The CSV is consistent; the two fields measure
  different things, and H3 is about c0.

## H4 — Adaptive retrieval beats the no-adaptive ablation at acceptable cost

- **Criterion:** ΔF1 CI excludes 0 AND latency within 3× Standard RAG
  (proposed limit).
- **Method (dev interim only):** full E-RAG Active vs no-adaptive ablation
  (hop limit 0) on Dev-100, paired (100/100 ids).
- **Result (dev):** full EM 0.3900 / F1 0.4800 at 14.72 calls; no-adaptive
  EM 0.3700 / F1 0.4496 at 7.00 calls. dF1 +0.0304, 95% CI [-0.0607,
  0.1211]; dEM +0.0200, CI [-0.0700, 0.1100]; McNemar p=0.8318. The CIs
  include 0 — on Dev-100 the adaptive-vs-none difference is inside noise,
  as expected at N=100.
- **Verdict: NOT TESTED (confirmatory).** The Test-400 ablation has not
  run. Prepared run (needs a Groq key, ~20–30 min, ~1,500–2,000 calls,
  fresh namespace so it is all-live):

  ```
  .venv/bin/python scripts/run_experiment.py --config configs/erag_trueadaptive.yaml \
    --set retrieval.retriever_type=bm25 run.cache_namespace=test_noadaptive_v1_bm25 \
    run.name=erag_ablate_no_adaptive_test erag.ablate=[no_adaptive]
  ```

  (Same frozen TrueAdaptive config as the v1 Test-400 run, plus
  `erag.ablate=[no_adaptive]`; data split is test by default in that
  config — verify before running.)
- **The 3× latency bound is a problem, stated plainly.** As literally
  written it is not met by any multi-hop system in the stored data:
  TrueAdaptive mean wall latency 5.92s vs Standard-BM25 0.28s (21×);
  on dev, full Active 23.75s vs Standard 0.91s (26×). But those wall
  latencies are confounded by cache state (Standard's runs are heavily
  cache-replayed; TA's was all-live), so the ratio is not a clean
  measurement. More fundamentally, the bound contradicts the report's own
  numbers: its worst-case estimate was ~18 calls/Q for E-RAG vs 1 for
  Standard, and any system making >3 calls/Q exceeds 3× a 1-call baseline
  on calls alone (TA 4.78×, Balanced 8.95×, even IRCoT 2.54× is close to
  the line). The bound was a proposed limit, never confirmed. It needs a
  dated clarification before Phase 4 — e.g. latency within 3× *IRCoT*,
  or cost-per-correct-answer instead of raw latency — not silent
  non-compliance.

## H5 — Verified-belief memory cuts retrieval without lowering accuracy

- **Criterion:** fewer retrievals, ΔEM no worse than −0.02, wrong memories
  overridden. Descriptive only (N≈30 stream).
- **Method:** the E5 files as stored (`results/stream_mem.jsonl`,
  `stream_nomem.jsonl`, `stream_planted.jsonl`; 30 questions each).
- **Result:** memory-off vs memory-on identical — EM 0.4000, F1 0.4828,
  14.30 calls/Q, 0.00 retrievals saved per question. ΔEM +0.0000 (meets
  the ≥ −0.02 half trivially). Planted: 1 of 5 false beliefs overridden
  (Wolfgang Becker, contradicted by fresh evidence and deleted; that
  question still ended unknown, EM 0.0).
- **Verdict: NOT SUPPORTED on the retrieval-reduction half.** No calls
  were saved, so the hypothesis as stated fails even though accuracy did
  not drop. Two precisions on the override half: (1) among false beliefs
  actually *retrieved*, the override rate is 1/1 — the mechanism works
  when it fires; (2) among *planted* beliefs it is 1/5, because the other
  four never passed the similarity threshold (θ_mem 0.75) for any question
  and so were never even considered. The test as designed overstates the
  protection: the denominator that matters is retrieved beliefs, and the
  four unretrieved beliefs are a coverage gap (read threshold too strict,
  or stream questions that did not match).
- **The used passages were true stream beliefs.** Memory fired on the
  same two questions in the clean run (no planting), so the used beliefs
  came from earlier questions in the stream, not from the planted set.
  (Their texts are not recoverable from the stored rows — the trace pools
  record titles only, and memory passages are not reflected there. A
  provenance gap in E5's logging.)
- **What remains:** the re-test on the tuned system (master plan Phase 1
  Step 6). If that is also null, H5 stays unsupported and the paper
  reports memory as mechanism-verified, effectiveness-not-demonstrated.

## H6 — Gains concentrate where initial retrieval missed a paragraph

- **Criterion:** the E-RAG gain is larger in the incomplete-retrieval
  subset than in the complete subset.
- **Method:** hop-0 retrieval completeness per question = gold titles in
  `trace[0]` pool (hop 0, top-3) vs gold titles from the test manifest's
  supporting facts. Split: complete (hop-0 recall = 1.0, n=208) vs
  incomplete (recall < 1.0, n=192). Gain = TrueAdaptive minus IRCoT (the
  multi-hop baseline), paired bootstrap CI, McNemar.
- **Result:** complete subset — TA EM 0.5769, IRCoT EM 0.5769, dEM 0.0000,
  95% CI [-0.0337, 0.0337], p=1.0; dF1 -0.0169, CI [-0.0467, 0.0129].
  Incomplete subset — TA EM 0.3646, IRCoT EM 0.2500, dEM +0.1146, 95% CI
  [0.0521, 0.1823], p=0.00094; dF1 +0.1261, CI [0.0594, 0.1923].
- **Verdict: SUPPORTED, strongly.** Literally all of TrueAdaptive's gain
  over IRCoT is in the hop-0-incomplete subset; where the first retrieval
  was already complete, the gain is exactly zero on EM (and slightly
  negative, non-significant, on F1). The adaptive hops earn their keep
  precisely when the first retrieval fails — which is the mechanism the
  hypothesis claims.
- **Correction to an earlier reading:** the assessment given on 2026-11-09
  said the evidence "leans against" H6, on the basis that TA's wins over
  IRCoT have high *final* recall (0.987) and most wrong answers had full
  recall. That reading used the wrong measure. Final recall is high in
  TA's wins *because the hops retrieved the missing gold* — which is
  exactly H6's mechanism. Hop-0 recall is the correct operationalization,
  and it reverses the conclusion. The earlier statement is withdrawn.

## What is still open (after this assessment)

1. **H2** — pair set + evaluation running separately; verdict pending.
2. **H1 (confirmatory)** — re-run on the frozen tuned system at Phase 2;
   Holm correction across H1/H4 once H4's Test-400 p-value exists.
3. **H4 (confirmatory)** — Test-400 no-adaptive ablation run (command
   above; needs a Groq key) + a dated clarification of the 3× latency
   bound.
4. **H5** — re-test on the tuned system (Phase 1 Step 6).
5. **H2 threshold** — dated confirmation of the 0.70 threshold (or a
   stated reason for keeping it) before the H2 result is judged.
