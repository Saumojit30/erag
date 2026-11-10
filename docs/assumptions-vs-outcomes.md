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

## Going forward (from 2026-11-10)

- Every experiment from here — step 6, Phase 2, Phase 3, the ablations,
  the cost analysis — gets an entry here the same day it is verified,
  with the assumption as it stood before the run and the actual outcome
  with its file/commit.
- The comparison results themselves continue to be stored as result
  files + analyzer output + §12 log entries; this file is the
  assumption-vs-outcome layer, not a second copy of the numbers.
