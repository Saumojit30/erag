# Assumptions vs Outcomes — ERag experiment record

**Created:** 2026-11-10, on the user's instruction: complete the current
research work as planned, and store (a) the produced results of every
comparison and (b) what was assumed vs what actually happened, per
experiment.

**Purpose:** a single checkable record of predictions against reality.
Every experiment enters here the same day it is verified — the assumption
as it stood *before* the run (with its source), the actual outcome (numbers
+ the stored file or commit that backs them), and the verdict or lesson.
A number appears only if a stored file or a commit backs it (the §12 rule).

**Where comparison results live:** every comparison produces a stored
result file (`results/trueadaptive/*.jsonl`, `results/ircot_test_bm25.jsonl`,
`results/bm25/*.jsonl`, `results/stream_*.jsonl`) plus an analysis in
`scripts/analyze_trueadaptive_test400.py` / `scripts/eval_memory.py`, and
an entry in the master plan §12 log and the retrospective changelog. This
file is the assumption-vs-outcome layer on top of those — it does not
replace them.

**Rules:**

- One entry per experiment or analysis, chronological. In-flight work is
  not entered until verified and committed.
- "Assumed" quotes the pre-run expectation: the hypothesis, the gate, the
  design's prediction, or the plan's statement — with the source named.
  Never rewrite an assumption after seeing the result.
- "Actual" gives the numbers and the file/commit. If the outcome differs
  from the assumption, say so plainly and record what was learned or
  changed — including when the change was a user decision.
- If an assumption cannot be recovered from the record, mark it
  `not recoverable` rather than reconstructing it.

---

## Backfilled entries (2026-11-08 to 2026-11-10, from the verified record)

### 2026-11-08 — TrueAdaptive v1 build: the Dev-100 gate

- **Assumed** (OpenSpec change `erag-trueadaptive`, design): v1 meets
  ≤6 calls/Q and EM ≥0.50 on Dev-100.
- **Actual:** MiniLM EM 0.50, F1 0.6018, 4.91 calls/Q — gate MET, exactly
  at the EM threshold. BM25 EM 0.56, F1 0.6495, 4.58 calls/Q — better
  than MiniLM. Mocked fast path 2 calls (was 5 Balanced / 7 Reference).
  Commits `6c671d0`, `d5c820f`, `738dd1e`, `7d5cba4`, `8a64503`.
- **Lesson:** the gate was met at the floor on MiniLM; BM25 was not the
  planned main retriever and beat it — the retriever choice changed
  because of this result.

### 2026-11-08 — Retriever choice: MiniLM main, BM25 second check

- **Assumed** (original plan + report): MiniLM-L6-v2 + FAISS is the one
  fixed retriever; BM25 appears once in the report as a departure note.
- **Actual:** BM25 Dev-100 EM 0.56 vs MiniLM 0.50 (+6 points, fewer
  calls). The user chose BM25 first for Test-400, MiniLM only if
  required. Results `ef937fc`.
- **Lesson:** the plan's retriever assumption was overturned by a dev
  measurement, before any test run — the right order.

### 2026-11-09 — Test-400 v1 head-to-head: TrueAdaptive vs IRCoT (BM25)

- **Assumed:** TrueAdaptive beats IRCoT on Test-400 (dev suggested it:
  TA 0.56 vs IRCoT 0.44 on Dev-100).
- **Actual:** TA EM 0.4750, F1 0.6192, 4.78 calls/Q vs IRCoT EM 0.4200,
  F1 0.5674, 2.545 calls/Q. McNemar b=38, c=16, p=0.0043 —
  **SIGNIFICANT**. Also beats Balanced BM25 (0.4450 at 8.95 calls) by
  +3.0 points at −46.6% calls. Committed `d69490f`. Both fresh, frozen
  configs, 0 cache hits.
- **Lesson:** the first significant frozen-system E-RAG vs IRCoT Test-400
  result; it resolved audit H3 (the only earlier significance was
  post-hoc re-thresholding, p=0.21–0.29 on frozen systems).

### 2026-11-09 — Step 1: reader grounding

- **Assumed** (change `tune-reader-grounding`): a claim-grounded re-read
  after the hop loop fixes unknown/wrong drafts.
- **Actual:** Dev A/B EM 0.5600 vs 0.5600 flat, F1 0.6611 vs 0.6495,
  calls 4.75 vs 4.58. Re-read triggered 16/100, fixed 2, broke 1
  (net +1) — a wash on dev. GATE PASS, mechanism kept; Test-400
  confirmation judges it. Confound: cache-key v=2 made the tuned run
  effectively all-live; temp-0.0 nondeterminism flipped 8 untouched
  rows (±3-row noise). Committed `9d1d108`, archived.
- **Lesson:** a mechanism can be kept on a wash when the gate passes and
  the test is the judge — but the dev number alone proves nothing.

### 2026-11-09 — Step 2: claim extraction

- **Assumed:** question-grounded claims raise gold-in-claims among
  full-recall wrong rows (baseline 0.333) while EM holds (gate: EM ≥
  baseline −0.01, answer-bearing question-sourced ≤10%).
- **Actual:** gold-in-claims 0.524 (11/21) — PASS; answer-bearing
  question-sourced 6/100 — PASS; EM 0.5400 vs 0.5600 (−2 rows, inside
  ±3-row noise) — gate 3/4, FAILS on EM only. The user chose to proceed
  and keep the mechanism. Tuned value: `max_claims: 8`.
- **Lesson:** a gate can fail on one measure inside the noise band and
  still be kept — but only by an explicit user decision, recorded as
  such, not by re-reading the gate.

### 2026-11-09 — Step 3: unknown prompt

- **Assumed:** a best-guess or cite-first prompt cuts model-unknowns to
  ≤4/100 while recovering some of them.
- **Actual:** best_guess unknowns 6/100 (recovered 2/7, EM 0.50); cite_first
  unknowns 5/100 (recovered 3/7, EM 0.6667). Both 3/4 on the gate — both
  FAILED the unknown-reduction measure. Mechanism DROPPED per the
  pre-registered rule; `unknown_prompt` stays `"base"`. Commits `c0b5e67`,
  `afc10f1`.
- **Lesson:** the gate worked as designed — a failed mechanism was
  dropped, not kept on the strength of its EM upticks (inside noise).

### 2026-11-09 — Step 4: theta_abs (selective answering)

- **Assumed:** raising theta_abs 0.40 → 0.50 improves selective EM and
  cuts the wrong-answer rate (the paper's hallucination objective).
- **Actual:** selective EM 0.6353 → 0.6456 (+1.03), wrong rate 0.3647 →
  0.3544 — but EM 0.54 → 0.51 (−3.0 pts) and coverage 0.85 → 0.79.
  The confidence signal does NOT separate right from wrong at the
  margin: the 6 newly abstained rows were 3 correct / 3 wrong — a coin
  flip. The live A/Bs were ~99% cache replays and were discarded per
  the tripwire; the user chose to accept the pre-registered
  counterfactual as the evidence. theta_abs = 0.50. Commits `4701ac3`,
  `78df3cd`.
- **Lesson:** a +1-point selective-EM gain bought with −3 EM points and
  −6 coverage points is a trade, not a win — recorded as such.

### 2026-11-09 — Step 5: hop-2 SC cap

- **Assumed:** capping max_hops at 1 saves ~0.15 calls/Q at ~equal EM.
- **Actual:** calls/Q 4.65 → 4.49 (−0.16, as expected), EM 0.5100
  unchanged, hop-2 rows 10→0. Gate as written FAILED on live calls only
  (0.06 vs 0.04 — replay noise, not a real effect). The user did not
  pick either gate-reading option; they chose the learned policy
  instead. Step 5 closed SUPERSEDED, gate not re-judged; max_hops
  stays 2. Commit `7a3598c`, archived.
- **Lesson:** a gate can fail on a measure that does not discriminate
  (live calls in a 99%-replay run) — and the right response can be to
  supersede the step rather than re-judge the gate.

### 2026-11-09 — Step 6: memory effectiveness (E5, the old test)

- **Assumed** (report H5): memory reduces retrieval calls without
  lowering accuracy.
- **Actual:** stream_mem vs stream_nomem identical — EM 0.4000, F1
  0.4828, 14.30 calls/Q both. The mem arm served cache_hits ==
  llm_calls on 30/30 rows (shared default namespace) — the "null" is a
  null of a cache replay, i.e. uninformative, not a real null. The
  override mechanism itself is NOT confounded (local-NLI mem_events;
  1/1 retrieved planted belief overridden). Re-test (step 6) pending.
- **Lesson:** the sharpest finding of the project so far — a null result
  produced by a broken test, not by the mechanism. H5 to be revisited
  with a dated note after step 6, not rewritten.

### 2026-11-09 — Step 6: stream extension 30 → 60 questions

- **Assumed** (change `tune-memory-effectiveness`): the raw HotpotQA dev
  file is fetchable from the CMU mirror, so the stream extends to 60.
- **Actual:** the fetch failed three times (both mirror variants return
  curl (52) Empty reply); `data/raw/` does not exist on this VM. The
  pre-registered fallback stands: run N=30 as-is, fire-rate floor ≥5/30.
  No Parquet reconstruction attempted, no questions invented.
- **Lesson:** an external dependency (a dataset mirror) failed; the
  fallback written into the design before the failure is what saved the
  step from stalling.

### 2026-11-09 — Step 7 Phase A: learned continuation policy (offline)

- **Assumed:** a logistic regression on hop-0 features beats the static
  baseline in cross-validated simulation (EM ≥ 0.5000, calls/Q < 4.65).
- **Actual (original):** LR τ=0.30, simulated EM 0.5000, calls/Q 3.98 —
  Gate A PASS, exactly at the floor (47/94; one fewer correct row
  fails it). F1 and coverage dipped below baseline; the saving was
  bought by stopping on wrong drafts.
- **Actual (after the blocker):** `draft_unknown` was trained on the row
  draft — the FINAL draft, which does not exist at the hop-0 decision
  point. The definitions diverge on 16/100 rows. The user chose the
  retrain. Re-trained (hop-0 definition): LR τ=0.05, simulated EM
  0.5152, F1 0.6238, calls/Q 3.92, coverage 0.869 — Gate A re-check
  PASS with margin. Commit `7872b24`.
- **Lesson:** the original pass rested on a definitionally wrong feature
  and was superseded rather than defended. The retrain is a methods
  disclosure for the paper, not a footnote.

### 2026-11-09 — Step 7 Gate B: live Dev-100 A/B of the wired policy

- **Assumed** (pre-registered Gate B): live EM ≥ 0.5000, live calls/Q <
  4.65, live numbers within ±0.02 EM / ±0.2 calls/Q of the simulation.
- **Actual:** live EM 0.5000 (exactly at the floor), calls/Q 4.07,
  dEM −0.0152, dCalls/Q +0.15 — **Gate B PASS**. STOP 81 (EM 0.5679) /
  CONTINUE 19 (EM 0.2105). Live EM is 1 row below baseline (0.5100).
  Commit `4c9576f`. Analyzer bug found during C.1 (§15 compared
  `policy_decision` against uppercase; the runner writes lowercase) —
  fixed the same day; full suite 140 passed.
- **Lesson:** a pass exactly at the floor is a pass, but it must be
  reported as one — Test-400 is the real judge.

### 2026-11-09 — H1–H6 assessment

- **H1 assumed:** E-RAG beats Standard RAG. **Actual:** SUPPORTED
  interim — ΔEM +0.0725, 95% CI [0.0350, 0.1125], McNemar p=0.00034
  (v1 TA vs Standard-BM25, Test-400). Confirmatory re-run on the tuned
  system owed at Phase 2.
- **H2 assumed:** NLI verifier macro-F1 AND contradicted recall ≥0.70.
  **Actual:** macro-F1 0.6825 (missed), contradicted recall 0.75
  (passed) — NOT SUPPORTED, narrow miss at N=60. Main weakness:
  supported recall 0.60 (verifier too conservative on multi-hop claims).
- **H3 assumed:** higher self-consistency goes with correct answers
  (AUROC CI excludes 0.5). **Actual:** TA AUROC(c0) 0.5915, CI
  [0.5421, 0.6391] — SUPPORTED but weaker than Reference (0.6519):
  sequential SC + Fast-Path gating coarsen the signal.
- **H4 assumed:** adaptive beats no-adaptive on F1 at latency ≤3×
  Standard. **Actual:** dev interim ΔF1 +0.0304, CI includes 0 —
  inconclusive; the 3× latency bound as written is unmeetable by any
  multi-call system and cache-confounded — needs a dated clarification
  before Phase 2. Test-400 ablation not yet run.
- **H5 assumed:** memory cuts retrievals with ΔEM ≥ −0.02. **Actual:**
  NOT SUPPORTED on a cache-confounded test (see the step-6 E5 entry) —
  to be revisited after step 6 with a dated note.
- **H6 assumed:** gains concentrate where initial retrieval missed a
  paragraph. **Actual:** SUPPORTED strongly — all of TA's gain over
  IRCoT is in the hop-0-incomplete subset (n=192, ΔEM +0.1146, CI
  [0.0521, 0.1823], p=0.00094); zero gain where retrieval was complete
  (n=208, ΔEM 0.0000). This corrects the author's earlier "leans
  against" reading, which wrongly used final recall.

### 2026-11-08/09 — Audit claims vs reality

- **Assumed (Phase 5 report):** "45.4% LLM call reduction."
  **Actual:** Reference→Balanced is −39.8% calls. The figure was wrong.
- **Assumed (supplied template §3):** a repair sequence (Batch 2A,
  provenance safeguards, conflict-policy characterisation, contradiction
  veto) exists in this repo. **Actual:** the cited commits are bad
  objects, the tag does not exist, the test files and `src/provenance.py`
  are missing, the veto identifiers never existed. The template's
  sequence does not exist here; the actual repair sequence is the audit
  remediation, recorded instead.
- **Assumed (report):** a multi-retriever plan version exists in the
  report file. **Actual:** all three plan versions fix ONE retriever
  (MiniLM-L6-v2 + FAISS top-3); BM25 appears once as a departure note.
  The user's recollection is not supported by the file's text —
  unresolved: a different file, or a memory of the Phase 5 work.

### 2026-11-09 — Venue: GreenAI-2027

- **Assumed:** the Springer conference at Sri Sri University, Cuttack
  (likely GreenAI-2027, Jan 29–30 2027) has an open deadline.
- **Actual:** GreenAI-2027's full-paper deadline was 15 Oct 2026 —
  already passed when checked. The user has not confirmed GreenAI-2027
  is the one; HITA 2027 is the other SSU possibility (submissions open
  soon, venue TBD). Venue selection deferred to after Phase 2.
- **Lesson:** a venue assumption must be checked against the live CFP,
  not against the conference's existence.

### 2026-11-09 — "Repo is clean" (step-7 close-out)

- **Assumed (assistant's message to the user):** nothing uncommitted
  except the cache files.
- **Actual:** 8 unstaged deletions (the `openspec archive` moves for
  steps 5 and 7) plus step 5's archived copies never added. A background
  check caught it; the user approved the cleanup; committed `201c05f`
  (validate 9 passed, 0 failed; status then showed only the known cache
  files and untracked draft/side docs).
- **Lesson:** a cleanliness claim must come from `git status`, not from
  memory of what was committed — and a correction, once found, is
  reported plainly rather than left standing.

---

### 2026-11-10 — Step 6 live A/B: memory effectiveness on the tuned system

- **Assumed (pre-registered gate, design.md D.1):** the tuned system on
  the entity-sharing stream would fire memory on ≥5/30 questions (the
  N=30 fallback floor), and the mem arm would show an EM gain or a
  call reduction with EM not falling, with the override test passing.
  The E5 test had fired 2/30 on the Reference system, so ≥5/30 on the
  tuned system was the working expectation.
- **Actual:** mem fired on **1/30** — verdict "instrument too weak"
  (gate criterion 1 fails). nomem EM 0.6000 / 4.73 calls/Q; mem EM
  0.6667 / 4.60 calls/Q; planted EM 0.6333 / 4.67 calls/Q (all N=30
  deduped, 0 failed, all-live: cache_hits/Q 0.07/0.00/0.00). The
  ΔEM +0.0667 / Δcalls −0.13 would have passed criterion 2 but is
  unattributable — the single fired row changed nothing. Override
  1/1 retrieved (Becker purged); the checker's 2 false-claim flags
  are substring false positives (verified by inspecting both rows).
  Memory stays OFF; H5 stays NOT SUPPORTED with a dated note.
  Files: `results/trueadaptive/stream_tuned_{nomem,mem,planted}_v1.jsonl`.
- **Lesson:** the tuned system answers most stream questions at hop 0,
  so little gets written to memory and less gets read — the stream
  instrument is weaker for the tuned system than it was for the
  Reference system. A stronger instrument would need later questions
  that depend on earlier answers; the gate forbids a re-run to chase a
  better number. Also: a doubled `--set` silently runs the wrong split
  (see the step-6 §12 entry) — check the progress bar before walking
  away.

---

### 2026-11-10 — Adaptive-RAG Gate AR-1 + D.1 sanity run

- **Assumed (pre-registered, design.md):** a DistilBERT router trained
  on 1,100 outcome-labelled questions would beat the 0.50
  majority-class rate on held-out data and produce a non-degenerate
  Dev-100 route distribution (no single route > 90%); the live D.1
  run would reproduce the offline distribution.
- **Actual:** held-out accuracy 0.9318 vs 0.50 (per-class A 0.0 / B
  0.9623 / C 0.9364); Dev-100 routes A0/B45/C55 offline AND live
  (exact match). D.1: EM 0.5000, F1 0.6018, 1.78 calls/Q, 0 failed,
  all-live. Sanity PASSES. Two caveats recorded for the paper: the
  router never predicts route A (only 19 A examples in training), and
  the 268MB weights are gitignored, so a fresh clone must re-run
  training.
- **Lesson:** outcome-based labelling makes route B's dev EM look good
  by construction (B routes are questions Standard already got
  right) — D.1 numbers are a wiring check, not a verdict; H8 is
  judged on Test-400 only.

- **Phase 2 verdict (2026-11-11, pre-registered): INCONCLUSIVE.**
  Assumed: the tuned system would beat fresh IRCoT on Test-400 BM25
  EM with p<0.05 (Win), or at least clearly. Actual: tuned EM 0.4500
  vs IRCoT v2 0.4225, dEM +0.0275, p=0.1608 — the gain is real in
  direction and inside noise. Tuning cut calls vs v1 (4.13 vs 4.78)
  but did not improve accuracy (0.4500 vs 0.4750, p=0.2678). Per the
  decision table: "no significant gain", Phase 3 proceeds with the
  tuned system, no further tuning.
- **H4 (2026-11-11):** assumed adaptivity would beat the no-adaptive
  ablation on F1 at acceptable cost. Actual: dEM +0.0150, p=0.4050;
  dF1 CI includes 0; cost/correct 9.18 vs 5.25 (nearly double) —
  NOT SUPPORTED on both legs. Holm: H1 adjusted p 0.0188
  (SUPPORTED), H4 adjusted p 0.405.
- **D2 ablations (2026-11-11):** assumed each adaptive component
  carries part of the gain. Actual: sequential SC is a cost win only
  (4.13 vs 6.00 calls/Q at the same accuracy, p=0.6072); the fast
  path is directional only (+1.75pts, p=0.2100, same cost). H7 NOT
  SUPPORTED. Post-hoc observation (not a verdict): eager SC
  (FP-control) is +1.75pts over the tuned system at +0.70 calls/Q,
  p=0.2810 — the deferred-SC gate may cost a little accuracy, but
  the data cannot say so.
- **MiniLM second check (2026-11-11):** assumed the BM25 verdict
  would stand with MiniLM as a check. Actual: tuned 0.4450 vs IRCoT
  0.4250, dEM +0.0200, p=0.2559 — same direction as BM25, also
  inconclusive. BM25 verdict stands; both reported.
- **E.1 / H8 (2026-11-11):** assumed the tuned system beats
  Adaptive-RAG on EM at equal-or-fewer calls/Q. Actual: EM edge
  +0.0225, p=0.2327 (not significant) AND tuned uses 2.5× the calls
  (4.13 vs 1.68) — NOT SUPPORTED. Adaptive-RAG ties IRCoT
  (0.4275 vs 0.4225, p=0.8238) at fewer calls. Route B is the weak
  route (n=210, EM 0.3714 at 1.00 call/Q) vs route C (n=190,
  EM 0.4895 at 2.44) — the up-front router sends most questions to
  the single-step path, which is the weaker one.
- **Recovery (2026-11-11):** assumed the rest-chain would run ~2h.
  Actual: repeated VM restarts + slow Groq (~10s/it vs ~2s/it)
  stretched it to ~7h wall with two relaunches; HF_HUB_OFFLINE=1 +
  skip-if-complete worked (FP-control + FP-off finished, MINILM-TUNED
  resumed at 202/400 after a restart at 201/400). No rows lost.

- **Phase 2.5 decision + diagnosis (2026-11-11):** user challenged the
  plan — if nothing is improving, why run the same system on a new
  dataset? Assumed (pre-registration): the improvement targets are
  (1) contested-claim selection at the final read, (2) extraction
  recall, (3) eager SC. Diagnosis from stored Test-400 rows only
  (`scripts/diagnose_phase25.py`, `docs/phase25-improvement-diagnosis.md`):
  53 gold-in-claims wrong rows, 34/53 with the final answer inside a
  WRONG supported claim, re-read never triggered on 41/53; 33
  never-claimed rows with hop-0 recall 1.0 on 27/33; FP-control 19 gains
  / 12 losses, net +7, both directions churning the answer/abstain
  boundary. H12/H13/H14 pre-registered before any new run; theta_abs
  explicitly NOT a lever (would raise the wrong-answer rate, against
  the paper's first objective). No live runs yet in this phase.

- **H12 A/B (2026-11-11):** assumed the contested trigger (T2) would
  raise Dev-100 EM ≥ +0.02 at ≤ +0.5 calls/Q with fixes > breaks on
  triggered rows. Actual: baseline EM 0.5200 / F1 0.6430 at 3.99 calls/Q
  vs contested EM 0.5500 / F1 0.6397 at 4.38 calls/Q — dEM +0.0300, 95%
  CI [−0.02, +0.08], McNemar b=5, c=2, p=0.4531 (not significant on
  N=100, expected — gate is a smoke test); dF1 −0.0033 (flat-to-down);
  +0.39 calls/Q (inside budget). Trigger fired 25/100; fixed 3, broke 1,
  net +2 on triggered rows; untriggered rows +1 (temp-0.0 noise — the
  +3 total includes ~1 noise row). One triggered row flipped to
  abstained/unknown in the contested arm. Cache_hits/Q 0.00 both arms
  (all live, fresh namespaces). **Gate PASSES on all three legs; H12
  enters the improved system.** Baseline is 2 rows above the step-7
  Gate B file (0.5200 vs 0.5000) — noise/drift, controlled by the paired
  fresh baseline. Files:
  `results/trueadaptive/erag_p25_h12_{base,contested}_dev.jsonl`;
  implementation commit b1c30e4; chain log `~/workspace/phase25_h12.log`.

---

### 2026-11-11 — Phase 2.5 H13: second extraction pass over the hop-0 pool (Dev-100 BM25 A/B)

**Assumed (pre-registered, before the run):** an unconditional second
extraction pass at hop 0 raises the gold-in-claims rate among
full-recall wrong rows vs the fresh paired baseline (0.619 on the
fresh H12 baseline file — dated clarification, not the stale step-2-era
0.333), EM does not fall, calls/Q rise ≤ +1.0. The pass fires on every
row (+1 call/Q max by construction); median `second_pass_added` > 0
required, else the mechanism is dropped per the proposal's threat note.
Diagnosis behind it: 33 Test-400 never-claimed rows, hop-0 recall 1.0
on 27/33 — evidence retrieved, never extracted; max_claims=8 binds on
only 2/33, parsing never fails, so the extractor skips the gold
sentence (coverage failure, not capacity).

**Actual (verified 2026-11-11, `scripts/phase25_h13_verdict.py`,
independently re-checked):** baseline (tuned + contested) EM 0.5400 /
F1 0.6400 at 4.35 calls/Q vs second-pass EM 0.5600 / F1 0.6656 at
5.95 calls/Q — dEM +0.0200, 95% CI [−0.03, +0.08], McNemar b=3, c=5,
p=0.7266; dF1 +0.0256; dcalls +1.60, 95% CI [+1.33, +1.88]. **Rate
FELL: 0.625 (10/16) → 0.533 (8/15)** — same counts under the repo
`normalize_answer`, so not a normalizer artifact. **Gate FAILS:**
rate did not rise AND calls blew the +1.0 guardrail (whole CI above
1.0). The pass fires heavily (median added 4.0, mean 3.88, only 10/100
added 0) but adds the wrong claims — it does not surface the gold
sentence. Surprise in the other direction: 4 of the 5 gained rows were
base-'unknown' → answered correctly, so the pass un-blocks reader
refusals more than it fixes claim selection; but it also flipped 3
correct rows to 'unknown', net +2 EM is churn inside noise.
Cache_hits/Q 0.00 both arms. **H13 NOT SUPPORTED; mechanism DROPPED,
stays OFF; improved system remains tuned + contested (H12 only).**
Files: `results/trueadaptive/erag_p25_h13_{base,second}_dev.jsonl`;
implementation commit 8f215e0; chain log `~/workspace/phase25_h13.log`.
---

### 2026-11-11 — Phase 2.5 H14: eager SC dev replication (Dev-100 BM25 A/B)

**Assumed (pre-registered 2026-11-11, before any new run):** making SC
eager (`gate_sc_behind_fast_path=false`) reproduces the FP-control
direction on Dev-100 BM25 — EM gain vs the tuned baseline at ≤ +1.0
calls/Q. Dev is a replication check, not a fresh discovery: the
direction was seen on Test-400 first (FP-control 0.4675 vs tuned
0.4500, 19 gains / 12 losses, p=0.28), so the Test-400 number cannot
be re-judged; if dev replicates, the mechanism enters the improved
system, judged fresh as a whole on its one Test-400 confirmation.

**Actual (verified 2026-11-11, `scripts/phase25_h14_verdict.py`):**
baseline (tuned + contested) EM 0.5300 / F1 0.6488 at 4.30 calls/Q vs
eager EM 0.5400 / F1 0.6380 at 5.11 calls/Q — dEM +0.0100, 95% CI
[−0.03, +0.05], McNemar b=2, c=3, p=1.0; dF1 −0.0108; dcalls +0.81,
95% CI [+0.55, +1.08]. **Gate PASSES** on its pre-registered terms
(dEM > 0 and dcalls ≤ +1.0 on the point estimate). Caveat: the cost
CI straddles the +1.0 guardrail (upper 1.08), so +0.81 is not a
tightly-bounded cost win. The dev replication is smaller than the
Test-400 direction (+0.0100 vs +0.0175) and likewise inside noise —
consistent with the circularity note. Cache_hits/Q 0.00 both arms.
**H14 GATE PASS (dev smoke test); eager SC enters the improved
system. Phase 2.5 closes: improved = tuned + contested (H12) +
eager SC (H14); second extraction stays OFF (H13).** Files:
`results/trueadaptive/erag_p25_h14_{base,eager}_dev.jsonl`;
implementation none (config-only); chain log `~/workspace/phase25_h14.log`.

---

## Going forward (from 2026-11-10)

- Every experiment from here — step 6, Phase 2, Phase 3, the ablations,
  the cost analysis — gets an entry here the same day it is verified,
  with the assumption as it stood before the run and the actual outcome
  with its file/commit.
- The comparison results themselves continue to be stored as result
  files + analyzer output + §12 log entries; this file is the
  assumption-vs-outcome layer, not a second copy of the numbers.
