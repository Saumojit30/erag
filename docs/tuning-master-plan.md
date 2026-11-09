# ERag Adaptive — Master Plan

**Scope:** the research track only — make TrueAdaptive ERag measurably better than
IRCoT, prove it once on Test-400, then generalize to a new dataset, then write
the paper. The production RAG track (customers, FastAPI, deployment) is a
separate plan (`~/workspace/goals/erag-adaptive-rag-project/files/production-rag-plan.md`)
and is not in this document. DevDoc is a separate project and is not in this
document.

**Status:** 2026-11-09. Steps 1–2 of tuning are built and gated (step 2 kept
by user decision after a 3/4 gate pass; EM 0.54 vs 0.56 inside noise).
Step 3 is DONE 2026-11-09 — both variants failed the unknown-reduction
gate (best_guess 6/100, cite_first 5/100 vs ≤4 required), mechanism
dropped per the pre-registered rule, `unknown_prompt` stays `"base"`.
Steps 4–5 are planned here and not started. Step 6 (memory
effectiveness) was added 2026-11-09 after the user pointed out
the plan omitted it. Test-400, new dataset, and paper are planned here and not
started. This plan is the document OpenSpec changes
are built against: every tuning step gets its own OpenSpec change (proposal,
design, tasks, spec) before any code, and every change must trace back to a
section of this plan.

**How to read it:** §1 is the rules — they override everything below if there
is a conflict. §2 is where we are. §3–§6 are the four phases in order. §7 is
the building discipline (OpenSpec). §8 is how anything gets measured. §9 lists
the decisions still open and what decides them. §10 is the risk and findings
log. The appendix holds the frozen baseline numbers everything is compared
against.

---

## 1. Governing principles

1. **Adaptive first, then architecture, then test, then new data, then paper.**
   The order is fixed: (a) adaptive ERag, (b) finetune the ERag *architecture*
   (never the LLM), (c) one Test-400 comparison vs IRCoT, (d) new dataset,
   (e) paper. No phase starts before the previous one is gated, except that
   the paper's *methods* notes may be drafted from the OpenSpec changes as
   they land.
2. **Tune on dev, judge on test, never select on test.** Dev-100 is for
   tuning and for smoke-testing a change. Test-400 is the judge and is run
   once per frozen system. No threshold, prompt, or mechanism is ever chosen
   because it looked good on test. No re-running test to chase significance.
3. **One retriever, one comparison.** The head-to-head is ERag-adaptive vs
   IRCoT only, on one fixed retriever (BM25 first; MiniLM only if the BM25
   result is inconclusive — §4.3). If both retrievers ever run, both get
   reported; the better one is never picked post-hoc.
4. **No BGE right now. No LLM fine-tuning. No manuscript until there are
   results.** These are user decisions, not open questions.
5. **Every tuning step gets an OpenSpec change before code** ("for each step
   use openspec along the way", user 2026-11-09). No code change lands without
   a validated change proposal the user has seen.
6. **Show the work.** Every claim carries its receipt: commit hash, test
   count, recomputed number, or file path. A number without a source is a
   rumour. Irreversible steps (merges, force-pushes, history rewrites) are
   explained before they happen, never after.
7. **Push policy.** Only push target is `Saumojit30/erag` (origin).
   `ManojAdapakala/ERag` (upstream) is fetch-only, push URL `no_push`. Nothing
   from branch `trueadaptive` has ever been pushed; pushing is a user
   decision each time. Groq keys and GitHub tokens are used transiently only
   (env var), never saved in files, memory, or git config.

---

## 2. Where we are (2026-11-09)

### 2.1 What exists

- **TrueAdaptive v1** — built on branch `trueadaptive` (off merged `9564676`),
  local only. Sequential self-consistency (M=1→3, ΔH<0.05), SC gated behind
  the Fast Path, direct EIG, incremental claims, never resample, thresholds
  unchanged (0.8/0.6/0.4), `max_claims: 5`. Frozen config
  `configs/erag_trueadaptive.yaml`. Closed-book/entropy-gated retrieval is v2,
  not v1.
- **Audit remediation, all phases done** (branch `trueadaptive`, HEAD was
  `9408542` before tuning): cache-write guard + purge of 55 empty rows,
  row-level provenance, Phase 5 report corrections, manifest SHAs,
  verification script `scripts/verify_results.py` (10 checks, all passing).
- **Test-400 BM25 head-to-head, completed 2026-11-09** (commit `d69490f`):
  TrueAdaptive v1 **EM 0.4750, F1 0.6192, 4.78 calls/Q** vs fresh IRCoT
  **EM 0.4200, F1 0.5674, 2.55 calls/Q**. McNemar paired b=38, c=16,
  **p=0.0043 (exact 0.0038) — significant**, the first significant
  frozen-system E-RAG vs IRCoT Test-400 result. TrueAdaptive also beats
  Balanced BM25 Test-400 (0.4450 at 8.95 calls) by +3.0 pts at −46.6% calls.
- **Error analysis, done 2026-11-09** (commit `ed154d7`):
  `scripts/analyze_trueadaptive_test400.py` +
  `docs/trueadaptive-test400-error-analysis.md`. Error budget (400 Qs):
  right 190, wrong 133, system-abstained 37, model-said-unknown 40.
  Reasoning, not retrieval, is the bottleneck: 107/133 wrong had recall 1.0;
  of those, 70 had gold in trace claims (reader/graph) and 37 never had gold
  as a claim (claim extraction). Hops help net +28. The 77 unknowns are two
  populations (37 abstentions vs 40 reader refusals) — do not conflate.
  Call tail: 54 rows ≥7 calls consume 22% of calls at EM 0.333.
- **Step 1 (reader grounding) — built, gated, archived.** OpenSpec change `tune-reader-grounding` (commit `c3c97dc`),
  implementation `303efb5`, analysis-script extension `2b1118c`, A/B result
  `9d1d108`. Dev-100 BM25 A/B: EM 0.56 flat, F1 0.661, coverage 0.86,
  4.75 calls/Q; re-read triggered 16/100, fixed 2, broke 1 (net +1).
  Gate PASS (narrowly). See §3.1 for the confound found.
- **Step 2 (claim extraction) — proposed, not built.** OpenSpec change
  `tune-claim-extraction` (commit `0e51368`), validated 4 passed, 0 failed.
  See §3.2.
- **Memory module — implemented, disabled, effectiveness unproven.** The
  Titan-inspired Verified-Belief Episodic Memory (`src/systems/memory.py`:
  surprise-gated writes, NLI verification gating, contradiction override
  deletion, decay 0.98, capacity 200) is wired into `run_erag` and the
  runner but **disabled by default** (`memory.enabled: false`), so every
  result in §2.2 is memory-off. Its validation (Experiment E5,
  `research/openspec_memory.md`) ran once, on the Reference system, 30
  questions in 5 entity-sharing clusters: memory-off EM 0.4000 / F1 0.4828 /
  14.3 calls vs memory-on EM 0.4000 / F1 0.4828 / 14.3 calls — **identical**;
  memory fired on only 2/30 questions. The planted wrong-belief test DID
  work (the false "Wolfgang Becker is a French director" belief was
  overridden/deleted on contradiction), so the deletion mechanism is
  verified but the effectiveness is a null result on N=30. The plan omitted
  this test until 2026-11-09; it is now Phase 1 Step 6 (§3.6).
- **The report exists — hypothesis now stated, not inferred.** The user
  supplied the project report on 2026-11-09
  (`~/workspace/user/files/ERAG_Human_Style_Research_Report_FULL_ONE.pdf`,
  62 pages, dated 4 Nov 2026, @Jit). It contains the three plan versions
  (Appendix A latest consolidated master report, Appendix B revised 15-day
  plan, Appendix C original five-phase plan E1–E14) and the formal
  hypothesis table H1–H6. Primary research question: "Can evidence-aware
  uncertainty estimation and claim-level verification guide adaptive
  retrieval in multi-hop RAG, improving answer reliability at a reasonable
  computational cost?" H1 (E-RAG beats Standard RAG) and H4 (adaptive
  retrieval beats the no-adaptive ablation at acceptable cost, latency ≤3×
  Standard) are the CONFIRMATORY tests (McNemar paired EM, Holm correction
  across the two); every other comparison — **including E-RAG vs IRCoT** —
  is exploratory, reported with intervals only. H2: NLI macro-F1 and
  contradicted-class recall ≥0.70. H3: self-consistency AUROC excludes 0.5.
  H5: memory cuts retrieval with ΔEM ≥ −0.02, descriptive only (N≈30
  stream). H6: gains concentrate where initial retrieval missed a paragraph.
  Verified directly from the extracted text (not just a delegated summary).
  Consequence for this plan: the Phase 2 pre-registered verdict (§4.2)
  tests TA vs IRCoT, which the report labels exploratory; the confirmatory
  H1/H4 analyses are a separate open decision (§9).
- **Retriever correction (verified from the report text).** All three plan
  versions fix ONE retriever — all-MiniLM-L6-v2 + FAISS, top-3 — and insist
  it stay constant ("one model, one retriever and one question set"). BM25
  appears once, as a departure note (dense instead of BM25, the original
  IRCoT's retriever). BGE/E5 appear nowhere. The four-retriever Phase 5 and
  the BM25-first adaptive work are later repo developments, NOT in this
  report — and the user's recollection of a multi-retriever version in this
  file is not supported by the file's text. Unresolved: whether a different
  file/version holds the multi-retriever plan, or the memory is of the Phase
  5 work. Do not assert a multi-retriever plan version exists until the user
  confirms.
- **Report's only measured numbers.** Phase 1 baseline (50 HotpotQA dev,
  MiniLM, gpt-oss-20b): EM 0.54, F1 0.634, recall 0.73, 7/50 unknown.
  Phase 2 regression: EM ~0.56 → ~0.28 when the epistemic layer entered the
  end-to-end pipeline — unresolved in the report, with the 0.54 vs 0.56
  baseline discrepancy flagged in the document itself. The repo's current
  numbers (Reference Test-400 EM 0.4525) show recovery past 0.28, but the
  report contains no record of that resolution. Report's cost expectation:
  worst case ~18 calls/Q for 2-hop E-RAG; TrueAdaptive measured 4.78.
- **H1–H6 assessed 2026-11-09 (commit `3468d08`).** From stored results
  only, script `scripts/analyze_hypotheses_h1_h6.py`, report
  `docs/hypotheses-h1-h6-assessment.md`. Verdicts: H1 SUPPORTED (interim,
  v1: TA vs Standard-BM25 dEM +0.0725 CI [0.0350, 0.1125], McNemar
  p=0.00034; Holm pending H4; confirmatory re-run on the tuned system
  pending); H3 SUPPORTED but weaker for TA (AUROC(c0) 0.5915 vs Reference
  0.6519 — Fast-Path gating + sequential SC coarsen the confidence
  signal); H6 SUPPORTED strongly (all TA gain over IRCoT in the
  hop-0-incomplete subset, dEM +0.1146; zero gain where retrieval was
  complete — corrects the earlier "leans against" reading, which used
  final recall instead of hop-0 recall); H5 NOT SUPPORTED on retrieval
  reduction (E5 identical EM, 0 calls saved; override 1/1 retrieved,
  1/5 planted); H4 NOT TESTED on Test-400 (dev interim inconclusive;
  3× latency bound unmeetable as stated and cache-confounded — needs a
  dated clarification); H2 NOT SUPPORTED, narrow miss (macro-F1 0.6825
  < 0.70, contradicted recall 0.75 ≥ 0.70; supported recall 0.60 is the
  weakness).
- **Status doc 2026-11-09:** `docs/hypotheses-current-status.md` — the six
  hypotheses with evidence and verdicts, where TrueAdaptive is now, the
  ordered next steps, and the rules for how hypotheses may change later
  (dated clarifications before the affected run only; never rewrite after
  seeing a result; new phases get new hypotheses written before touching
  the data). It also records the recommendation for Phase 3: same
  retriever first (BM25), different retriever only as a second check.
- **No manuscript text exists.** The report is a plan + status report with a
  paper blueprint (two working titles, claim-to-evidence map), not a paper
  draft: no abstract/introduction/conclusion text. The Implementation Guide
  PDF (55 pp) is still not in the repo. Team (Appendix C): GITA Autonomous
  College, Soumya Swarup Kar, Saumojit Santra, Temburu Akhil, Adapakala
  Manoj.

### 2.2 Frozen baselines (the numbers everything is compared against)

| System / split | Retriever | EM | F1 | Calls/Q |
|---|---|---|---|---|
| TrueAdaptive v1, Dev-100 | MiniLM | 0.5000 | 0.6018 | 4.91 |
| TrueAdaptive v1, Dev-100 | BM25 | 0.5600 | 0.6495 | 4.58 |
| TrueAdaptive v1 + step 1, Dev-100 | BM25 | 0.5600 | 0.6611 | 4.75 |
| IRCoT, Dev-100 | BM25 | 0.4400 | — | 2.38 |
| Balanced, Dev-100 | BM25 | 0.5100 | — | 8.92 |
| TrueAdaptive v1, Test-400 | BM25 | 0.4750 | 0.6192 | 4.78 |
| IRCoT fresh, Test-400 | BM25 | 0.4200 | 0.5674 | 2.55 |
| Balanced, Test-400 | BM25 | 0.4450 | — | 8.95 |

Full numbers (coverage, recall, selective EM, McNemar) are in the error
analysis report and the appendix. The Test-400 TA file has 401 lines for 400
questions (a resume retried 1 failed question, leaving a stale failed row) —
always dedupe by id keeping the LAST row.

### 2.3 Branch and remote state

- Branch `trueadaptive`: all tuning and remediation work. Never pushed.
- Branch `master`: 1 commit ahead of origin (`88f2512`, the `.mailmap` fix
  for Manoj's authorship). Needs a fresh GitHub token to push.
- `results/cache.sqlite` and `results/nli_memo.pkl` are modified by runs and
  deliberately left uncommitted. `configs/erag_adaptive.yaml` is an old
  untested draft, untracked.

---

## 3. Phase 1 — Architecture tuning (finetune ERag, not an LLM)

### 3.0 How a tuning step works

Every step follows the same lifecycle, no exceptions:

1. **Diagnose from stored data first.** Before any design, the step's error
   bucket is re-measured from the stored Test-400 file (read-only). The
   diagnosis must name the mechanism (not just the symptom) and quantify the
   sub-populations. If the diagnosis cannot name a mechanism, the step does
   not start.
2. **OpenSpec change.** One change per step: `proposal.md` (why, what,
   alternatives, non-goals, impact), `design.md` (mechanisms, deferred
   variants, guardrails), `tasks.md` (checkboxes, gate), `specs/<name>/spec.md`
   (requirements with scenarios). Every proposal carries a **Threats to
   validity** note: what could make the A/B lie (cache staleness, key
   versioning, live-call noise, dev noise). `openspec validate --all` must be
   0 failed before code.
3. **Tests first.** Mocked-LLM tests for the new behaviour (including the
   flag-off case: byte-identical to the previous system) before implementation.
4. **Implementation.** Behind a config flag (default off), so the previous
   system stays runnable and the A/B is a single-flag flip.
5. **Dev-100 BM25 A/B.** The tuned system vs the previous tuned system, same
   fixed retriever, same split. The dev gate is a **smoke test, not a
   verdict** (see §8): it can only say "did not break catastrophically" and
   "calls in budget". It cannot say "this mechanism works" — Dev-100 moves in
   1-pt steps and live-call noise is ~±3 rows. A dev wash is not a failure
   and not a success; it is inconclusive, and the mechanism is judged on
   Test-400 (§4).
6. **Gate + commit.** The step's gate (below, per step) decides whether the
   mechanism stays in. On pass, commit code + tests + dev results. On fail,
   record the result, do not tune thresholds to compensate, and either try
   the recorded variant as its own change or drop the mechanism.
7. **Archive.** `openspec archive <change> -y` (always with `-y`) when the step closes, then start
   the next change. Archiving must not block the next step's proposal.

**Cost budget for the phase:** the tuned system must stay ≤ 6 calls/Q on
Dev-100 (the v1 gate). A step that adds calls must justify them with EM or
coverage; a step that only adds calls with no EM movement is dropped at the
Test-400 verdict, not at the dev gate.

### 3.1 Step 1 — Reader grounding (DONE)

- **Evidence:** 70 Test-400 rows had gold in a trace claim and still got the
  wrong answer; the final reader never saw the graph's verified claims.
  Plus 40 rows where the draft was literally "unknown" while the graph was
  confident.
- **Mechanism:** conditional claim-grounded re-read after the hop loop (draft
  "unknown" OR draft disagrees with the answer claim), grounded on supported
  claims, behind `erag.ground_final_read` (default false).
- **OpenSpec change:** `tune-reader-grounding` (archived 2026-11-09 as
  `2026-11-09-tune-reader-grounding`).
- **Dev A/B result:** EM 0.56 flat, F1 0.661, coverage 0.86, 4.75 calls/Q;
  triggered 16/100, fixed 2, broke 1 (net +1). Gate PASS (narrowly).
- **Confound found (recorded for all later steps):** the A/B was supposed to
  replay v1's cached completions via namespace reuse, but audit M3 cache-key
  versioning (v=2, landed after the v1 dev run) makes old rows unreachable —
  the tuned run was effectively all-live (0.02 cache hits/row), and
  gpt-oss-20b at temp 0.0 flipped 8 untouched rows. The headline EM tie
  carries ~±3 rows of live-call noise; the within-run section-10 estimate
  (fixed 2, broke 1) is the clean measure. **Lesson: never assume cache
  replay — verify `cache_hits` in the output file before believing a paired
  comparison.**
- **Findings carried forward:** the re-read broke one correct answer on
  formatting ("1970s and 1980s" → "1970s–1980s"); one live draft call
  returned an empty string (pre-existing robustness gap, not caused by the
  re-read).

### 3.2 Step 2 — Claim extraction (BUILT, gate passed by user decision 2026-11-09)

- **Evidence:** 37 rows with recall 1.0 where gold was never a claim.
  Diagnosis: all 37 wrong draft (0 unknown); sub-patterns are wrong-answer
  claims asserting the draft, and abbreviated-name claims ("Thon Maker" for
  gold "Thon Marial Maker"); 9 incremental-freeze, 11 at the `max_claims: 5`
  cap, 0 fallbacks. **No trigger separates the 37** (c0 median 1.0 both
  groups; answer claim supported in 18/37).
- **Mechanism:** question-grounded claims in the single extraction call
  (zero new LLM calls), each claim with a `"source"` field, cap 5 → 8 in the
  A/B. The draft-free second pass and the freeze fix are recorded follow-ups,
  not bundled.
- **OpenSpec change:** `tune-claim-extraction` (commit `0e51368`; build
  commits below).
- **Dev gate (smoke test):** EM not below the step-1 tuned dev (0.56);
  gold-in-claims rate among full-recall wrong dev rows improves on the 0.333
  baseline (12/18 never claimed); calls +≤0.5/Q; answer-bearing claim
  question-sourced in ≤10% of rows.
- **Build order:** mocked-LLM tests → prompt + `_parse` change → fast suite
  → Dev-100 BM25 A/B (needs a Groq key transiently) → gate → commit → archive.
- **Result (Dev-100 BM25 A/B, `results/trueadaptive/erag_trueadaptive_bm25_dev_claims.jsonl`,
  N=100, 0 failed):** EM 0.5400 vs step-1 tuned 0.5600 (2 rows lower —
  inside the documented ±3-row live-call noise band); F1 0.6391 vs 0.6611;
  calls 4.65/Q vs 4.75. Mechanism measures: gold-in-claims 0.524 (11/21)
  vs 0.333 baseline; 349/764 claims question-sourced (45.7%); gold-bearing
  claim question-sourced in 48/73 rows; answer-bearing question-sourced
  6/100 (≤10% PASS); re-read triggered 24/100, fixed 3, broke 0. Cache
  note: 2.53 cache_hits/Q (step-1 run 0.02) — namespace reused, only
  extraction calls were live. **Gate: 3/4 pass; EM fails on the point
  estimate only. User decision 2026-11-09: proceed (keep the mechanism),
  Test-400 judges it.** Tuned value recorded: `max_claims: 8` (goes in the
  frozen tuned config at end of Phase 1, not yet a file). Build also found
  and fixed a design error: `"source"` was dropped at the graph boundary
  (`build_graph` never passed it, `Claim` had no field) — threaded through
  with a test (`test_build_graph_preserves_claim_source`); docs amended.

### 3.3 Step 3 — Model-unknown prompt experiment (DONE 2026-11-09 — GATE FAILED, MECHANISM DROPPED)

- **Evidence:** 40 rows end with the draft literally "unknown" while the
  graph is confident (`answer_conf` median 0.875, `c0` median 1.000). Only
  3/40 had any hop produce a real answer; 16/40 had full recall. The reader
  refuses from hop 0 — it is a prompt problem, not a threshold problem
  (`theta_abs` cannot touch these rows). Even 50% recovery is ≈ +5 pts EM,
  but the value is unmeasured until a live run.
- **Mechanism (to be designed in its change):** a prompt experiment on the
  reader — variants of `ANSWER_SYSTEM` / `answer_messages` that change when
  the model says "unknown" (e.g. forcing a best-guess answer with an
  explicit "give your best short answer from the context" instruction, or
  separating "not in context" from "uncertain"). Must be a prompt-only
  change; the abstention rule stays the arbiter of whether an answer is
  withheld. Design must state the variants up front (no fishing through
  variants on dev and picking the best — that is selection on a 100-row set;
  at most 2–3 pre-registered variants, each a separate A/B, each reported).
- **OpenSpec change:** `tune-unknown-prompt` (drafted 2026-11-09, validated
  5 passed 0 failed; proposal first, code second — build starts on user
  approval). Two pre-registered variants (`best_guess`, `cite_first`),
  each its own Dev-100 BM25 A/B, behind `erag.unknown_prompt` (default
  `"base"`). Gate per variant: unknowns fall by ≥3 rows (7 → ≤4);
  recovered-row EM ≥ 0.5; EM not below step-2 tuned dev (0.54); calls
  +≤0.5/Q. Selection between passing variants by pre-registered rule
  (larger unknown reduction; tie → `best_guess`). Key risk recorded:
  recovered guesses will likely be high-confidence, so `theta_abs` will
  not withhold bad ones — the recovered-row accuracy gate is the
  protection.
- **Dev gate (smoke test):** EM not below the step-2 tuned dev; model-unknown
  rows on dev fall; calls +≤0.5/Q. The real measure is Test-400 (§4).
- **Outcome (2026-11-09, Dev-100 BM25 A/B, N=100 each, 0 failed):**
  `best_guess` unknowns 6/100 (falls by 1 — gate needed ≥3), recovered 2/7
  EM 0.50, EM 0.5500, calls 4.76/Q; `cite_first` unknowns 5/100 (falls by
  2), recovered 3/7 EM 0.6667, EM 0.5600, calls 4.48/Q. Both 3/4 on the
  gate — both FAIL on the primary measure (unknown reduction). Per the
  pre-registered rule the mechanism is DROPPED: `erag.unknown_prompt`
  stays `"base"` in the frozen tuned config; no third variant inside this
  change. The EM upticks (+1, +2 rows) sit inside the ±3-row noise band.
  Dev is a weak instrument here (only 7 unknown rows); the 40 Test-400
  model-unknown rows remain unrecovered. Code and tests remain (variants
  available for later work), nothing branches on a non-base variant.

### 3.4 Step 4 — theta_abs (PLANNED, decided by the paper's goal)

- **Evidence:** 37 system abstentions (`answer_conf` median 0.214, 17 with
  correct drafts). Dev sweep (counterfactual on stored rows): t=0.00 → EM
  0.58, t=0.10–0.30 → 0.57, t=0.40 (current) → 0.56 — a +1–2 pt gain inside
  the ±10 pt dev noise bar. Test diagnostic (never select on it): t=0.00 →
  0.5175. Direction agrees, magnitude is uncertain.
- **Mechanism:** change `theta_abs` (currently 0.4) to a dev-selected value.
  This is a one-line config change, but it is the step most at risk of
  overfitting dev — so it is done LAST among the threshold-adjacent steps
  and its value is justified by the paper's goal, not by chasing the dev
  maximum.
- **The decision that must be made first (user decision, §9):** what is the
  paper's goal — selective answering (high precision on answered questions,
  abstain more) or maximum EM (answer everything, abstain less)? A low
  `theta_abs` raises EM and coverage and lowers selective EM; a high one does
  the opposite. The dev sweep cannot make this choice; the goal does.
- **OpenSpec change:** `tune-theta-abs` (to be created when step 3 closes).
- **Dev gate (smoke test):** EM and selective EM move in the direction the
  goal requires; calls unchanged (thresholds cost no calls). If the goal is
  undecided when step 4 starts, the step is skipped and `theta_abs` stays
  0.4 — a missing decision is not a reason to tune blind.

### 3.5 Step 5 — Hop-2 SC cap (PLANNED, cost lever)

- **Evidence:** 54 rows ≥7 calls consume 422 of 1,910 calls (22%) at EM
  0.3333; 20 of them end unknown. Mean calls by hops: 0→3.02, 1→5.52,
  2→7.95. The hop-2 rows are the most expensive and the least accurate.
- **Mechanism (to be designed in its change):** cap the self-consistency
  work on hop 2 (e.g. skip post-hop resampling on hop 2, or cap SC samples
  on hop 2 at 1), so the tail costs less. This is a pure cost lever: expected
  saving ≈ 100 calls/400 questions, measurable precisely from the output
  file. EM effect must be measured, not assumed — if hop-2 SC is load-bearing
  for the few rows it helps, the cap is narrowed, not forced.
- **OpenSpec change:** `tune-hop2-sc-cap` (to be created when step 4 closes).
- **Dev gate (smoke test):** calls/Q falls with EM not below the step-4
  tuned dev by more than 1 pt (a cost step that costs accuracy is a trade,
  not a win, and the trade is decided at the Test-400 verdict, not on dev).

### 3.6 Step 6 — Memory module effectiveness (component test; ADDED 2026-11-09)

This step was missing from the plan until the user pointed it out. It is a
component test, not a tuning step: the memory module is a distinct part of
the architecture with its own hypothesis, and it must be gated **before**
the Test-400 freeze (§4.1), because enabling it would change the frozen
system.

- **The hypothesis (as implemented — see the note below).** E-RAG's overall
  hypothesis is that explicit epistemic state (belief graphs over claims,
  NLI verification, self-consistency confidence, gap-driven adaptive
  retrieval) lets a RAG system answer multi-hop questions more accurately
  with fewer LLM calls than fixed pipelines (Standard, IRCoT). The memory
  module's specific hypothesis (from `research/openspec_memory.md` and
  `research/decisions.md` D-009) is: in sequential question streams where
  later questions reuse facts established in earlier ones, a verified-belief
  episodic memory improves accuracy and reduces retrieval — *without*
  preserving hallucinations, because writes are surprise-gated (only when
  initial confidence was low or a contradiction was resolved, the Titans
  idea of memorizing at test time when surprised), reads are NLI-verified
  against fresh evidence, contradicted beliefs are deleted (override), and
  unused beliefs decay.
- **Prior evidence (E5, the only run).** Stream A/B, Reference system, 30
  questions, 5 entity-sharing clusters: memory-off vs memory-on identical
  (EM 0.4000, F1 0.4828, 14.3 calls/Q); memory fired on 2/30 questions.
  Planted wrong-belief test: the false belief was overridden on contradiction
  (mechanism verified, effectiveness not demonstrated). Files:
  `results/stream_mem.jsonl`, `results/stream_nomem.jsonl`,
  `results/stream_planted.jsonl`; manifests `data/manifests/stream.jsonl`
  (30 Qs), `data/manifests/planted.json`.
- **Why Dev-100 cannot test memory.** Dev questions are independent and
  shuffled; later questions do not reuse earlier questions' facts, so memory
  would almost never fire (`mem_used` ≈ 0) and the A/B would be vacuous.
  The correct instrument is the E5 stream design (entity-sharing clusters),
  not Dev-100.
- **Mechanism (to be designed in its change):** run the *tuned* system
  (TrueAdaptive + all gated tuning steps) on the stream manifest with memory
  off vs on; measure EM, calls/Q, and `mem_used`/`mem_events` per question,
  split by position in cluster (early vs later questions — the benefit, if
  any, concentrates in later questions). Re-run the planted override test on
  the tuned system. If the stream is too small to resolve anything (N=30,
  ~±18 pts), extend the manifest with more entity-sharing clusters *before*
  running (a data-prep change, decided in the step's proposal, not after
  seeing results).
- **OpenSpec change:** `tune-memory-effectiveness` (to be created when step
  5 closes). The change also records whether the memory module stays in the
  paper's claims at all.
- **Gate:** memory goes into the frozen Test-400 system ONLY if the stream
  A/B shows an EM gain or a call reduction with EM not falling, and the
  override test passes on the tuned system. Otherwise memory stays OFF for
  Test-400 and the paper reports it as a null: the override mechanism is
  verified, the effectiveness is not demonstrated on the available stream.
  A null here does not block Phase 2; it scopes the paper's claims.
- **Note on the hypothesis (now verified, not inferred).** The hypothesis
  in §3.6's first bullet is the report's own statement (primary RQ + H1–H6,
  see §2.1), verified from the report's text 2026-11-09. One consequence is
  recorded here rather than silently assumed: per the report, E-RAG vs IRCoT
  is an *exploratory* comparison; the confirmatory tests are H1 (vs Standard
  RAG) and H4 (vs the no-adaptive ablation). The Phase 2 verdict (§4.2) as
  written tests the exploratory comparison — see §9 for the open decision on
  adding the confirmatory H1/H4 analyses. The Implementation Guide PDF is
  still not in the repo; if it is supplied, the hypothesis statement is
  re-checked against it.

### 3.7 What is explicitly NOT in Phase 1

- **Closed-book gate (v2).** Deferred. The error analysis says retrieval is
  not the bottleneck (107/133 wrong had recall 1.0), so skipping retrieval
  cannot fix the rows that matter. Its design is already written in the
  `erag-trueadaptive` change (Mechanism 2, deferred) for the v2 change.
- **Retriever changes.** BM25 stays fixed for tuning. No hybrid retriever,
  no BGE, no E5 in this phase.
- **New dataset, manuscript.** Phases 3 and 4, not here.
- **Threshold fishing.** No sweeping a threshold across dev and picking the
  max. `theta_abs` is the only threshold touched in this phase, and only in
  step 4, by goal (§3.4).

---

## 4. Phase 2 — Test-400 confirmation (the verdict)

This phase is **pre-registered here, before tuning ends**. Nothing in this
section may be changed after any Test-400 result in this phase is seen. If a
change to this section is ever needed, it is made in a dated amendment with a
stated reason, before the run it affects.

### 4.1 What runs

- **Systems:** (a) tuned TrueAdaptive — all gated tuning steps (1–5) plus
  the memory decision from step 6 (§3.6), frozen config; (b) fresh IRCoT —
  same frozen config as the v1 Test-400 run.
- **Setting:** BM25, k=3, distractor, HotpotQA Test-400 (N=400), both systems
  run fresh, all live calls (0 cache hits expected — new prompts and new
  namespaces).
- **Namespaces (fresh, never used before):** tuned `test_tuned_v1_bm25`,
  IRCoT `test_ircot_v2_bm25`. Fresh namespaces are mandatory: reusing a
  namespace would replay old completions under the v=2 key only if the keys
  match, and they do not across changed prompts.
- **Frozen config:** a new frozen config file for the tuned system
  (`configs/erag_trueadaptive_tuned.yaml`, written at the end of Phase 1 from
  the gated flags: `ground_final_read`, `max_claims`, prompt revisions,
  `theta_abs`, hop-2 cap, and the memory on/off decision from step 6).
  IRCoT runs its existing frozen config. No `--set` overrides at run time
  except the retriever, namespace, and run name — the frozen files are the
  record.
- **Run order:** tuned first, then IRCoT, sequential, detached, with
  checkpoint resume (proven twice: the v1 Test-400 run and the step-1 dev
  A/B both survived runtime restarts via the runner's skip-completed-ids
  recovery). Output files are new; the v1 Test-400 files are never
  overwritten.

### 4.2 The verdict (pre-registered)

**Primary endpoint:** exact match (EM), paired McNemar exact two-sided test
on the 400 paired outcomes (tuned vs IRCoT), α = 0.05.

- **Win:** tuned EM > IRCoT EM **and** p < 0.05.
- **Loss:** tuned EM ≤ IRCoT EM, or p ≥ 0.05 with tuned EM ≤ IRCoT EM.
- **Inconclusive:** tuned EM > IRCoT EM but p ≥ 0.05 (right direction, not
  significant).

**Secondary endpoints (reported, not gated):** F1, calls/Q, coverage,
recall, selective EM, cost (Groq tokens × $0.10/$0.20 per 1M), and the same
paired comparison of tuned vs v1 TrueAdaptive (EM 0.4750) and vs Balanced
(0.4450). The error analysis is re-run on the tuned file
(`scripts/analyze_trueadaptive_test400.py`, extended with the step
sections) and the verification script (`scripts/verify_results.py`) must pass
10/10 on the new results.

**Decision table:**

| Outcome | What happens |
|---|---|
| Win | The tuned system is the paper's system. Proceed to Phase 3 (new dataset) with it. Steps that passed their dev gates stay in. |
| Inconclusive | Run MiniLM Test-400 (see §4.3). If MiniLM is also inconclusive, the tuning is reported as "no significant gain on Test-400" and Phase 3 still proceeds — a null result is a result, and the paper reports it honestly. No further tuning to chase significance. |
| Loss | Stop tuning. The tuned system is not the paper's system: revert to v1 (EM 0.4750, significant vs IRCoT) for Phase 3, and report the tuning as a negative result (which steps helped on dev, which did not survive test). No re-tuning to reverse a loss. |

### 4.3 Rules

- One run per system. No re-runs to chase significance, no threshold or
  prompt changes after seeing test.
- **MiniLM rule (already agreed):** MiniLM Test-400 runs only if the BM25
  result is inconclusive (not significant, or the dev advantage does not
  replicate in direction). If both run, both are reported — never pick the
  better one post-hoc.
- Dedupe by id keeping the LAST row (the resume-retried stale row lesson).
- The analysis uses the repo's `exact_match`, never a hand-rolled normalizer.
- Groq key and any tokens are transient only, as always.

### 4.4 Analysis and reporting

- Run `scripts/analyze_trueadaptive_test400.py` on the tuned file (with the
  `--reread` and `--claims` sections) and the fresh IRCoT file; write the
  error analysis for the tuned system the same way as the v1 report.
- Run `scripts/verify_results.py` (10 checks) on the new results; fix or
  record any failure before reporting.
- Commit the results files, the frozen tuned config, and the analysis report
  on `trueadaptive`. The Test-400 numbers go into the appendix baselines.

---

## 5. Phase 3 — New dataset (generalization)

**Goal:** show the tuned system generalizes beyond HotpotQA — or find out
honestly that it does not.

- **Candidates (user has not chosen):** 2WikiMultiHopQA or MuSiQue.
  2WikiMultiHopQA is structurally closest to HotpotQA (multi-hop, distractor
  setting, comparable size) — the safer comparability choice. MuSiQue is
  harder and more compositional (multi-hop with disconnected reasoning) —
  the stronger generalization claim, and the harder test. The choice is the
  user's (§9); the deciding question is what the paper claims: "works on
  multi-hop QA" (2Wiki) vs "works on harder multi-hop QA" (MuSiQue).
- **Work items (each an OpenSpec change when the phase starts):**
  1. Dataset prep: manifests (dev/test splits), overlap check against
     HotpotQA test (zero overlap required — the audit's dataset check is the
     template), distractor corpus construction, baseline reproduction.
  2. Frozen baselines on the new dataset: Standard, IRCoT, and tuned
     TrueAdaptive, same retriever discipline (BM25 first).
  3. Head-to-head: tuned vs IRCoT on the new test split, same pre-registered
     verdict shape as §4.2 (McNemar, α=0.05), with the dataset named up
     front.
  4. Error analysis on the new dataset, same script pattern.
- **What does not happen:** no tuning on the new dataset's test split; any
  tuning uses its dev split only, and only if the HotpotQA-tuned system
  underperforms there for a diagnosed, mechanistic reason (a new OpenSpec
  change, not a quiet tweak).
- **Out of scope for this phase:** a third dataset. Two datasets are enough
  for the paper's claim.

---

## 6. Phase 4 — Paper / manuscript

Only after Phase 2 (and Phase 3, if it runs). No manuscript exists today and
none is started in this plan.

- **Related-work positioning (from the supplied papers, verified 2026-11-09
  against the papers' text).** Five papers supplied
  (`~/workspace/user/files/`); FlashRAG and others NOT supplied — the
  related-work section cannot be closed until they arrive or the user
  confirms them out of scope (§9).
  - **IRCoT (Trivedi et al., ACL 2023):** structural template and baseline.
    ERag's hop loop *is* an interleaved retrieve–reason loop; ERag replaces
    free-text CoT with a belief graph over NLI-verified claims, and the fixed
    step cap with confidence/gap/EIG-driven stopping plus abstention.
  - **Adaptive-RAG (Jeong et al., NAACL 2024):** the thesis (allocate effort
    per question) is ERag's core principle; the mechanism is NOT implemented
    (no trained complexity classifier, no up-front routing — decisions are
    made during reasoning from epistemic state). Warning that transfers:
    adaptivity lives or dies by signal quality (Adaptive-RAG's oracle
    classifier would jump HotpotQA F1 53.82 → 64.00).
  - **CRAG (Yan et al., arXiv:2401.15884):** verification-gating is central
    to ERag, but CRAG's corrective loop is NOT implemented — no discard of
    bad retrieval, no web fallback, no strip refinement; ERag verifies claims
    but never corrects retrieval, only retrieves more. No Ambiguous-style
    soft fallback for uncertain NLI verdicts either.
  - **DRAGIN (Su et al., ACL 2024):** retrieve on information need, at
    claim/hop level (gaps, EIG, saturation precheck). The RIND/QFS mechanism
    is NOT implemented and cannot be: it needs token probabilities and
    attention weights, which the Groq API does not expose.
  - **Titans (Behrouz et al., NeurIPS 2025):** the WEAKEST borrowing — the
    paper must not overclaim it. Titans' core is a neural memory updated by
    gradient descent at test time, surprise defined as the gradient norm.
    ERag's BeliefMemory is a symbolic store of verified belief strings — no
    gradients, no test-time training. Genuinely borrowed: the design pattern
    (surprise-gated writes, decay, bounded capacity), where ERag's "surprise"
    is a decision-level proxy (low self-consistency confidence), not a
    gradient. Say "surprise-gated write idea only" (the Nov 4 report already
    does) and never imply test-time training. Titans' caveat transfers: the
    memory's constants (decay 0.98, capacity 200, thetas) are heuristic with
    no theory behind them — and empirically the module barely fires (E5: 2/30).
- **What the paper needs (all of it already produced or planned):** frozen
  results (Test-400 + new dataset), the audit trail (OpenSpec changes as the
  methods record — each change's proposal/design is effectively a methods
  paragraph with its gate result), the error analysis, the cost analysis
  (calls/Q, tokens, dollars), and the ablations (the tuning steps are natural
  ablations: v1 → +step 1 → +step 2 → …).
- **Venue:** undecided. The forwarded audit prompt suggested Springer; that
  is the prompt's suggestion, not a user decision (§9).
- **What is not in this plan:** writing the manuscript itself — that is a
  separate piece of work once the results exist, with its own OpenSpec
  change if the user wants the same discipline for it.

---

## 7. OpenSpec workflow (the building discipline)

This is how §3's steps are built. It is the same workflow used for
TrueAdaptive v1 and for steps 1–2.

1. **One change per step.** A change is a directory
   `openspec/changes/<step>/` with `proposal.md`, `design.md`, `tasks.md`,
   and `specs/<name>/spec.md`. The proposal states why (with numbers),
   what changes, considered alternatives, non-goals, and impact. The design
   states the mechanisms and the deferred variants. The tasks list the
   checkboxes including the gate. The spec states requirements with
   scenarios in SHALL/WHEN/THEN form.
2. **Proposal before code.** No `src/` change lands without a validated
   change the user has seen (`openspec/project.md` convention). `openspec
   validate --all` must be 0 failed before implementation.
3. **Threats to validity (mandatory in every proposal).** Each proposal
   names what could make its A/B lie: cache staleness and key versioning,
   live-call nondeterminism, dev noise, prompt anchoring, selection effects.
   Step 1's proposal named the namespace-reuse assumption — that is how its
   failure was caught. A proposal without this section is incomplete.
4. **Tests first.** Mocked-LLM tests before implementation, including the
   flag-off case (byte-identical to the previous system).
5. **Flags, not forks.** Every mechanism lands behind a config flag
   (default off). The previous system stays runnable; the A/B is a flag flip.
6. **Archive when the step closes.** `openspec archive <change> -y` (always
   with `-y` — without it the command blocks forever on its confirmation
   prompt, see §10), then the
   next change starts. Archiving is bookkeeping and must not block the next
   step's proposal (step 1's archive command hung — see §10 — and step 2's
   proposal was committed anyway).
7. **What OpenSpec does not do.** It validates document structure, not
   science. It cannot tell you whether a design is right, whether dev can
   measure the effect, or whether a gate is meaningful. Those are judgments,
   recorded in the proposal, and tested by the A/B — not by the validator.

## 8. Evaluation and measurement discipline

- **Dev-100 is a smoke test.** It answers: did the change break anything
  catastrophically? Are calls in budget? Does the mechanism fire at a sane
  rate? It does not answer: does the mechanism work? (N=100, 1-pt steps,
  ±10 pt noise, plus ~±3 rows of live-call noise.) A dev wash is
  inconclusive, not a pass or a fail — the mechanism is judged on Test-400.
- **Within-run measures beat paired comparisons on dev.** When a mechanism
  logs per-row (re-read triggers, claim sources), the within-run estimate
  (fixed vs broke on triggered rows, gold-in-claims rate) is cleaner than
  the headline EM difference, because it is not confounded by live-call
  noise on untouched rows. Every step's gate includes at least one
  within-run measure.
- **Verify `cache_hits` before believing a paired comparison.** The step-1
  lesson: if the tuned run's mean `cache_hits` is ~0, the run was all-live
  and the comparison carries live-call noise. Say so in the report; do not
  present the headline as clean.
- **Reproduce, don't re-derive.** The analysis script
  (`scripts/analyze_trueadaptive_test400.py`) and the verification script
  (`scripts/verify_results.py`) are the instruments. Numbers in reports come
  from running them, not from hand computation. EM uses the repo's
  `exact_match` — never a hand-rolled normalizer (the analysis once
  undercounted ~3 pts that way; the committed script reproduces the report
  numbers).
- **Dedupe by id, keep the last row.** Resume-retried questions leave stale
  failed rows in output files. Every analysis dedupes.
- **Never conflate the two unknown populations.** System abstentions
  (`abstained`, low `answer_conf`) and model refusals (draft literally
  "unknown", high `answer_conf`) are different mechanisms with different
  fixes. Any report that merges them is wrong.

## 9. Open decisions

| # | Decision | What decides it | Status |
|---|---|---|---|
| 1 | New dataset: 2WikiMultiHopQA or MuSiQue | The paper's claim (§5) | Open — user's call, before Phase 3 starts |
| 2 | `theta_abs`: selective answering vs max EM | The paper's goal (§3.4) | Open — user's call, before step 4 starts; if undecided, step 4 is skipped and `theta_abs` stays 0.4 |
| 3 | Keep step-1 re-read if Test-400 shows no gain | The pre-registered verdict (§4.2) | Decided by test, not by dev |
| 3b | Memory in the frozen Test-400 system (on or off) | Step 6 gate (§3.6): stream A/B gain or call reduction, override test passes | Open — decided by step 6, before the §4.1 freeze |
| 3c | Add the report's confirmatory H1/H4 analyses to Phase 2 (H1: TA vs Standard, paired bootstrap + McNemar; H4: adaptive vs no-adaptive ablation — needs a Test-400 ablation run) | The report (Nov 4) labels E-RAG vs IRCoT exploratory; H1/H4 are confirmatory with Holm correction | Open — the §4.2 verdict as written tests the exploratory comparison |
| 4 | When (and whether) to push `trueadaptive` to origin | User, each time | Open — nothing pushed so far |
| 5 | Push master `.mailmap` commit (`88f2512`) | Needs a fresh GitHub token, transiently | Open — housekeeping, not blocking |
| 6 | Paper venue | User, after results exist | Open — Springer was the forwarded prompt's suggestion, not a decision |
| 7 | Whether the closed-book gate (v2) is ever built | Only if a later diagnosis shows retrieval is the bottleneck; the current analysis says it is not | Deferred |
| 8 | FlashRAG + other unsupplied inspiration papers: supply them, or confirm out of scope | User | Open — related work (§6) cannot be closed without them |

## 10. Risks, known gaps, and findings log

- **Live-call nondeterminism (measured).** gpt-oss-20b at temp 0.0 flips
  ~8 rows per 100 on untouched questions between all-live runs (step-1 A/B).
  Consequence: dev EM differences smaller than ~3 rows are noise; Test-400
  paired McNemar is the judge. Mitigation: within-run measures (§8),
  pre-registration (§4).
- **Cache-key versioning (M3).** Old cache rows never hit under a new key
  version. Any proposal that assumes cache replay must verify `cache_hits`
  after the run. The namespace-reuse exception in step 1's proposal was
  wrong for exactly this reason.
- **Runtime restarts.** The VM restarts during long runs (twice so far). The
  runner's checkpoint resume works (skip completed ids) — proven in the v1
  Test-400 run and the step-1 dev A/B. Long runs are launched detached and
  resumed, not restarted from scratch.
- **Empty draft completions.** One live draft call returned an empty string
  (step-1 A/B, row `5a865bbf`). The Phase A guard prevents *caching* empty
  completions, but a live empty draft still propagates as `""`. Pre-existing
  robustness gap; a fix (retry on empty draft, or treat empty as "unknown")
  is a candidate small change, not part of any tuning step.
- **Re-read formatting breaks.** The step-1 re-read broke one correct answer
  on formatting ("1970s and 1980s" → "1970s–1980s"). Exact match is brittle
  to formatting; the re-read prompt already asks for the short-answer format,
  and the model still varied it. Worth one line in the paper's limitations;
  not worth a tuning step on its own.
- **OpenSpec CLI hangs — RESOLVED 2026-11-09.** The `openspec archive
  tune-reader-grounding` command ran ~18 minutes with no output, then the
  runtime restarted and the session had no confirmed result. Root cause
  found on recovery: the command was run WITHOUT `-y`, so it was waiting on
  an interactive confirmation prompt with no TTY — not a CLI bug. Re-ran
  once with `-y`: archived in ~1s as `2026-11-09-tune-reader-grounding`,
  spec merged to `openspec/specs/reader-grounding/spec.md`, validate 4
  passed 0 failed. **Lesson: always run `openspec archive` with `-y`
  (non-interactive) in this environment; without it the command blocks
  forever on its confirmation prompt.**
- **`--set` overwrites.** The runner's `--set` is `nargs="*"` with default
  store action: repeated `--set` flags overwrite, only the last survives.
  All overrides go in ONE `--set`. (Caught in step 1: the first A/B attempt
  silently re-ran the MiniLM dev file; no files were touched.)
- **Memory effectiveness is unproven (E5 null).** The only memory A/B
  (N=30 stream, Reference system) was identical with memory on vs off
  (EM 0.4000, 14.3 calls/Q; fired on 2/30). Only the override mechanism is
  verified. Until step 6 runs on the tuned system, the paper cannot claim
  memory helps — and the plan now says so (§3.6).
- **No manuscript in the repo.** The paper's hypothesis as stated by its
  authors has not been read here (no `paper/`, no README, the Implementation
  Guide PDF is not in the repo). The hypothesis in §3.6 is inferred from
  code and repo docs. If the manuscript or Guide is supplied, the plan's
  hypothesis statement is corrected against it before Phase 4.
- **Groq key handling.** Keys are supplied in chat, smoke-tested with 1 call,
  used transiently via env var, never saved. Rotation is advised after use
  (a key pasted in chat should be treated as exposed).

## 11. Branches, remotes, and housekeeping

- `origin` = `Saumojit30/erag` (fetch + push, only push target).
  `upstream` = `ManojAdapakala/ERag` (fetch only, push URL `no_push`).
- Branch `trueadaptive`: all adaptive work, tuning, remediation, results.
  Branch `master`: merged upstream Phase 5 + `.mailmap` fix.
- Credentials: none saved anywhere. Every push and every Groq run needs a
  fresh transient supply from the user.
- VM quirks (verified, do not re-learn): Groq/httpx needs BOTH `NO_PROXY`
  and lowercase `no_proxy` set to `localhost,127.0.0.1`; retrieval tests
  need `HF_HUB_DISABLE_XET=1` (XET endpoint returns 403; MiniLM ~90MB cached).
- Files deliberately left uncommitted: `results/cache.sqlite`,
  `results/nli_memo.pkl` (modified by runs). Untracked: `configs/erag_adaptive.yaml`
  (old untested draft), `docs/`, `openspec/project.md`.

---

## Appendix — Key numbers (frozen)

**TrueAdaptive v1, Test-400 BM25 (N=400, 0 failed, 0 cache hits):**
EM 0.4750, F1 0.6192, 4.78 calls/Q, coverage 0.8075, recall 0.8975.
Calls {2:86, 4:59, 5:126, 6:75, 7:23, 8:18, 9:13}; hops {0:160, 1:198, 2:42}.

**IRCoT fresh, Test-400 BM25:** EM 0.4200, F1 0.5674, 2.55 calls/Q,
coverage 0.78, recall 0.7975. McNemar vs TA: b=38, c=16, p=0.0043
(exact 0.0038).

**Error budget (Test-400):** right 190, wrong 133, abstained 37,
model-unknown 40. Full-recall wrong 107/133; gold in claims 70, never
claimed 37. Hops: hop-0 draft EM 0.4050 → final 0.4750 (fixed 42, broke 14).
Unknowns: abstentions `answer_conf` median 0.214 (17 correct drafts);
reader refusals `answer_conf` median 0.875, `c0` median 1.000. Call tail:
54 rows ≥7 calls = 422/1,910 calls (22%) at EM 0.333. Fast-path SC skips:
86 rows, 2.00 calls, EM 0.5465.

**Theta sweep (dev-selected; test diagnostic only):** dev t=0.00 → 0.58,
t=0.10–0.30 → 0.57, t=0.40 → 0.56; test t=0.00 → 0.5175.

**Costs:** Groq `openai/gpt-oss-20b`, $0.10/$0.20 per 1M tokens (input/output).
v1 Test-400: 4.78 calls/Q. Balanced Test-400: 8.95 calls/Q at EM 0.4450.

**History:** this plan supersedes the forwarded audit prompt's roadmap
(Phase 5, four retrievers, Springer manuscript) as the *sequencing*
document. That prompt's audit findings were used (and corrected where wrong:
"45.4% reduction" is −39.8% calls; manifest SHA `0346c86f…`; Standard Dev-100
EM is 0.4400, not 0.4200), but its order is not this plan's order. The user's
order (§1) governs.
