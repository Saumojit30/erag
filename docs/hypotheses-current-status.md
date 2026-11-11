# Current hypotheses, TrueAdaptive status, and what comes next

Date: 2026-11-09. Branch: `trueadaptive` (local only, never pushed).
HEAD at writing: `348735c`. Companion documents: the H1–H6 assessment
(`docs/hypotheses-h1-h6-assessment.md`, with the script
`scripts/analyze_hypotheses_h1_h6.py` and the machine-readable results
`results/hypotheses_h1_h6.json`) and the master plan
(`docs/tuning-master-plan.md`, which is the pre-registered record for
Phase 2).

This file answers four questions in one place: what the hypotheses are
and where each stands; where TrueAdaptive is now; what the next steps
are; and how the hypotheses are allowed to change later — versus the
sequence adaptive → tune → test on test data → new dataset.

## 1. The six hypotheses — claim, evidence, verdict, what remains

The hypotheses come from the Nov 4, 2026 report
(`~/workspace/user/files/ERAG_Human_Style_Research_Report_FULL_ONE.pdf`).
H1 and H4 are the confirmatory pair (McNemar paired EM, Holm correction
across the two); every other comparison, including E-RAG vs IRCoT, is
exploratory per the report. The primary research question they serve:
"Can evidence-aware uncertainty estimation and claim-level verification
guide adaptive retrieval in multi-hop RAG, improving answer reliability
at a reasonable computational cost?"

### H1 — E-RAG beats Standard RAG (confirmatory)

- **Claim:** the epistemic system answers better than a fixed one-pass
  Standard RAG pipeline. **Criterion:** the 95% paired-bootstrap CI of
  ΔF1/ΔEM excludes 0 in E-RAG's favour.
- **Evidence:** TrueAdaptive vs Standard-BM25, Test-400 (N=400, paired
  by question). TA EM 0.4750 vs Standard 0.4025; TA F1 0.6192 vs
  Standard 0.5461. ΔEM +0.0725, 95% CI [0.0350, 0.1125]; ΔF1 +0.0730,
  CI [0.0351, 0.1114]; McNemar p=0.00034. (For context, the older
  Balanced system clears H1 on EM but not on F1 — its ΔF1 CI includes
  0. TrueAdaptive clears both.)
- **Verdict: SUPPORTED (confirmatory re-run, 2026-11-11).** Tuned
  system vs Standard-BM25, Test-400 (N=400, paired): tuned EM
  0.4500 vs Standard 0.4025; ΔEM +0.0475, 95% CI [+0.0150,
  +0.0800]; McNemar b=34, c=15, p=0.0094. Holm across H1/H4:
  adjusted p 0.0188 < 0.05 — H1 survives the correction. The v1
  interim result (ΔEM +0.0725, p=0.00034) is superseded by this
  re-run as the confirmatory evidence; both point the same way.
- **Remains:** nothing for H1 on HotpotQA. Phase 3 tests the
  generalization of the same claim on new datasets (H9).

### H2 — The NLI verifier separates supported / contradicted / unresolved

- **Claim:** the NLI verifier's verdicts track the truth — a claim the
  evidence supports is called supported, a claim the evidence contradicts
  is called contradicted, and a claim the evidence does not address is
  called unresolved. **Criterion:** macro-F1 and contradicted-class
  recall both ≥ 0.70. **Dated confirmation 2026-11-10:** the 0.70
  threshold is confirmed as-is (under the delegated mandate, proceeding
  on the recommendation). Re-thresholding after seeing the 0.6825 miss
  would be cherry-picking; the narrow miss stands as a miss.
- **Evidence:** no labelled evaluation existed, so one was built for
  this assessment: 60 pairs (20 per class) from 20 dev questions,
  premise = the gold paragraphs' sentences, hypotheses written in own
  words (no hypothesis verbatim from its premise; contradicted pairs
  flip exactly one checkable fact, recorded; unresolved pairs concern
  entities absent from the premise). Model: the repo's own NLI
  (`cross-encoder/nli-deberta-v3-base`). Files:
  `data/nli_eval_pairs.jsonl`, `results/nli_eval_h2.jsonl`; repro
  scripts in `scripts/` (`build_nli_pairs_h2.py`,
  `run_nli_h2.py`, `debug_nli.py`). Confusion matrix (rows gold, cols
  predicted [supported, contradicted, unresolved]): supported [12, 1,
  7]; contradicted [4, 15, 1]; unresolved [0, 6, 14].
  **Macro-F1 0.6825; contradicted recall 0.75.**
- **Verdict: NOT SUPPORTED — a narrow miss.** Contradicted recall
  passes (0.75 ≥ 0.70) but macro-F1 misses (0.6825 < 0.70). With N=60
  the miss is within noise — one more correct supported prediction
  would change it. The main weakness is supported recall (0.60): 7
  supported claims were called unresolved. The verifier is
  conservative, not trigger-happy.
- **Why it failed (per-window debug runs):** (1) `verify()` scores
  independent 2-sentence windows and takes the max, so a claim needing
  facts from two paragraphs scores neutral ≈ 1.0 — ERag's extracted
  claims are exactly this kind of multi-hop synthesis. (2)
  Same-topic/different-entity is read as contradiction, not neutral:
  the entity extractor fragments multi-word names ("University of
  Miami" → `University` + `Miami's`), and the cross-encoder treats a
  different-entity claim as false rather than unaddressed — in
  production this marks claims about absent entities "contradicted"
  instead of "unresolved", corrupting the belief graph's gap
  computation. (3) The tie-break (supported if entailment ≥
  contradiction − 0.05) overrules a near-certain contradiction
  (0.9996) with a strong entailment on a different aspect of the same
  claim. (4) Max-aggregation picks the worst window: entailment fires
  on windows lacking the evidence, from title/entity overlap.
- **Remains:** nothing to re-run for the threshold — it is confirmed
  (2026-11-10, above). Optionally, a threshold-sensitivity check on the
  same 60 pairs — but any re-thresholding needs a fresh pair set before
  it can be claimed.

### H3 — Higher self-consistency goes with correct answers

- **Claim:** questions the system is more self-consistent on are more
  often answered correctly — i.e. the confidence signal means
  something. **Criterion:** the AUROC CI excludes 0.5. H3 is about
  *self-consistency*, so the correct field is c0 (initial
  self-consistency), not `answer_conf` (final confidence).
- **Evidence:** AUROC(c0) on Test-400. TrueAdaptive 0.5915, 95% CI
  [0.5421, 0.6391]; Reference 0.6519 [0.6033, 0.6995]; Balanced 0.6279
  [0.5837, 0.6717]. TA's calibration is also worse (ECE 0.4539 /
  Brier 0.4296 vs Reference 0.3868 / 0.2796). Note: the older cost CSV
  reported Reference AUROC 0.7368 — that used `answer_conf`, not c0;
  recomputed both ways the numbers match exactly, so the CSV is
  consistent and the two fields simply measure different things.
- **Verdict: SUPPORTED, but weaker for TrueAdaptive.** The criterion
  is met, yet TA's confidence discriminates markedly worse than the
  older systems'. The likely cause is the adaptivity itself: the
  Fast-Path gate stamps one shared confidence value on skipped rows,
  and sequential SC (M=1→3) gives coarser granularity than fixed
  5-sample SC. Fewer samples bought efficiency at the price of signal
  quality — the same warning Adaptive-RAG's oracle gap carries
  (their oracle classifier would jump HotpotQA F1 53.82 → 64.00).
- **Remains:** nothing to re-run for H3 itself. The implication to
  carry forward: if a later tuning step coarsens the confidence signal
  further (e.g. more aggressive Fast-Path gating), H3 should be
  re-checked on the tuned system alongside H1.
- **Step-7 note (2026-11-09, Gate B PASS):** the learned continuation
  policy is a direct test of whether the confidence signal, combined
  with the other hop-0 features, can drive effort better than fixed
  thresholds — and on Dev-100 it can, modestly: live EM 0.5000 at
  4.07 calls/Q vs the static tuned baseline 0.5100 at 4.65, with
  STOP-rows EM 0.5679 vs CONTINUE-rows 0.2105 (the policy stops on
  the better questions). But the signal's limits show in the
  composition: the saving is bought partly by stopping on wrong
  drafts, and the live EM sits exactly at the gate floor. H3's
  verdict does not change (it is about c0 alone); the policy result
  belongs in the paper's adaptivity discussion, not as H3 evidence.

### H4 — Adaptive retrieval beats the no-adaptive ablation at acceptable cost (confirmatory)

- **Claim:** doing retrieval adaptively (only when the system is
  uncertain) beats doing the full pipeline with adaptivity switched off,
  without costing too much. **Criterion:** ΔF1 CI excludes 0 AND cost
  per correct answer of the adaptive system is no worse than the
  no-adaptive ablation's. **Dated clarification 2026-11-10:** the cost
  bound replaces the proposed "latency within 3× Standard RAG" bound
  (under the delegated mandate, proceeding on the recommendation, and
  before the Test-400 ablation run). Cost per correct answer is measured
  in LLM calls: total `llm_calls` divided by the number of correct
  answers, computed from the stored rows by the repo's exact match. The
  dollar conversion (Groq per-token pricing, verified at manuscript
  time) is a reporting step (publication plan D6), not a second bound.
  The 3× latency bound is retired because, as written, no multi-hop
  system can meet it (see the problem stated below) — and a bound no
  honest system can meet is not a bound, it is a trap.
- **Evidence (Test-400, 2026-11-11):** tuned vs no-adaptive ablation,
  paired (N=400): tuned EM 0.4500 / F1 0.5905 at 4.13 calls/Q;
  no-adaptive EM 0.4350 / F1 0.5781 at 2.28 calls/Q. ΔEM +0.0150,
  95% CI [-0.0150, +0.0450]; ΔF1 +0.0124, CI [-0.0190, +0.0439];
  McNemar b=21, c=15, p=0.4050. Cost per correct answer: tuned
  9.18 vs no-adaptive 5.25. File:
  `results/trueadaptive/erag_ablate_no_adaptive_test.jsonl`
  (N=400, 0 failed, cache_hits/Q 0.000). (Dev interim, for
  reference: ΔF1 +0.0304, CI [-0.0607, 0.1211], p=0.8318 — same
  direction, also inside noise.)
- **Verdict: NOT SUPPORTED (confirmatory).** Both criterion legs
  fail: the ΔF1 CI includes 0, and the adaptive system costs MORE
  per correct answer than the ablation. Holm across H1/H4: adjusted
  p 0.405. The paper reports tuning's adaptivity as a negative
  result on this leg; the H1 claim (E-RAG beats Standard) is
  unaffected.
- **The 3× latency bound is a problem, stated plainly.** As literally
  written it is not met by any multi-hop system in the stored data:
  TrueAdaptive mean wall latency 5.92s vs Standard-BM25 0.28s (21×);
  on dev, full Active 23.75s vs Standard 0.91s (26×). Those wall
  latencies are confounded by cache state (Standard's runs are heavily
  cache-replayed; TA's was all-live), so the ratio is not a clean
  measurement — but more fundamentally, the bound contradicts the
  report's own numbers: its worst-case estimate was ~18 calls/Q for
  E-RAG vs 1 for Standard, and any system making >3 calls/Q exceeds
  3× a 1-call baseline on calls alone (TA 4.78×, Balanced 8.95×).
  The bound was a proposed limit, never confirmed.
- **Remains:** nothing for H4 on HotpotQA. The bound was clarified
  before the run (2026-11-10) and the result was reported against
  it, not dropped — the silent non-compliance the note warned
  about did not happen.
  dropping it.

### H5 — Verified-belief memory cuts retrieval without lowering accuracy

- **Claim:** the BeliefMemory (verified beliefs carried across
  questions in a stream) reduces retrieval calls without hurting
  accuracy, and wrong memories get overridden. **Criterion:** fewer
  retrievals, ΔEM no worse than −0.02, wrong memories overridden.
  Descriptive only (stream N≈30).
- **Evidence:** the E5 files as stored (`results/stream_mem.jsonl`,
  `stream_nomem.jsonl`, `stream_planted.jsonl`; 30 questions each).
  Memory-off vs memory-on identical — EM 0.4000, F1 0.4828, 14.30
  calls/Q, **0.00 retrievals saved per question**. ΔEM +0.0000 (meets
  the ≥ −0.02 half trivially). Planted: 1 of 5 false beliefs overridden
  (Wolfgang Becker, contradicted by fresh evidence and deleted; that
  question still ended unknown, EM 0.0).
- **Verdict: NOT SUPPORTED on the retrieval-reduction half.** No calls
  were saved, so the hypothesis as stated fails even though accuracy
  did not drop. Two precisions on the override half: among false
  beliefs actually *retrieved*, the override rate is 1/1 — the
  mechanism works when it fires; among *planted* beliefs it is 1/5,
  because the other four never passed the similarity threshold
  (θ_mem 0.75) for any question and so were never even considered. The
  test as designed overstates the protection: the denominator that
  matters is retrieved beliefs, and the four unretrieved beliefs are a
  coverage gap. The two beliefs memory did use were true stream
  beliefs (proven by the clean run using memory on the same two
  questions with nothing planted); their texts are not recoverable
  from the stored rows — the trace pools record titles only, a
  provenance gap in E5's logging.
- **Remains:** the re-test is DONE (2026-11-10, step 6, tuned system,
  all-live arms): mem fired on 1/30 (floor 5/30) — verdict
  "instrument too weak", NOT a clean null. ΔEM +0.0667 and Δcalls/Q
  −0.13 both favor memory but cannot be attributed to it (the single
  fired row changed nothing; the +2 EM rows are noise). Override
  1/1 retrieved (Becker purged); the checker's 2 false-claim flags
  are substring false positives (gold-correct answers, nothing
  retrieved). **H5 stays NOT SUPPORTED, with this dated note: two
  under-powered tests (E5 cache-confounded, step 6 fired 1/30) —
  the paper reports memory as mechanism-verified,
  effectiveness-not-demonstrated, and does not claim a null.**
  Memory stays OFF for Test-400. Note the memory module is
  implemented and wired but disabled by default
  (`memory.enabled: false`) — all results so far are memory-off.

### H6 — Gains concentrate where initial retrieval missed a paragraph

- **Claim:** E-RAG's advantage over a fixed multi-hop baseline comes
  from the cases where the first retrieval was incomplete — the
  adaptive hops earn their keep precisely when the first retrieval
  fails. **Criterion:** the gain is larger in the incomplete-retrieval
  subset than in the complete subset.
- **Evidence:** hop-0 retrieval completeness per question = gold
  titles in `trace[0]` pool (hop 0, top-3) vs gold titles from the
  test manifest's supporting facts. Split: complete (hop-0 recall =
  1.0, n=208) vs incomplete (recall < 1.0, n=192). Gain =
  TrueAdaptive minus IRCoT, paired bootstrap CI, McNemar. Complete
  subset: TA EM 0.5769, IRCoT EM 0.5769, ΔEM 0.0000, 95% CI [−0.0337,
  0.0337], p=1.0; ΔF1 −0.0169, CI [−0.0467, 0.0129]. Incomplete
  subset: TA EM 0.3646, IRCoT EM 0.2500, ΔEM **+0.1146**, 95% CI
  [0.0521, 0.1823], p=0.00094; ΔF1 +0.1261, CI [0.0594, 0.1923].
- **Verdict: SUPPORTED, strongly.** Literally all of TrueAdaptive's
  gain over IRCoT is in the hop-0-incomplete subset; where the first
  retrieval was already complete, the gain is exactly zero on EM (and
  slightly negative, non-significant, on F1). This corrects an earlier
  reading that said the evidence "leans against" H6 because TA's wins
  have high *final* recall — final recall is high in TA's wins
  *because the hops retrieved the missing gold*, which is exactly H6's
  mechanism. Hop-0 recall is the correct operationalization, and it
  reverses the conclusion.
- **Remains:** nothing to re-run for H6 itself. It is the cleanest
  result in the set, and it is the mechanism the paper should lead
  with: adaptive hops help exactly where the first retrieval fails.

### H7 — Each adaptive component carries part of the gain (new, 2026-11-10)

- **Claim:** the tuned system's accuracy/cost trade-off is carried by
  its adaptive components, not by one of them alone — disabling the
  Fast Path or the sequential SC worsens EM or raises calls/Q.
  **Criterion:** SC-off vs tuned (paired, Test-400 BM25): EM lower
  or calls/Q higher; Fast-Path-off vs its eager-SC control (paired,
  Test-400 BM25): EM lower or calls/Q higher. H7 is exploratory (it
  compares system variants, like the ERag-vs-IRCoT comparison); the
  confirmatory claims remain H1 and H4.
- **Evidence (Test-400, 2026-11-11):** SC-off (fixed SC, 5 samples)
  EM 0.4425, F1 0.5748, 6.00 calls/Q vs tuned 0.4500, 4.13 calls/Q;
  dEM +0.0075, CI [-0.0125, +0.0275], p=0.6072 — sequential SC is a
  cost win (~31% fewer calls), not an accuracy win. Fast-Path pair
  (SC eager in both arms): control EM 0.4675, F1 0.5939, 4.83
  calls/Q vs off EM 0.4500, F1 0.5802, 4.86 calls/Q; dEM +0.0175,
  CI [-0.0050, +0.0425], p=0.2100 — directional only. Files:
  `results/trueadaptive/erag_trueadaptive_tuned_sc_fixed_test.jsonl`,
  `results/trueadaptive/erag_fp_control_test.jsonl`,
  `results/trueadaptive/erag_fp_off_test.jsonl` (all N=400, 0
  failed, cache_hits/Q 0.000).
- **Verdict: NOT SUPPORTED.** Neither component shows a significant
  accuracy contribution; SC's contribution is cost, the fast path's
  is directional.
- **Why the Fast-Path-off needs a pair (code reading, 2026-11-10):**
  the publication plan assumed Fast-Path-off is one config flag
  (`erag.ablate=[no_fast]`). Reading `src/systems/erag.py` shows it
  is not: in the frozen system the fast path fires in the deferred-SC
  branch (lines ~258–270), which breaks without consulting `no_fast`
  — and at hop 0 the learned policy has replaced the fast-path
  decision anyway, so `no_fast` alone has ~no effect on the tuned
  system. The flag only bites when SC is NOT deferred (the
  decision-chain branch, line ~324). So the Fast-Path-off is a pair
  with SC eager in both arms (`gate_sc_behind_fast_path=false`):
  control (fast path on) vs `no_fast` (fast path off) — the
  difference isolates the fast path's retrieval-skipping effect with
  SC timing held constant. The SC-off is one run as assumed, except
  it needs both overrides: `erag.sc_mode=fixed` AND
  `erag.sc_samples=5` — the frozen config sets `sc_samples: 3`, so
  `sc_mode=fixed` alone would run fixed SC with 3 samples, not the
  5-sample reference.

### H8 — TrueAdaptive beats the other adaptive baseline (Adaptive-RAG)

- **Claim:** the frozen tuned TrueAdaptive beats Adaptive-RAG (the
  other-adaptive control: a trained router picking no-retrieval /
  single-step / multi-step up front, from the question text alone) on
  HotpotQA Test-400 BM25 EM at equal-or-fewer calls/Q.
  **Criterion:** EM higher AND calls/Q no higher; paired McNemar
  α=0.05. Secondaries: F1, calls/Q, coverage, route distribution,
  per-route EM. H8 is exploratory (it compares two adaptive systems,
  like the ERag-vs-IRCoT comparison); the confirmatory claims remain
  H1 and H4.
- **Evidence (Test-400, 2026-11-11; Gate AR-2 PASS):** Adaptive-RAG
  EM 0.4275, F1 0.5572, 1.68 calls/Q, coverage 0.760 (N=400,
  0 failed, fresh namespace `test_adaptive_rag_v1_bm25`); routes B
  210 / C 190 (A 0, as predicted); route B EM 0.3714 at 1.00 call/Q,
  route C EM 0.4895 at 2.44 calls/Q. Tuned vs AR: dEM +0.0225,
  CI [-0.0100, +0.0550], McNemar b=27, c=18, p=0.2327. AR vs IRCoT:
  0.4275 vs 0.4225, p=0.8238. File:
  `results/adaptive_rag/adaptive_rag_test_bm25.jsonl`; analyzer
  section 16.
- **Verdict: NOT SUPPORTED.** The EM edge is not significant, and
  the tuned system uses 2.5x the calls (4.13 vs 1.68), so the
  equal-or-fewer-calls leg fails outright. Adaptive-RAG ties IRCoT
  at fewer calls — it is the cheapest system per question, not the
  most accurate.

### H9 — The tuned system generalizes to new multi-hop datasets

- **Claim:** the frozen tuned system beats IRCoT on each new dataset's
  test split (2WikiMultiHopQA first, then MuSiQue), not just on
  HotpotQA. **Criterion:** per dataset, EM higher AND paired McNemar
  α=0.05; each dataset is judged on its own (a Win on one does not
  predict the other). H9 is exploratory per dataset; it is the
  Phase 3 claim.
- **Evidence:** none yet — Phase 3 is the evidence (master plan §5).
  No tuning on the new test splits; no re-running Phase 2 to chase a
  Phase 3 number.
- **Verdict: NOT TESTED.**

### H10 — The tuned system is cheaper per correct answer

- **Claim:** the tuned system costs less per correct answer than the
  non-adaptive Balanced system and than IRCoT. **Criterion:** LLM
  calls per correct answer (total `llm_calls` / number correct,
  from the stored rows by the repo's exact match) lower than both
  comparators on Test-400 BM25. The dollar conversion (Groq
  per-token pricing, verified at manuscript time) is a reporting
  step, not a second bound. H10 is exploratory.
- **Evidence (Test-400, 2026-11-11):** calls per correct answer from
  the stored rows: tuned 9.18, IRCoT v2 5.88, Balanced 20.11.
  The tuned system beats Balanced hugely but loses to IRCoT.
- **Verdict: NOT SUPPORTED on the IRCoT leg.** The claim as written
  needs both comparators; IRCoT's frugality wins the ratio.

### H11 — The tuned system hallucinates less than IRCoT

- **Claim:** the tuned system has a lower wrong-answer rate than
  IRCoT at equal-or-better coverage on Test-400 BM25 — it abstains
  rather than guessing, which is the paper's stated main objective
  (reduce hallucination first, reduced LLM cost second).
  **Criterion:** wrong-answer rate (wrong / answered) lower than
  IRCoT's, with coverage (answered / total) no lower than IRCoT's.
  H11 is exploratory.
- **Evidence (Test-400, 2026-11-11):** wrong-answer rate tuned
  0.4495 (147/327 answered) vs IRCoT 0.4566 (142/311) at better
  coverage (0.818 vs 0.777).
- **Verdict: TIE — not a demonstrated reduction.** The criterion's
  two legs are technically met (lower wrong rate, no-lower coverage)
  but the gap is 0.7pts (~2 questions), inside noise, and the
  criterion carries no significance test — so the paper reports a
  tie, not a win. The hallucination-reduction claim rests on H6
  and the abstention mechanism, not on this comparison.

### Scoreboard

| ID | Verdict | Headline number |
|----|---------|-----------------|
| H1 | SUPPORTED (confirmatory, tuned) | dEM +0.0475, CI excludes 0; McNemar p=0.0094; Holm adj p 0.0188 |
| H2 | NOT SUPPORTED (narrow miss) | Macro-F1 0.6825 < 0.70; contradicted recall 0.75 ≥ 0.70 |
| H3 | SUPPORTED, weaker for TA | AUROC(c0) 0.5915, CI excludes 0.5; below Reference 0.6519 |
| H4 | NOT SUPPORTED (confirmatory) | dEM +0.0150, p=0.4050; cost/correct 9.18 vs 5.25; Holm adj p 0.405 |
| H5 | NOT SUPPORTED (retrieval half) | E5: identical EM, 0 calls saved; override 1/1 retrieved |
| H6 | SUPPORTED, strongly | All gain in hop-0-incomplete subset: ΔEM +0.1146, CI excludes 0 |
| H7 | NOT SUPPORTED | SC = cost win only (p=0.6072); fast path directional (p=0.2100) |
| H8 | NOT SUPPORTED | Tuned EM edge n.s. (p=0.2327) and 2.5x the calls; AR ties IRCoT |
| H9 | NOT TESTED | Phase 3 (2Wiki, then MuSiQue) |
| H10 | NOT SUPPORTED (IRCoT leg) | Calls/correct tuned 9.18 vs IRCoT 5.88 vs Balanced 20.11 |
| H11 | TIE (not a demonstrated reduction) | Wrong rate 0.4495 vs 0.4566 (0.7pts, inside noise); coverage better |

Three supported, six not supported, one tie, one untested. That is
an honest scoreboard for a research system: the core mechanism claim
(H6) and the head-to-head claim (H1, confirmatory) hold, the verifier
(H2), the memory (H5), the adaptivity claim (H4, confirmatory) and
the component claims (H7, H8, H10) do not do what was hoped, and the
hallucination claim (H11) is a tie. The tuning phase bought cost,
not accuracy — and Phase 3 is where the generalization claim gets
tested.

## 2. Where TrueAdaptive is now

**What v1 is.** Built 2026-11-08 on branch `trueadaptive` (off the
merged upstream Phase 5 commit `9564676`), local only, never pushed.
Design: `sequential_consistency()` in `src/epistemic/confidence.py`
(M=1→3, stop on unassailable majority or ΔH < 0.05 after ≥2 samples,
behind `erag.sc_mode`, default `fixed`); self-consistency gated behind
the Fast Path (`erag.gate_sc_behind_fast_path` — when skipped,
c0 = min_eff, recorded as `c0_source: fast_path_min_eff`); direct EIG,
incremental claims, never resample, saturation precheck, thresholds
unchanged (0.8/0.6/0.4), `max_claims: 5`. The closed-book /
entropy-gated retrieval is v2, not v1 — the error analysis says
retrieval is not the bottleneck, so it stays deferred. Frozen config:
`configs/erag_trueadaptive.yaml`. Mocked call counts: fast path 2
calls (was 5 Balanced / 7 Reference), 1-hop 5 calls.

**The Test-400 result (the headline).** BM25, k=3, distractor, N=400,
both systems fresh, frozen configs, all live (0 cache hits).
TrueAdaptive: **EM 0.4750, F1 0.6192, 4.78 calls/Q**, coverage 0.8075,
recall 0.8975, mean wall latency 5.92s. IRCoT: EM 0.4200, F1 0.5674,
2.55 calls/Q. **McNemar paired: b=38, c=16, p=0.0043 (exact 0.0038) —
SIGNIFICANT.** TrueAdaptive also beats Balanced BM25 Test-400 (0.4450
at 8.95 calls) by +3.0 pts EM at −46.6% calls. Fresh IRCoT reproduces
the old 0.4100 baseline (0.4200). Per the agreed rule, MiniLM Test-400
is NOT required — the BM25 result is significant and conclusive — but
the user has not explicitly confirmed this yet. Dev-100 for reference:
TA BM25 EM 0.56 / F1 0.6495 at 4.58 calls; TA MiniLM EM 0.50 / F1
0.6018 at 4.91 calls; Balanced Dev-100 EM 0.5100 at 8.92 calls; IRCoT
Dev-100 EM 0.44 at 2.38 calls.

**What the error analysis said (Test-400, 400 Qs).** Right 190, wrong
133, system-abstained 37, model-said-unknown 40. Reasoning, not
retrieval, is the bottleneck: 107/133 wrong answers had recall==1.0.
Of those 107, 70 had gold in the trace claims (reader/graph
bottleneck) and 37 never extracted gold as a claim (claim-extraction
bottleneck). Hops help net +28 (fixed 42, broke 14; hop-0 draft EM
0.4050 → final 0.4750). The 77 unknowns are two populations: 37
system abstentions (`answer_conf` median 0.214, 17 with correct
drafts — `theta_abs` can touch these) vs 40 reader refusals (draft
literally "unknown", `answer_conf` median 0.875, c0 median 1.000,
only 3/40 had any hop produce a real answer — `theta_abs` cannot
touch these). Call tail: 54 rows ≥7 calls consume 22% of calls at EM
0.333. Fast-path SC gate works (86 skips at 2.00 calls, EM 0.5465).

**Tuning progress (Phase 1, one OpenSpec change per step).**
- **Step 1 — reader grounding — DONE, gate pass, archived.** Conditional
  claim-grounded re-read after the hop loop, behind
  `erag.ground_final_read` (default false). Dev A/B: EM 0.5600 vs
  0.5600 flat, F1 0.6611 vs 0.6495, calls 4.75 vs 4.58; triggered
  16/100, fixed 2, broke 1 (net +1) — a wash on dev; mechanism kept,
  Test-400 confirmation judges it. Confound recorded: cache-key v=2
  meant the tuned run was effectively all-live, and temp-0.0
  nondeterminism flipped 8 untouched rows, so the EM tie carries ~±3
  rows of noise. Lesson: never assume cache replay — verify
  `cache_hits` before believing a paired comparison.
- **Step 2 — claim extraction — DONE, gate 3/4, kept by user decision,
  archived.** Question-grounded claims in the single extraction call
  (zero new LLM calls), each claim with a `"source"` field
  ("draft"/"question"), `max_claims` 5→8. Dev A/B on the step-1 tuned
  system: EM 0.5400 vs 0.5600 (−2 rows, inside ±3-row noise),
  gold-in-claims among full-recall wrong rows 0.524 vs 0.333 baseline,
  answer-bearing question-sourced 6/100 (gate ≤10% PASS). Gate failed
  on EM only; the user chose to proceed. Tuned value: `max_claims: 8`.
- **Step 3 — unknown prompt — DONE, gate FAILED, mechanism DROPPED.**
  Two pre-registered variants (best_guess, cite_first) behind
  `erag.unknown_prompt`: both failed the pre-registered gate on
  unknown reduction (best_guess 6/100 unknowns, needed ≤4; cite_first
  5/100). `unknown_prompt` stays `"base"`. The 40 Test-400
  model-unknown rows remain unrecovered.
- **Step 4 — theta_abs — DONE, theta_abs = 0.50.** The user decided
  the goal is selective answering (reduce hallucination first). The
  pre-registered counterfactual was accepted as the evidence (the live
  runs were ~99% cache replays and were discarded per the tripwire,
  then accepted with a dated amendment — the tripwire premise is false
  for threshold-only steps): t=0.50 → selective EM 0.6456, wrong rate
  0.3544, coverage 0.790, EM 0.5100. Honest finding: the confidence
  signal does not separate right from wrong at the margin (newly
  abstained 6 rows, 3 correct / 3 wrong — a coin flip).
- **Step 5 — hop-2 SC cap — DONE, SUPERSEDED by step 7 (not passed,
  not failed).** The mechanism is `erag.max_hops=1`, config-only. Live
  A/B: EM 0.5100 unchanged, calls/Q 4.49 vs 4.65, hop-2 rows 10→0;
  the gate as written failed on live calls only (replay noise). The
  user chose the learned continuation policy instead of deciding the
  gate; `max_hops` stays 2 as a ceiling; the static cap is NOT adopted.
- **Step 6 — memory effectiveness — measurement built, A/B pending.**
  Component test on the tuned system using the E5 stream instrument
  (Dev-100 cannot test memory — independent questions), gated before
  the Test-400 freeze. The `--position` analyzer section and the
  `mem_store_size`/`mem_texts` row fields are built and verified
  (`e5da900`); the stream A/B (3 arms, fresh namespaces, N=30
  fallback) awaits the step-7 outcome + a Groq key. Memory enters the
  frozen system ONLY if the stream A/B shows an EM gain or a call
  reduction with EM not falling, and the override test passes;
  otherwise memory stays OFF and the paper reports the null. Note:
  the E5 null itself is now known to be cache-confounded (mem arm
  served cache_hits == llm_calls on 30/30 rows) — uninformative, not
  a real null; H5 is revisited with a dated note after step 6.
- **Step 7 — learned continuation policy — Phase A + retrain + B.1
  DONE; live A/B pending.** A logistic regression on hop-0 features
  predicting P(hop-0 draft correct); CONTINUE iff P < τ. The original
  Gate A pass (τ = 0.30, sim EM 0.5000, exactly at the floor) rested
  on a definitionally wrong feature — `draft_unknown` was trained on
  the row draft (final draft), not the hop-0 draft (16/100 rows
  diverge). The user chose the retrain: Gate A re-check PASS with
  margin (τ = 0.05, sim EM 0.5152, F1 0.6238, calls/Q 3.92, coverage
  0.869, OOF AUROC 0.6775; `7872b24`). The τ = 0.30 artifact is
  superseded. B.1 wiring DONE and verified (`a0eb216`): the policy is
  live in `run_erag` behind `erag.continuation_policy`; 12 new mocked
  tests; feature agreement 1e-9 on all 100 dev rows; suite 139 passed.
  C.1 live Dev-100 A/B awaits a Groq key, then Gate B.

**State of the repo.** Branch `trueadaptive`, HEAD `b885297`, local
only, 19 commits ahead of origin, unpushed. Master is 1 commit ahead
of origin (`88f2512`, the `.mailmap` fix) and unpushed. Nothing has ever been pushed to
ManojAdapakala/ERag (fetch-only, push URL `no_push`). No Groq key or
GitHub token is saved anywhere — every future push or live run needs
one supplied transiently. One known pre-existing test failure
(`test_retry_exhaustion_raises_runtime_error` expects "after 4
attempts", code says 6; fails on base too, left untouched).

## 3. Next steps, in order

Phase 2 is complete (verdict INCONCLUSIVE, 2026-11-11). What was
"next" in the old version of this section — steps 6/7, hypothesis
hygiene, the freeze, the Phase 2 runs — is all done.

1. **Phase 2 close-out.** Records (this update, master plan §12,
   changelog §2, assumptions entries), the Adaptive-RAG change
   archived, everything committed on `trueadaptive`, then push to
   origin (needs a fresh GitHub PAT, re-sent by the user). Refresh
   the short-point project report.
2. **Phase 3 — new dataset.** 2WikiMultiHopQA first, then MuSiQue,
   on the FULL official dev sets, BM25 first then MiniLM as the
   second check, frozen tuned system (the Inconclusive rule). New
   hypotheses written BEFORE touching either dataset (H9 already
   written); each dataset judged on its own. No tuning on the new
   test splits; no re-running Phase 2 to chase a Phase 3 number.
3. **Phase 4 — paper.** Per the publication-ready plan: D6 cost
   upgrade (incl. H10), D8 qualitative error taxonomy, regenerated
   tables/figures from the FINAL results, LNCS manuscript with the
   D4 disclosures. H6 leads; H1 confirmatory stands; H2/H4/H5/H7/
   H8/H10 reported honestly; H11 reported as a tie. Venue: target
   February 2027 deadlines (ICAIIT 2027 first).

**Blockers / open decisions (master plan §9; see also
`docs/paper-readiness-plan.md` §4):** fresh GitHub PAT for the push
(transient, on request); FlashRAG + the unsupplied papers (supply or
confirm out of scope); whether a multi-retriever plan version exists
in another file (the user's recollection vs the report's text —
unresolved); the formal paper-goal statement (objective stated:
reduce hallucination first, reduced LLM cost second).

## 4. How the hypotheses change later — and how they don't

**Short answer: the sequence comes first, and the hypotheses do not
get rewritten to fit results.** Finish adaptive → tune it → run it
once on test data → new dataset. The hypotheses change only in the
ways below, and only *before* the run they affect. That is the whole
point of writing them down now.

**Rule 1 — never rewrite a hypothesis after seeing the result it
tests.** That is HARKing (hypothesizing after the results are known):
it turns a failed test into a passing one by moving the goalposts, and
it destroys the confirmatory value of H1/H4. H2 and H5 failed; they
stay failed, and the paper reports them as failed. If a better
hypothesis occurs to anyone *because* of these results, it goes in a
new section as a *post-hoc observation to test later*, not as a
replacement for the tested hypothesis.

**Rule 2 — dated clarifications are allowed, before the affected run,
where a hypothesis is underspecified.** Three are already known and
waiting: the H2 0.70 threshold (proposed, never confirmed — confirm it
or state why 0.70 stands, before the H2 result is judged); the H4 3×
latency bound (unmeetable as stated and contradicted by the report's
own numbers — clarify it, e.g. 3× IRCoT or cost-per-correct-answer,
before the Test-400 ablation); and the H6 comparator (now fixed as
TrueAdaptive vs IRCoT on hop-0 recall). A clarification is dated, has
a reason, and is written in the master plan before the run it affects.
A clarification that changes a threshold *after* the result is known
is not a clarification — it is Rule 1.

**Rule 3 — confirmatory hypotheses get re-run on the new system, not
rewritten.** H1 and H4 were written for E-RAG in general, not for v1
specifically. At Phase 2 they are tested again on the frozen tuned
system, with the same criteria (plus the H4 clarification from Rule
2). Same hypothesis, new system version, fresh test — that is a
legitimate confirmatory re-run. What is not legitimate is re-running
until one version passes and reporting only that one.

**Rule 4 — new phases get new hypotheses, written before touching the
data.** Phase 3 (new dataset) is not a re-test of H1–H6; it is a
generalization test, and it needs its own hypotheses, written before
the first run on that dataset. The natural ones: (a) the tuned system
beats IRCoT on the new dataset (same comparison, new data — a
generalization of H1/H6); (b) the gain again concentrates where the
first retrieval was incomplete (H6, new data); (c) the call budget
holds (≤6 calls/Q on the new dataset). Each gets a criterion and a
pre-registered analysis before any run. If the new dataset uses a
different retriever, that is a *separate* hypothesis about retriever
generalization, not something folded into (a) — see the retriever
question below.

**Rule 5 — the sequence is fixed; the hypotheses follow it, not the
other way round.** Adaptive first (done), tune the architecture on
dev (in progress), one confirmation run on test data (Phase 2), new
dataset last (Phase 3), paper after results (Phase 4). Do not start
Phase 3 to escape a Phase 2 result, and do not add tuning steps after
the freeze to chase a p-value. If Phase 2 is a Loss, the plan already
says what happens: revert to v1 for Phase 3 and report tuning as a
negative result. That is a better paper than a tuned system that only
wins on a test set it was selected on.

**The retriever question for the new dataset.** The user asked
whether Phase 3 uses a different retrieval. The recommendation is:
**same retriever first (BM25), different retriever only as a second
check.** The reason is confound control: if both the dataset and the
retriever change at once, a changed result cannot be attributed to
either. BM25 first isolates the dataset — the only thing that changes
is the data, so a win or loss on the new dataset is a statement about
generalization. Then, if the BM25 result on the new dataset is
inconclusive, run MiniLM as the second check — the same rule used on
HotpotQA — and report both, never pick the better one post-hoc. A
different retriever as the *primary* for Phase 3 would need its own
justification (e.g. the new dataset's corpus makes BM25 a poor fit)
and its own pre-registered hypothesis; it is not the default.

**A note on "actual test data".** The repo's Test-400 is a held-out
slice of HotpotQA *dev* distractor (official HotpotQA test answers
are not public) — manifest: dev N=100, test N=400, all hard, source
`hotpot_dev_distractor_v1.json`. It is the closest thing to actual
test data available for HotpotQA, and it is held out from all tuning,
which is what matters for the Phase 2 verdict. The new dataset in
Phase 3 would use its real test split, which is the true
generalization test.
