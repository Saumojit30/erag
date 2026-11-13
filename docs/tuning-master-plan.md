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
Step 4's goal is now set by the user (2026-11-09): reduce hallucination
is the main objective, reduced LLM cost second — so step 4 is selective
answering, and its change is being drafted. Steps 5–6 changes are drafted
(design-only, uncommitted, validated). Test-400, new dataset, and paper
are planned here and not started. This plan is the document OpenSpec changes
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
  **EM 0.4200, F1 0.5674, 2.545 calls/Q**. McNemar paired b=38, c=16,
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
- **Step 2 (claim extraction) — DONE, gate 3/4, kept by user decision,
  archived 2026-11-09.** OpenSpec change `tune-claim-extraction`
  (commit `0e51368`), build `8c9f25e`, archived `c062baf`. Question-grounded
  claims in the single extraction call (zero new LLM calls), each claim with
  a `"source"` field, `max_claims` 5→8. Dev A/B: EM 0.5400 vs 0.5600 (−2 rows,
  inside ±3-row noise), gold-in-claims among full-recall wrong rows 0.524 vs
  0.333 baseline, answer-bearing question-sourced 6/100 (gate ≤10% PASS).
  Gate failed on EM only; user chose to proceed. Tuned value: `max_claims: 8`.
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
  1/5 planted) — BUT the E5 test is now known to be cache-confounded
  (mem arm served cache_hits == llm_calls on 30/30 rows), so the
  verdict rested on an uninformative test, not a real null. The step-6
  re-test (2026-11-10, tuned system, all-live) is ALSO under-powered:
  mem fired on 1/30 (floor 5/30), verdict "instrument too weak" —
  memory stays OFF, H5 stays NOT SUPPORTED with a dated note (§3.6);
  H4 NOT TESTED on
  Test-400 (dev interim inconclusive; 3× latency bound unmeetable as
  stated and cache-confounded — needs a dated clarification); H2 NOT
  SUPPORTED, narrow miss (macro-F1 0.6825 < 0.70, contradicted recall
  0.75 ≥ 0.70; supported recall 0.60 is the weakness).
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
| IRCoT fresh, Test-400 | BM25 | 0.4200 | 0.5674 | 2.545 |
| Balanced, Test-400 | BM25 | 0.4450 | — | 8.95 |

Full numbers (coverage, recall, selective EM, McNemar) are in the error
analysis report and the appendix. The Test-400 TA file has 401 lines for 400
questions (a resume retried 1 failed question, leaving a stale failed row) —
always dedupe by id keeping the LAST row.

### 2.3 Branch and remote state

- Branch `trueadaptive`: all tuning and remediation work. HEAD `b885297`,
  19 commits ahead of origin, unpushed (needs a fresh GitHub token).
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

### 3.4 Step 4 — theta_abs (DONE 2026-11-09 — theta_abs=0.50, gate PASS on the pre-registered counterfactual)

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
  **Decided 2026-11-09 by the user:** the main objective is to REDUCE
  HALLUCINATION of RAG, with reduced LLM cost second — so step 4 is
  selective answering. Judge by selective EM and wrong-answer rate, with
  EM as a guardrail (not the maximand). The formal paper-goal statement is
  still open and can be refined later; this objective is what the step is
  built on.
- **OpenSpec change:** `tune-theta-abs` (archived 2026-11-09).
- **Outcome:** A.1 analyzer `--theta` section built, verified, committed
  (5738181; 69 tests passed). Live A/Bs ran 2026-11-09 (100/100, 0
  failed) but the pre-registered cache tripwire FIRED (live calls/Q 0.04
  / 0.02 — ~99% replays, because the threshold changes no prompt and no
  call, so the reused namespace served the step-2 run's cached calls);
  both files DISCARDED as evidence per the rule. User decision
  2026-11-09: accept the pre-registered counterfactual as the evidence
  (dated amendment in the change's design.md — the tripwire's premise is
  false for threshold-only steps; the counterfactual numbers were fixed
  before the runs, so nothing is cherry-picked). Gate on the
  counterfactual: both candidates PASS all four measures (selective EM
  0.6456 > 0.6353; wrong 0.3544 < 0.3647; EM 0.5100 ≥ 0.51, exactly at
  the bound; calls 4.65/4.64 within 0.2 of 4.65); identical wrong-rate
  falls → tie rule selects candidate A, **theta_abs = 0.50**, coverage
  0.790. Tuned value recorded for the frozen tuned config. Margins are
  1 row, inside the ±3-row dev noise band — the gate is a smoke test and
  Test-400 is the judge.
- **Dev gate (smoke test):** EM and selective EM move in the direction the
  goal requires; calls unchanged (thresholds cost no calls). If the goal is
  undecided when step 4 starts, the step is skipped and `theta_abs` stays
  0.4 — a missing decision is not a reason to tune blind.

### 3.5 Step 5 — Hop-2 SC cap (A/B DONE, SUPERSEDED by step 7 — see below)

- **Evidence:** 54 rows ≥7 calls consume 422 of 1,910 calls (22%) at EM
  0.3333; 20 of them end unknown. Mean calls by hops: 0→3.02, 1→5.52,
  2→7.95. The hop-2 rows are the most expensive and the least accurate.
- **Mechanism (to be designed in its change):** cap the self-consistency
  work on hop 2 (e.g. skip post-hop resampling on hop 2, or cap SC samples
  on hop 2 at 1), so the tail costs less. This is a pure cost lever: expected
  saving ≈ 100 calls/400 questions, measurable precisely from the output
  file. EM effect must be measured, not assumed — if hop-2 SC is load-bearing
  for the few rows it helps, the cap is narrowed, not forced.
- **OpenSpec change:** `tune-hop2-sc-cap` (DRAFTED 2026-11-09, design-only,
  uncommitted, validate 6 passed 0 failed). Correction found in the draft:
  the plan's SC-cap sketch doesn't match the code (SC runs once, at hop 0),
  so the mechanism is `erag.max_hops=1`, config-only, zero code. Expected
  saving ~74 calls/400 test at draft-level −2 rows.
- **Dev gate (smoke test):** calls/Q falls with EM not below the step-4
  tuned dev by more than 1 pt (a cost step that costs accuracy is a trade,
  not a win, and the trade is decided at the Test-400 verdict, not on dev).
  Post-step-4 tuned dev baseline (the step-4 A file,
  `results/trueadaptive/erag_trueadaptive_bm25_dev_theta_a.jsonl`): EM
  0.5100, 4.65 calls/Q — so step 5's gate is EM ≥ 0.5000 with calls/Q
  and live calls/Q below 4.65.
- **A-build (DONE 2026-11-09, commit 5c01ede):** mocked-LLM cap test
  (`tests/test_erag.py`, cap binds at 5 calls, control reaches hop 2
  at 6) + `--hopcap` analyzer section 14
  (`scripts/analyze_trueadaptive_test400.py`, 9 tests in
  `tests/test_analyzer_hopcap.py`). Verified by the parent: reproduces
  the pre-registered numbers exactly on all three stored files (step-2
  dev 10 hop-2 rows / 78 calls; Test-400 42 / 334, tail 54 / 422;
  theta_a baseline EM 0.5100, 4.65 calls/Q). `max_hops` read only at
  `src/systems/erag.py:240`. Live A/B (C.1) needs a Groq key,
  transient only.
- **A/B (DONE 2026-11-09) + VERDICT: SUPERSEDED (commit 7a3598c,
  archived as `2026-11-09-tune-hop2-sc-cap`).** A/B finished 100/100,
  0 failed: EM 0.5100 (unchanged), F1 0.5969, calls/Q 4.49 vs 4.65
  (−0.16), live calls/Q 0.06 vs 0.04 (+0.02), hop-2 rows 10→0,
  hop-2 calls 78→0. As written the gate FAILS on the live-calls
  measure only (6 vs 4 live calls, both runs ~99% replays — replay
  noise). The user chose the learned continuation policy (step 7)
  instead of deciding the gate: the hop-depth decision is the
  policy's job now, `max_hops` stays 2 as a ceiling, the static cap
  is not adopted. The gate is not re-judged.

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
- **OpenSpec change:** `tune-memory-effectiveness` (DRAFTED 2026-11-09;
  A/B measurement build DONE 2026-11-09, commit e5da900; validate 8
  passed 0 failed). Decision was to extend stream 30→60 Qs (5→10
  clusters × 6), first 30 rows byte-identical — **NOT done: the raw
  HotpotQA file fetch failed a third time (2026-11-09, both CMU mirror
  variants return curl (52) Empty reply), so the pre-registered N=30
  fallback stands**; the 30-row sidecar
  `data/manifests/stream_clusters.json` is committed. A/B measurement:
  `--position` section in `scripts/eval_memory.py` (11 tests,
  reproduces all E5 numbers exactly) + `mem_store_size`/`mem_texts`
  row fields in `run_erag` (2 mocked tests, proven genuine by
  stashing). Full suite 111 passed, 1 failed (known retry-test
  mismatch). The stream A/B (C.1) awaits the step-5 verdict and a
  Groq key.
  **E5 cache finding (2026-11-09, verified from stored rows):** the E5
  effectiveness null is cache-confounded — the mem arm served
  `cache_hits == llm_calls` on 30/30 rows (shared default namespace),
  answers/EM/F1 identical to nomem. Memory changed no LLM prompt in E5,
  so H5's NOT SUPPORTED rests on an uninformative test; the override
  mechanism is NOT confounded. Step 6 uses one fresh namespace per arm
  with a live-calls tripwire, and H5 is revisited after step 6 with a
  dated note. Raw HotpotQA file is absent from this VM — extension needs
  a scripted fetch, fallback to N=30 as-is.
- **Gate:** memory goes into the frozen Test-400 system ONLY if the stream
  A/B shows an EM gain or a call reduction with EM not falling, and the
  override test passes on the tuned system. Otherwise memory stays OFF for
  Test-400 and the paper reports it as a null: the override mechanism is
  verified, the effectiveness is not demonstrated on the available stream.
  A null here does not block Phase 2; it scopes the paper's claims.
- **OUTCOME 2026-11-10 — CLOSED, verdict "instrument too weak" (NOT a
  clean null).** C.1 ran 2026-11-10 on the post-step-7 tuned system
  (three arms, fresh namespaces, N=30 fallback): nomem EM 0.6000, F1
  0.6614, 4.73 calls/Q; mem EM 0.6667, F1 0.7354, 4.60 calls/Q;
  planted EM 0.6333, F1 0.7284, 4.67 calls/Q — all N=30 deduped, 0
  failed. C.2 tripwire PASSES: live calls/Q ≈ llm_calls/Q per arm
  (cache_hits/Q 0.07 nomem — 2 hits from the retried rows — 0.00 mem,
  0.00 planted). **D.1 gate: (1) FAILS — mem fired on 1/30 (floor
  ≥5/30); (2) would pass (ΔEM +0.0667, Δcalls/Q −0.13, fired-row
  paired difference 0/0) but cannot be attributed to memory — the
  single fired row changed nothing, so the +2 EM rows are noise
  inside the usual ±3-row band; (3) override 1/1 retrieved (Becker
  purged), but the checker's 2 false-claim flags are substring false
  positives (gold-correct answers 'German' and 'private' on rows
  where nothing was retrieved).** Memory stays OFF; H5 stays NOT
  SUPPORTED, revisited with a dated note (see the status doc). The
  run itself was interrupted twice: the VM restarted overnight
  (first launch died at nomem 24/30; transient keys lost, re-sent by
  the user), and the first resume used a doubled `--set` (which
  overwrites — ran the DEV split, wrote 2 dev rows into the stream
  file; killed, rows removed, file restored to 24 stream rows,
  relaunched with one `--set`). Outputs:
  `results/trueadaptive/stream_tuned_{nomem,mem,planted}_v1.jsonl`.
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

### 3.7 Step 7 — Learned continuation policy (NEW MECHANISM, user-chosen 2026-11-09)

The user asked whether the system is properly adaptive or just static
values. The structure is adaptive (per-question effort 2→9 calls,
H6 shows the work lands where retrieval was incomplete), but the
decision boundaries are hand-set constants — steps 1–6 calibrated
them, none made the system more adaptive. This step replaces the
fixed hop-0 continuation decision with a learned one: a logistic
regression on hop-0 features (c0, claim verification statuses,
hop-0 recall, question type, draft-unknown flag) predicting P(hop-0
draft is correct); CONTINUE iff P < τ, τ chosen by 5-fold
cross-validation on dev. It subsumes the theta_fast fast-path rule
and the first gap-continuation rule at hop 0. EIG gap selection, SC,
abstention (theta_abs=0.5), and max_hops=2 (ceiling) are unchanged;
hop-1+ continuation stays static.

- **Training data:** dev only (post-step-4 tuned traces, N=100);
  Test-400 is never used for training, feature selection, τ choice,
  or model selection. Label (hop-0 draft correct) is 48/100 — the
  framing that makes this learnable at N=100 (predicting
  "continuing helps" has only 6 positives). Dev verification
  numbers (theta_a): hop-0 draft EM 0.4800, final EM 0.5100, fixed
  6, broke 3, hops {0:45, 1:45, 2:10}.
- **Gates (pre-registered, change `learned-continuation-policy`,
  drafted 2026-11-09, validate 9 passed 0 failed):** (A) offline
  counterfactual simulation on dev, out-of-fold only — simulated EM
  ≥ 0.5000 AND simulated calls/Q strictly below 4.65, else the
  policy is not wired in; (B) live Dev-100 A/B — live EM ≥ 0.5000
  AND live calls/Q strictly below 4.65 AND live numbers within
  ±0.02 EM / ±0.2 calls/Q of the simulation. Live calls/Q is NOT
  gated (the step-5 lesson: two 99%-replay runs can't discriminate
  on live calls).
- **Phase A DONE 2026-11-09, verified by the parent by independent
  re-run (scripts + training set + simulation + analyzer §15).**
  Extraction reproduces every verification number exactly
  (accounting violations 0 — the invariant is exact, no
  approximation needed). Oracle ceiling: included 83, excluded 17,
  EM 0.6506, calls/Q 4.61 — saves only 0.04/Q, because 28 of the 48
  correct drafts already stop at hop 0 under the static fast path.
  LR (τ = 0.30, 5-fold CV, OOF): simulated EM 0.5000, F1 0.5837,
  calls/Q 3.98 (saved +0.67), coverage 0.766, STOP 70 / CONTINUE
  24, excluded 6/100 (6.0%). **Gate A: PASS, exactly at the floor**
  (0.5000 = 47/94; one fewer correct row fails it). Honest reading:
  the saving is bought by stopping on wrong drafts — the policy
  STOPs on 4 of the 6 fix-rows (loses 4 fixes) and saves 1 of 3
  breaks; F1 and coverage dip below baseline. OOF AUROC 0.6546 vs
  c0 alone 0.484. No Test-400 data anywhere in training/features/τ
  (only a path constant in tests, used to assert refusal). Fast
  suite 126 passed, 1 failed (known retry mismatch).
- **Final model trained 2026-11-09 after the user chose "Wire it in"**
  (commit `d0fb457`): artifact `configs/continuation_policy_dev.json`,
  τ = 0.30, OOF AUROC 0.6546, verified to 2.2e-16. **SUPERSEDED —
  see the retrain below; the τ = 0.30 artifact must not be used for
  wiring.**
- **RETRAIN 2026-11-09 (commit `7872b24`) — the original Gate A pass
  is superseded.** The B.1 subagent found `draft_unknown` was trained
  on the row draft (the FINAL draft, `erag.py:354`), which does not
  exist at the hop-0 decision point; the parent verified the two
  definitions diverge on 16/100 dev rows (15 hop-0-unknown → final
  real answer, 1 real → unknown) while the other 11 features agree
  exactly. The user chose the retrain. Re-extraction with the hop-0
  definition (`trace[0]['answer']`) + re-training, same pre-registered
  gate: LR, τ = 0.05, simulated EM 0.5152, F1 0.6238, calls/Q 3.92
  (saved +0.73), coverage 0.869, STOP 81 / CONTINUE 18, excluded
  1/100 (1.0%); OOF AUROC 0.6775. **Gate A re-check: PASS with
  margin** (EM +0.0152 above the floor; F1 and coverage now ABOVE
  baseline 0.5969 / 0.790; composition: STOP on 2/6 fix-rows, 2/3
  broke rows saved). New artifact written (τ = 0.05,
  `draft_unknown` coef −1.489), verified to 2.2e-16; suite 127 passed,
  1 failed (known retry mismatch). B.1 re-spawned with the corrected
  brief; C.1 live A/B awaits B.1 + a Groq key. The retrain is a
  methods disclosure for the paper, not a footnote (see
  `docs/paper-readiness-plan.md` W4.3).
- **B.1 DONE 2026-11-09, committed `a0eb216`, verified by the parent:**
  new module `src/epistemic/continuation_policy.py` (load_policy,
  hop0_features, policy_probability, decide_policy — pure arithmetic,
  no sklearn in `src/`) and the wiring in `src/systems/erag.py`
  (+67/-9). Decision point after the deferred-SC resolution
  (c0/c0_source final); deferred fast-path `break` conditional on
  the policy being absent. 12 new mocked tests (STOP fast-path, STOP
  despite gaps, CONTINUE unknown draft, CONTINUE fast-path weakest
  claim, `no_conf`, flag-absent controls, feature agreement,
  artifact validation). Parent verification: definitions identical
  to `extract_features` incl. `draft_unknown` from the hop-0 draft;
  feature agreement row-for-row 1e-9 on all 100 dev rows; module
  probabilities match the fitted pipeline to 1.1e-16 and decisions
  reproduce the artifact's in-sample split (STOP 81 / CONTINUE 19);
  tests proven genuine by stashing the wiring (5 behavior tests fail
  without it); full suite 139 passed, 1 failed (known retry
  mismatch). Parent-added hardening: load_policy requires the
  artifact's feature list to be exactly the 12 MODEL_FEATURES in
  order. Frozen v1 config untouched; no Test-400 access; no live
  runs.
- **C.1 live A/B DONE 2026-11-09, committed `4c9576f`, Gate B PASS.**
  Detached run (~35 s, mostly cache replays), 100/100, 0 failed, 0
  API failures; output
  `results/trueadaptive/erag_trueadaptive_bm25_dev_policy.jsonl`
  (100 lines, 100 unique ids). Live: EM 0.5000, F1 0.6114, calls/Q
  4.07 (live 0.11, recorded not gated), coverage 0.83, selective EM
  0.6024, recall 0.765, retrievals 1.32/Q. Baseline theta_a: EM
  0.5100, 4.65 calls/Q (ΔEM −0.0100, Δcalls/Q −0.58). Agreement vs
  the retrained simulation (EM 0.5152, 3.92/Q): dEM −0.0152, dCalls/Q
  +0.15 — within the pre-registered ±0.02 / ±0.2. STOP 81 (EM
  0.5679) / CONTINUE 19 (EM 0.2105); hops {0:82, 1:15, 2:3}. **Gate
  B: PASS** — live EM 0.5000 ≥ 0.5000 (exactly at the floor), calls/Q
  4.07 < 4.65, agreement within bounds, N=100 deduped, 0 failed.
  The policy ENTERS the frozen Test-400 system. Honest reading:
  live EM is 1 row below baseline; Test-400 is the real judge.
  **Analyzer bug found during C.1 and fixed the same day:**
  `policy_metrics` (§15) compared `policy_decision` against
  uppercase STOP/CONTINUE while the runner writes lowercase per the
  design contract — the first analysis reported 0/0/100 unknown.
  Fixed by case-normalizing the field; tests switched to the
  lowercase contract + a case-insensitivity regression test; full
  suite 140 passed, 1 failed (known retry mismatch).
- **Interaction:** step 5 is SUPERSEDED by this step (see §3.5) —
  the hop-depth decision is the policy's job now. Step 6's stream
  A/B runs on the post-step-7 tuned system (the policy passed Gate
  B) and awaits a Groq key.

### 3.8 What is explicitly NOT in Phase 1

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

**DATED AMENDMENT 2026-11-09 (before any Phase 2 run — no Phase 2
result has been seen):** the tuned system below now includes step 7
(the learned continuation policy) and its artifact in the frozen
config, because step 7 was created after §4 was written and its Gate A
re-check passed with margin (commit `7872b24`, τ = 0.05, sim EM
0.5152, calls/Q 3.92). If the policy fails Gate B, the frozen config
uses the post-step-4 system instead and the amendment is updated to
say so before the run.

- **Systems:** (a) tuned TrueAdaptive — all gated tuning steps (1–7)
  plus the memory decision from step 6 (§3.6), frozen config; (b)
  fresh IRCoT — same frozen config as the v1 Test-400 run.
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
  `theta_abs`, hop-2 cap, the memory on/off decision from step 6, and the
  continuation-policy artifact from step 7 — `erag.continuation_policy`
  pointing at `configs/continuation_policy_dev.json` if Gate B passes).
  IRCoT runs its existing frozen config. No `--set` overrides at run time
  except the retriever, namespace, and run name — the frozen files are the
  record.
- **Run order:** tuned first, then IRCoT, sequential, detached, with
  checkpoint resume (proven twice: the v1 Test-400 run and the step-1 dev
  A/B both survived runtime restarts via the runner's skip-completed-ids
  recovery). Output files are new; the v1 Test-400 files are never
  overwritten.

**DATED AMENDMENT 2026-11-10 (D2 component ablations, publication-ready
plan §3.3 — written before any Phase 2 run; no Phase 2 result has been
seen):** three ablation runs join Phase 2, testing new hypothesis H7
(each adaptive component carries part of the gain; see
`docs/hypotheses-current-status.md`). All three are Test-400 BM25,
fresh namespaces, config overrides only, no code:

- **SC-off (1 run):** tuned system + `erag.sc_mode=fixed`
  `erag.sc_samples=5` — fixed 5-sample SC instead of sequential
  (M=1→3, ΔH<0.05). Both overrides are needed: the frozen config sets
  `sc_samples: 3`, so `sc_mode=fixed` alone would run fixed SC with 3
  samples, not the 5-sample reference. Namespace
  `test_tuned_sc_fixed_v1_bm25`. Judged vs the tuned run (paired).
- **Fast-Path-off (2 runs, a pair):** the publication plan assumed this
  is one flag (`erag.ablate=[no_fast]`). Reading `src/systems/erag.py`
  on 2026-11-10 shows it is not: in the frozen system the fast path
  fires in the deferred-SC branch, which breaks without consulting
  `no_fast` — and at hop 0 the learned policy has replaced the
  fast-path decision anyway, so `no_fast` alone has ~no effect on the
  tuned system. The flag only bites when SC is NOT deferred. So the
  pair holds SC timing constant (eager in both arms,
  `erag.gate_sc_behind_fast_path=false`): (a) control, fast path on;
  (b) fast path off, `erag.ablate=[no_fast]`. The (b)−(a) difference
  isolates the fast path's retrieval-skipping effect. Namespaces
  `test_fp_control_v1_bm25` and `test_fp_off_v1_bm25`. Judged within
  the pair (paired), not vs the tuned run — both pair arms differ from
  the tuned system in SC timing, so a comparison to tuned would
  conflate the two changes.
- The H4 no-adaptive ablation (`erag.ablate=[no_adaptive]`, namespace
  `test_noadaptive_v1_bm25`) is separate and unchanged. The §4.2
  verdict is unchanged: it is judged on the tuned-vs-IRCoT BM25
  comparison; the ablations are separately-judged component evidence
  under H7.
- **MiniLM namespaces (added 2026-11-10, with the MiniLM decision
  above):** tuned `test_tuned_v1_minilm`, IRCoT `test_ircot_v2_minilm`
  — fresh, never used before, same frozen configs and `--set` values
  as the BM25 runs except `retrieval.retriever_type=minilm`.

**DATED AMENDMENT 2026-11-10 (Adaptive-RAG Test-400 run, H8 — written
before any Phase 2 run; no Phase 2 result has been seen):** a third
system joins Phase 2 — Adaptive-RAG (Jeong et al., NAACL 2024), the
other-adaptive control (user confirmed 2026-11-10: "yes do adaptive
rag with ircot also"). It does NOT replace IRCoT: IRCoT stays the
fixed control; Adaptive-RAG is the second adaptive baseline. Same
setting (BM25, k=3, distractor, HotpotQA Test-400 N=400), fresh
namespace `test_adaptive_rag_v1_bm25`, output
`results/adaptive_rag/adaptive_rag_test_bm25.jsonl`, system
`adaptive_rag` (`src/systems/adaptive_rag.py`, router → A closed-book
/ B standard / C IRCoT). Gate AR-1 PASSED 2026-11-10 (held-out
accuracy 0.9318 vs 0.50 majority-class rate; Dev-100 routes A0/B45/
C55); a D.1 Dev-100 sanity run (namespace `dev_adaptive_rag_v1_bm25`)
precedes the Test-400 run. Judged under H8 (exploratory): tuned
TrueAdaptive beats Adaptive-RAG on Test-400 BM25 EM at equal-or-fewer
calls/Q; paired McNemar α=0.05; secondaries F1, calls/Q, coverage,
route distribution, per-route EM. The §4.2 verdict is unchanged: it
is judged on the tuned-vs-IRCoT BM25 comparison; Adaptive-RAG is
separately-judged baseline evidence under H8. Caveat, recorded here
so it reaches the paper: the router never predicts route A on
HotpotQA (per-class A accuracy 0.0), so the baseline will effectively
route B/C only.

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
- **AMENDMENT 2026-11-10 (under the delegated mandate, proceeding on the
  recommendation — the user delegated the pre-Phase-2 decisions on
  2026-11-10):** run HotpotQA MiniLM Test-400 regardless of the BM25
  verdict — the MiniLM rule above is superseded for HotpotQA. Rationale:
  the retriever-robustness check is worth having even on a significant
  BM25 result (it tests whether the win is retriever-specific), and the
  publication-ready plan recommends it. If both run, both are reported —
  never pick the better one post-hoc. The §4.2 verdict itself is
  unchanged: it is judged on BM25; the MiniLM result is a second check,
  not a second verdict.
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

## 4.5 Phase 2.5 — Improvement round (user decision 2026-11-11)

**Why:** Phase 2's verdict was INCONCLUSIVE, and the user asked the right
question — if nothing is improving, why just run the same system on a new
dataset? Phase 3 tests generalization; it does not make the system better.
So before Phase 3, one focused improvement round on the tuned system,
targeting the diagnosed bottlenecks. Diagnosis and pre-registration:
`docs/phase25-improvement-diagnosis.md`; script:
`scripts/diagnose_phase25.py`.

**Diagnosis (stored Test-400 rows only, diagnostic, never selection):**
- 53 gold-in-claims wrong rows: the final answer sits inside a WRONG
  supported claim on 34/53; the re-read never triggers on 41/53 (it fires
  only on disagreement/unknown, and these rows agree — with the wrong
  claim). Failure is claim selection at the final read.
- 33 never-claimed rows: hop-0 recall 1.0 on 27/33 — evidence retrieved,
  never extracted. Extraction-recall failure.
- Eager SC (FP-control): 19 gains / 12 losses, net +7, p=0.28 — churns the
  answer/abstain boundary both ways; weak directional evidence.
- theta_abs is NOT a lever: lowering it would raise EM but also the
  wrong-answer rate, against the paper's first objective.

**Pre-registered hypotheses (written 2026-11-11, before any new run):**
- **H12** — contested-claim resolution at the final read (≥2 supported
  answer-bearing claims disagree → re-read grounded on the competing
  claims). Dev-100 BM25: EM gain ≥ +0.02 at ≤ +0.5 calls/Q.
- **H13** — second extraction pass over the hop-0 pool. Dev-100 BM25:
  gold-in-claims rate among full-recall wrong rows rises vs the tuned dev
  baseline, EM does not fall.
- **H14** — eager SC (`gate_sc_behind_fast_path=false`) replicates the
  FP-control direction on Dev-100 BM25 at ≤ +1.0 calls/Q. Circularity
  note: the direction was observed on Test-400 first, so dev is a
  replication check and the Test-400 FP-control number cannot be re-judged.

**Order:** H12, then H13, then H14 — one OpenSpec change each, same
lifecycle as Phase 1 steps (diagnose → change with Threats → tests →
flag → Dev-100 BM25 A/B, gate as smoke test). Then freeze the improved
config and run **one** Test-400 confirmation (improved vs fresh IRCoT,
same verdict shape as §4.2). Then Phase 3.

**DATED AMENDMENT 2026-11-11 (freeze after H14):** Phase 2.5 is
closed. The improved system is frozen in
`configs/erag_trueadaptive_improved.yaml`: the tuned config plus
`erag.contested_resolution: true` (H12) and
`erag.gate_sc_behind_fast_path: false` (H14);
`erag.second_extraction: false` (H13 dropped); everything else
identical to the frozen tuned config (theta_abs 0.50, memory OFF,
continuation policy on, max_hops 2, max_claims 8). Nothing changes
after this freeze without a dated amendment. Next: ONE Test-400
confirmation (improved vs fresh IRCoT, same verdict shape as §4.2),
then Phase 3 with the improved system.

**Rules:** no tuning against Test-400 (diagnosis only); no theta_abs
change; no v1 substitution — the tuned system stays the base. If the
improved system beats v1 on the confirmation run, that is reported as a
result, not used to pick the system post-hoc.

---

## 4.6 Phase 2.6 — Beat-IRCoT round (user direction 2026-11-11)

The user asked for a model that reduces hallucination and beats IRCoT
first, then Adaptive-RAG, with the approach choice left to the
assistant. Full pre-registration: `docs/phase26-beat-ircot-plan.md`
(written 2026-11-11, before any new run). Order: (0) the Phase 2.5
confirmation above (improved vs fresh IRCoT) is the baseline this round
must beat; (1) H15 support-ranked final re-read; (2) H16 verifier
threshold sweep; (3) ONE Test-400 confirmation of the final system vs
fresh IRCoT. Win (pre-registered): EM > IRCoT AND paired McNemar
p < 0.05 AND wrong-answer rate down vs IRCoT (roughly 0.475+ against
IRCoT's 0.4225). H17 (calibrated abstention) is a candidate only, not
pre-registered. Rules as in §4.5, plus: if the confirmation is still
inconclusive, the paper reports it straight — no new mechanism is
bolted on to escape the verdict without a new pre-registered round.
Phase 3 entry moves to the end of this round (it was the Phase 2.5
confirmation; the system that enters Phase 3 is the one this round's
confirmation judges).

**DATED AMENDMENT 2026-11-11 (H15 gate pass):** support_ranked
enters the system. The final frozen config is written AFTER H18's
verdict (Phase 2.7, §4.7) — the final system is whichever
combination passes its gates — and the ONE Test-400 confirmation
judges that system vs fresh IRCoT. H15 alone is not frozen as a
config yet; the flag is `erag.support_ranked_reread: true` on top of
the improved config.

---

## 4.7 Phase 2.7 — Architecture round (user direction 2026-11-11)

The user asked for architecture change, not parameter tuning: the
codebase is only ~4 days old, the tuning phase treated the pipeline
shape as fixed, and the measurements say the shape is the ceiling
(tuned EM 0.4500 < v1 0.4750; H11 tie; H16 flat; H13 fail).
Full analysis (code-read, no code changed):
`docs/architecture-analysis-hallucination.md` (written 2026-11-11,
committed `db0b46f`). Central diagnosis: the pipeline is draft-first
— the draft is written before any verification exists, claims are
extracted FROM the draft, and verification is advisory (it can veto
or trigger a narrow re-read, never construct the answer). Design
principle for the round: the answer must be entailed by the evidence,
and the system must be unable to output an answer it cannot derive.
The LLM is a black-box API, so all changes are pipeline-level
(prompts, verification, retrieval, answer space), not model-level.

Program (each item = one OpenSpec change, one Dev-300 BM25 A/B vs the
improved system, fresh namespaces, both arms re-run fresh, paired;
gate = dEM >= +0.02 AND wrong-answer rate not up AND dcalls <= +0.5/Q
— the hallucination leg is part of every gate, since EM alone can be
bought by answering more. Decision set amended 2026-11-13, before any
H18 run: Dev-100 → Dev-300 (first 300 rows of
`data/manifests_dev500/dev.jsonl`, 500 fresh HotpotQA dev Qs, seed 29,
disjoint from dev-100/test-400; corpus Dev-500 + Test-400 passages).
Dev-100 CIs (±0.04–0.07) cannot resolve a +0.02 effect — the H15
"pass" at exactly +0.02 was noise-level — so Dev-300 (resolves
~+0.04) with a pre-registered extend rule: dEM in [+0.01, +0.04]
with the 95% CI straddling 0 → AMBIGUOUS, extend to the full Dev-500
instead of calling it. The Dev-500 manifest is committed `7486fa2`;
the full 7,405-row official dev set was re-downloaded from
HuggingFace (CMU URL dead) to build it):

- H18 — evidence-first answering (invert the pipeline: claims from
  passages, answer only from verified claims). Highest value, highest
  cost. **Pre-registered 2026-11-11 (this section +
  `openspec/changes/evidence-first-answering/` +
  `scripts/phase26_h18_verdict.py` + `~/workspace/phase26_h18_chain.sh`):
  on Dev-300 BM25, the evidence-first arm raises EM ≥ +0.02 vs the
  improved-system baseline at ≤ +0.5 calls/Q AND does not raise the
  wrong-answer rate. Decision set amended 2026-11-13, before the run
  (Dev-100 → Dev-300 + extend rule; see the Program note above).
  Exploratory. Per hop the draft call + claims call are replaced 1:1
  by a passage-claims call + a compose call, so any dcalls comes
  from continuation decisions, not the mechanism.
  H15 support-ranked stays OFF in both arms (not in the frozen
  improved config); the final combination is judged at confirmation.
  A/B launching 2026-11-13 on a re-sent Groq key (user-confirmed
  Dev-300 + per-experiment cache); per-experiment cache
  `results/cache/cache_p27_h18.sqlite` (`run.cache_path`,
  `7486fa2` also splits the cache: the shared `results/cache.sqlite`
  is untracked, one file per experiment from here).
- **H19 — extractive answering (FIRST, user direction 2026-11-11):**
  the final answer must come from supported claims only — a claims-only
  final re-read with NO context block, always on (not trigger-gated),
  replacing the other re-read triggers. Pre-registered 2026-11-11
  (this section + `openspec/changes/extractive-final-read/`): on
  Dev-100 BM25, the extractive arm raises EM >= +0.02 vs the
  improved-system baseline at <= +0.5 calls/Q AND does not raise the
  wrong-answer rate. Exploratory. **GATE FAIL 2026-11-11 (see §12):
  dEM -0.0100, dcalls +0.60, fixed 3 broke 5 on triggered rows;
  H19 NOT SUPPORTED, mechanism DROPPED, stays OFF.** The round moves
  to H18 (the full evidence-first inversion).
- H20 — compositional verification (verify the answer claim against
  the joint evidence of its supporting claims, not per-window).
- H21 — cross-encoder reranking of the pool before the reader.
- H22 — generate–critique–revise loop (critic verdict feeds back into
  generation; subsumes the re-read patches).
- H17 — calibrated abstention (candidate only, not pre-registered;
  write fully before any run touching it; only if H18–H22 leave H11
  a tie).

Order: H19 first (cheapest strong signal), then H18 (the full
inversion), then the winner combined with H20/H21. The final system
for the Phase 2.6 confirmation is whichever combination passes its
gates; the confirmation is still ONE Test-400 run vs fresh IRCoT,
judged on EM up AND wrong-answer rate down with p < 0.05. If the
architecture round fails its gates, the paper reports that straight
and leads with H6 + honest negatives. Old verdicts stay frozen
(HARKing rule); new mechanisms get new hypotheses written before the
runs. Phase 3 entry moves to the end of this round.

---

## 5. Phase 3 — New datasets (generalization)

**Goal:** show the Phase 2 system generalizes beyond HotpotQA — or find
out honestly that it does not.

**Phase boundary (this is the part that was unclear — fixed 2026-11-09):**
Phase 2 is HotpotQA ONLY (Test-400 confirmation of the tuned system vs a
fresh IRCoT, BM25, plus the H4 ablation and H1 re-run). Phase 3 is the
new datasets ONLY. Nothing from Phase 3 runs before Phase 2's verdict,
and no Phase 3 result feeds back into tuning the HotpotQA system.
- **Entry condition (amended 2026-11-11 — Phase 2.5 inserted):** Phase 2's
  pre-registered verdict is judged (§4.2 decision table), and the Phase 2.5
  improvement round runs first (§4.5) with its one Test-400 confirmation.
  The system that goes to Phase 3 is the **improved system** after that
  confirmation. (Original Phase 2 rule, now superseded by the user's
  2026-11-11 improve-first decision: **Win** → the tuned system is Phase 3's
  system. **Inconclusive** → the tuned system still goes to Phase 3 (a null
  result is a result). **Loss** → revert to v1 (EM 0.4750, significant
  vs IRCoT) for Phase 3 and report the tuning as a negative result.)
  The frozen config from the end of Phase 1 is what runs in Phase 3 —
  no changes after the freeze without a dated amendment.
- **New hypotheses first:** before touching either new dataset, write
  the Phase 3 hypotheses (same H1–H6 shape, adapted: the primary claim
  is that the tuned system beats IRCoT on the new test split; H6's
  hop-0-incomplete prediction carries over). No new data is opened
  before the hypotheses exist. (H9, the cross-dataset generalization
  hypothesis, is already written in `docs/hypotheses-current-status.md`
  on 2026-11-10; the per-dataset adaptation happens before each
  dataset is touched.)

- **Datasets (user chose BOTH, 2026-11-09):** 2WikiMultiHopQA AND MuSiQue,
  in that order — 2Wiki first (structurally closest to HotpotQA: multi-hop,
  distractor setting, comparable size — the safer comparability choice),
  then MuSiQue (harder and more compositional, multi-hop with disconnected
  reasoning — the stronger generalization claim, and the harder test). The
  paper's claim becomes "works on multi-hop QA" (2Wiki) AND "works on
  harder multi-hop QA" (MuSiQue). No third dataset beyond these two.
- **Retriever discipline (the multi-retriever comparison — NOT discarded):**
  on EACH dataset, BM25 first, then MiniLM as a second check — the
  generalization check the plan always carried (the user's rigor concern
  from 2026-11-08: dropping the multi-retriever comparison is a disclosed
  limitation, so it returns here as a frozen-system check, not as tuning).
  The HotpotQA MiniLM comparison is governed by the §4.3 MiniLM rule
  (runs only if the BM25 verdict is inconclusive); whether to run it
  regardless is an open user decision (§9).
- **Run list per dataset (in order, each an OpenSpec change when the phase
  starts; nothing runs out of order):**
  1. Dataset prep: manifests (dev/test splits), overlap check against
     HotpotQA test (zero overlap required — the audit's dataset check is the
     template), distractor corpus construction, baseline reproduction.
  2. Frozen baselines on the new dataset: Standard, IRCoT, and the Phase
     2 system, BM25 first.
  3. Head-to-head (BM25): Phase 2 system vs IRCoT on the new test split.
  4. Head-to-head (MiniLM): the same comparison on MiniLM, reported
     alongside BM25 — never pick the better one post-hoc.
  5. Error analysis on the new dataset, same script pattern as the
     Test-400 analysis.
- **Verdict per dataset (pre-registered, same shape as §4.2):** primary
  endpoint EM, paired McNemar exact two-sided, α=0.05 — Win: system EM >
  IRCoT EM AND p<0.05; Loss: system ≤ IRCoT or p≥0.05 with system ≤
  IRCoT; Inconclusive: system > IRCoT but p≥0.05. Secondaries: F1,
  calls/Q, coverage, recall, selective EM. A Win on 2Wiki does not
  predict MuSiQue — each dataset is judged on its own, and the paper
  reports both, including any split (Win on one, Loss on the other).
- **What does not happen:** no tuning on the new datasets' test splits;
  any tuning uses a dev split only, and only if the HotpotQA-tuned system
  underperforms there for a diagnosed, mechanistic reason (a new OpenSpec
  change, not a quiet tweak). No re-running Phase 2 to chase a better
  Phase 3 number.
- **Out of scope for this phase:** a third dataset beyond 2Wiki + MuSiQue.

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
- **Venue:** the user stated (2026-11-09) the venue is a Springer
  conference at Sri Sri University, Cuttack — NOT IEEE. Likely match
  found by web search: GreenAI-2027 (2nd Int. Conf. on Green AI &
  Industrial Applications, Jan 29–30 2027, Sri Sri University Cuttack;
  selected papers to Springer AISSE, Scopus-indexed) — BUT its
  full-paper deadline was 15 Oct 2026, already passed when checked
  2026-11-09. The user has NOT confirmed GreenAI-2027 is the one;
  other SSU possibility is HITA 2027 (submissions open soon, venue
  TBD — HITA 2025 was at SSU). See `docs/paper-readiness-plan.md`
  W4.4: confirm the conference (and whether a late/short-paper route
  exists) or pick another SSU Springer conference with an open
  deadline; re-verify every deadline at submission time. The
  call-reduction result (4.78 vs 8.95 calls/Q) is a genuine green-AI
  framing hook if GreenAI is the target.
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
| 1 | New dataset: 2WikiMultiHopQA or MuSiQue | The paper's claim (§5) | Decided 2026-11-09 by the user: BOTH, 2Wiki first then MuSiQue (recorded in §5; this row was stale) |
| 2 | `theta_abs`: selective answering vs max EM | The paper's goal (§3.4) | Decided 2026-11-09 by the user: selective answering (reduce hallucination first); step 4 done, theta_abs=0.50, coverage 0.790 |
| 3 | Keep step-1 re-read if Test-400 shows no gain | The pre-registered verdict (§4.2) | Decided by test, not by dev |
| 3b | Memory in the frozen Test-400 system (on or off) | Step 6 gate (§3.6): stream A/B gain or call reduction, override test passes | Decided 2026-11-10 by the step-6 gate: OFF — verdict "instrument too weak" (mem fired 1/30, floor 5/30); the frozen config uses memory.enabled: false |
| 3c | Add the report's confirmatory H1/H4 analyses to Phase 2 (H1: TA vs Standard, paired bootstrap + McNemar; H4: adaptive vs no-adaptive ablation — needs a Test-400 ablation run) | The report (Nov 4) labels E-RAG vs IRCoT exploratory; H1/H4 are confirmatory with Holm correction | Decided 2026-11-10 — YES, both join Phase 2 (under the delegated mandate, proceeding on the recommendation): H1 re-run on the tuned system + H4 Test-400 ablation + Holm across H1/H4 |
| 4 | When (and whether) to push `trueadaptive` to origin | User, each time | Open — nothing pushed so far |
| 5 | Push master `.mailmap` commit (`88f2512`) | Needs a fresh GitHub token, transiently | Open — housekeeping, not blocking |
| 6 | Paper venue | User, after results exist | User stated 2026-11-09: Springer conference at Sri Sri University, Cuttack (NOT IEEE). Specific conference unconfirmed; GreenAI-2027's full-paper deadline (15 Oct 2026) already passed when checked 2026-11-09 — see `docs/paper-readiness-plan.md` W4.4 |
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
- **No manuscript in the repo.** There is no `paper/` directory and no
  manuscript text; the Implementation Guide PDF is not in the repo. The
  hypotheses H1–H6 as stated now come from the Nov 4 report (§2.1,
  verified from the extracted text) — the earlier "inferred from code
  and repo docs" wording is superseded. If the manuscript or Guide is
  supplied, the hypothesis statement is corrected against it before
  Phase 4.
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
  `results/nli_memo.pkl` (modified by runs). Untracked:
  `configs/erag_adaptive.yaml` (old untested draft),
  `docs/audit-cache-dataset-integrity.md`, `docs/openspec-setup.md`,
  `openspec/changes/archive/2026-11-09-tune-hop2-sc-cap/`,
  `openspec/specs/hop2-sc-cap/` (step-5 archive files, staged
  differently across commits — see `git status` before any commit).

---

## 12. Experiment log (chronological — the single record of what ran and what it showed)

The traces of this project live in many places: result JSONLs in
`results/`, commits on `trueadaptive`, OpenSpec changes (archived per
step), analysis reports in `docs/`, and memory. This section is the one
file that ties them together. **Rule going forward: every run, analysis,
and decision gets an entry here the same day it happens** — date, what
ran, the config that matters, the output file, the headline numbers, the
verdict, and the commit. The JSONLs and commits are the evidence; this
log is the index. Nothing is logged from memory alone: a number appears
here only if a stored file or a commit backs it.

### 2026-11-08 — TrueAdaptive v1 built (branch `trueadaptive`, off merged 9564676)

- Spec: OpenSpec change `erag-trueadaptive` (6c671d0). Build: call-count
  tests with a mocked LLM (d5c820f), sequential SC M=1→3 ΔH<0.05 (738dd1e),
  SC gated behind the Fast Path (7d5cba4), frozen config
  `configs/erag_trueadaptive.yaml` (8a64503). Closed-book gate deferred to
  v2. Mocked fast path: 2 calls (was 5 Balanced / 7 Reference).

### 2026-11-08 — v1 Dev-100 validation (MiniLM, then BM25)

- MiniLM (ece1c0e), `results/trueadaptive/erag_trueadaptive_dev.jsonl`:
  EM 0.50, F1 0.6018, 4.91 calls/Q. Gate MET (≤6 calls, EM ≥0.50, exactly
  at the threshold).
- BM25 (ef937fc), `results/trueadaptive/erag_trueadaptive_bm25_dev.jsonl`:
  EM 0.56, F1 0.6495, 4.58 calls/Q. BM25 leads MiniLM on dev; chosen
  first for Test-400, MiniLM only if the BM25 result is inconclusive.

### 2026-11-08/09 — Audit remediation (audit: `docs/audit-adaptive-llm-calling.md`)

- Cache-write guard (7c32650), purge of 55 empty cache rows with a backup
  outside the repo (3064740), row-level retriever provenance (4040bfc),
  cache key versioned `v: 2` (011e5d2), verification script
  `scripts/verify_results.py` (10/10 PASS). Corrections: "45.4% call
  reduction" is −39.8%; Phase 5 report named the wrong model/cost rates
  (actual `openai/gpt-oss-20b`, Groq $0.10/$0.20 per 1M); Standard Dev-100
  EM is 0.4400, not 0.4200.

### 2026-11-09 — Test-400 BM25 head-to-head, TrueAdaptive v1 vs IRCoT (d69490f)

- Both fresh, frozen configs, k=3, distractor, N=400, 0 cache hits.
  TrueAdaptive (`results/trueadaptive/erag_trueadaptive_test_bm25.jsonl`,
  namespace `test_trueadaptive_v1_bm25`): **EM 0.4750, F1 0.6192, 4.78
  calls/Q**. IRCoT (`results/ircot_test_bm25.jsonl`, namespace
  `test_ircot_v1_bm25`): **EM 0.4200, F1 0.5674, 2.545 calls/Q**.
  McNemar b=38, c=16, **p=0.0043 — SIGNIFICANT**, first significant
  frozen-system E-RAG vs IRCoT Test-400 result. Also beats Balanced BM25
  (0.4450 at 8.95 calls) by +3.0 pts at −46.6% calls. Per the agreed rule,
  MiniLM Test-400 is NOT required (user has not explicitly confirmed).
  Caveat: TA file has 401 lines (resume retried 1 failed Q, stale row);
  dedupe by id keeping the last row → N=400.

### 2026-11-09 — Test-400 error analysis (ed154d7)

- Script `scripts/analyze_trueadaptive_test400.py`, report
  `docs/trueadaptive-test400-error-analysis.md`. Error budget (400):
  right 190, wrong 133, system-abstained 37, model-unknown 40.
  **Reasoning, not retrieval, is the bottleneck:** 107/133 wrong had
  recall==1.0; of those 70 had gold in trace claims (reader/graph
  bottleneck), 37 never extracted gold as a claim. Only 26 wrong were
  retrieval failures. Hops help net +28 (fixed 42, broke 14; hop-0 draft
  EM 0.4050 → final 0.4750). The 77 unknowns are two populations
  (37 system abstentions, answer_conf median 0.214; 40 reader refusals,
  answer_conf median 0.875). Call tail: 54 rows ≥7 calls = 22% of calls
  at EM 0.333. Fast-path SC gate works (86 skips, 2 calls, EM 0.547).
  Tuning order set by this analysis: (1) reader/graph, (2) claim
  extraction, (3) model-unknown prompt, (4) theta_abs by paper goal,
  (5) hop-2 SC cap, (6) closed-book gate deferred.

### 2026-11-09 — H1–H6 assessment (3468d08, H2: b9ee7ce)

- Script `scripts/analyze_hypotheses_h1_h6.py`, report
  `docs/hypotheses-h1-h6-assessment.md`, status doc
  `docs/hypotheses-current-status.md` (82c5a6e). **H1 SUPPORTED interim**
  (TA vs Standard-BM25 ΔEM +0.0725, CI [0.0350, 0.1125], p=0.00034;
  confirmatory re-run on the tuned system owed at Phase 2).
  **H2 NOT SUPPORTED** (60-pair NLI set, macro-F1 0.6825 < 0.70, narrow
  miss; contradicted recall 0.75 passed). **H3 SUPPORTED but weakened for
  TA** (AUROC on c0 0.5915 vs Reference 0.6519). **H4 dev interim
  INCONCLUSIVE** (ΔF1 +0.0304, CI includes 0; Test-400 ablation still
  owed). **H5 NOT SUPPORTED as stated, but the test is cache-confounded**
  (E5 mem arm served cache_hits == llm_calls on 30/30 rows — a replay,
  not a null; re-test is step 6). **H6 SUPPORTED strongly** (all of TA's
  gain over IRCoT concentrates where hop-0 retrieval was incomplete:
  ΔEM +0.1146, CI [0.0521, 0.1823], p=0.00094; zero gain where retrieval
  was complete). Decision recorded: complete the analyses, do not redraft
  hypotheses after seeing results (HARKing risk).

### 2026-11-09 — Step 1, reader grounding (DONE, gate PASS, mechanism kept)

- Change `tune-reader-grounding` (c3c97dc); implementation behind
  `erag.ground_final_read` (303efb5); analyzer `--reread` section
  (2b1118c); archived (5bf633b). Dev A/B (9d1d108),
  `results/trueadaptive/erag_trueadaptive_bm25_dev_reread.jsonl`: EM
  0.5600 vs 0.5600 flat, F1 0.6611 vs 0.6495, calls 4.75 vs 4.58.
  Re-read triggered 16/100, fixed 2, broke 1 (net +1) — a wash on dev;
  kept, Test-400 judges it. Confound recorded: cache-key v=2 meant the
  tuned run was effectively all-live; temp-0.0 nondeterminism flipped 8
  untouched rows, so the EM tie carries ~±3 rows of noise. Lesson:
  never assume cache replay — verify `cache_hits` before believing a
  paired comparison.

### 2026-11-09 — Step 2, claim extraction (DONE, gate 3/4, kept by user decision)

- Change `tune-claim-extraction` (0e51368); build (8c9f25e); archived
  (c062baf). Variant A built: question-grounded claims in the single
  extraction call (zero new LLM calls), each claim with a `source` field
  (`draft`/`question`), `max_claims` 5→8. Dev A/B,
  `results/trueadaptive/erag_trueadaptive_bm25_dev_claims.jsonl`: EM
  0.5400 vs step-1 tuned 0.5600 (−2 rows, inside the ±3-row noise band),
  F1 0.6391, calls 4.65/Q. Mechanism: gold-in-claims among full-recall
  wrong rows 0.524 vs 0.333 baseline (PASS); answer-bearing
  question-sourced claims 6/100 (gate ≤10% PASS). Gate FAILS on EM only
  (3/4); user chose to proceed. Tuned value: `max_claims: 8`. Cache note:
  2.53 cache_hits/Q — namespace reused, only extraction calls were live.

### 2026-11-09 — Step 3, model-unknown prompt (DONE, gate FAILED, mechanism DROPPED)

- Change `tune-unknown-prompt` (0d6942b); build + gate (c0b5e67);
  archived (afc10f1). Two variants behind `erag.unknown_prompt`:
  best_guess (`results/trueadaptive/erag_trueadaptive_bm25_dev_unknown_a.jsonl`)
  unknowns 6/100 (needed ≤4 — FAIL), EM 0.5500, 4.76 calls/Q;
  cite_first (`..._unknown_b.jsonl`) unknowns 5/100 (FAIL), EM 0.5600,
  4.48 calls/Q. Both 3/4. Per the pre-registered rule the mechanism was
  DROPPED; `unknown_prompt` stays `"base"` in the frozen tuned config.
  The 40 Test-400 model-unknown rows remain unrecovered.

### 2026-11-09 — Step 4, theta_abs (DONE, gate PASS on the pre-registered counterfactual)

- Change `tune-theta-abs` (drafted in db7b598); A.1 analyzer `--theta`
  section + 9 tests (5738181, fast suite 69 passed; reproduces all
  verification numbers exactly); gate verdict (4701ac3); archived
  (78df3cd). Live A/Bs ran (100/100, 0 failed each,
  `results/trueadaptive/erag_trueadaptive_bm25_dev_theta_a.jsonl` /
  `_b.jsonl`) but the pre-registered cache tripwire FIRED (live calls/Q
  0.04 / 0.02 — ~99% replays, because the threshold changes no prompt
  and no call); both files DISCARDED as live evidence per the rule.
  User decision 2026-11-09: accept the pre-registered counterfactual as
  the evidence (dated amendment in the change's design.md — the
  tripwire's premise is false for threshold-only steps; the numbers were
  fixed before the runs, so nothing is cherry-picked). Gate on the
  counterfactual: both candidates PASS all four measures (selective EM
  0.6456 > 0.6353; wrong 0.3544 < 0.3647; EM 0.5100 ≥ 0.51, exactly at
  the bound; calls 4.65/4.64 within 0.2 of 4.65); identical wrong-rate
  falls → tie rule selects candidate A, **theta_abs = 0.50**, coverage
  0.790. Margins are 1 row, inside the ±3-row dev noise band — the gate
  is a smoke test and Test-400 is the judge. Step-5 baseline is now the
  post-step-4 tuned dev (theta_a file): EM 0.5100, 4.65 calls/Q.

### Housekeeping (same period)

- `.mailmap` fix for Manoj Adapakala's authorship (88f2512, master, 1
  commit ahead of origin, unpushed). Branch `trueadaptive` 8 commits
  ahead of origin (db7b598, 5738181, 4701ac3, 78df3cd, 0ac6d99,
  3da932b, 5c01ede, e5da900), unpushed — both need a fresh GitHub
  token, transient only. Nothing pushed to ManojAdapakala/ERag, ever
  (push URL `no_push`).

### 2026-11-09 — E-RAG Retrospective Changelog created

- Document `docs/retrospective-changelog.md` (1,341 lines): a retrospective
  reconstruction of the project's technical history from repository
  evidence only, in the user's template (timeline, change entries, repair
  sequence, current state, evidence map, claims discipline, paper-facing
  narrative). 33 dated change entries plus 4 template entries marked
  `not recoverable from repository`; 24 evidence-map rows. Headline
  finding: the template's §3 repair sequence (Batch 2A, provenance
  safeguards, conflict-policy characterization, contradiction veto) does
  NOT exist in this repository — the three cited commits are bad objects,
  the tag `checkpoint-pre-audit3` does not exist (the commit `6aced98`
  does), the test files and `src/provenance.py` are missing, and no
  commit ever introduced the veto identifiers; the draft records the
  actual repair sequence (the audit remediation) instead. Current test
  status measured for the draft and re-verified by the parent: full suite
  87 passed, 1 failed (the known pre-existing retry-test mismatch),
  0 xfailed; `scripts/verify_results.py` 10/10 PASS. Rounding correction
  made during verification: IRCoT Test-400 exact mean is 1018/400 =
  2.545 calls/Q; the plan's 2.55 (half-up) and Python's 2.54 were both
  roundings of the same value — both documents now state 2.545.

### 2026-11-09 — Steps 5 and 6 measurement builds (5c01ede, e5da900)

- Step 5 A-build (commit 5c01ede): mocked cap test + `--hopcap`
  section 14; verified numbers in §3.5. Step 6 A/B build (commit
  e5da900): `--position` section + mem row fields + 30-row sidecar;
  verified numbers in §3.6. Raw-file fetch failed a third time — the
  N=30 fallback stands, no Parquet reconstruction, no invented
  questions. Both live A/Bs await Groq keys; step 6's also awaits the
  step-5 verdict.

### 2026-11-09 — Step 5 A/B + verdict SUPERSEDED; step 7 drafted (7a3598c)

- Step 5 A/B finished 100/100, 0 failed: EM 0.5100 (unchanged),
  calls/Q 4.49 vs 4.65 (−0.16), live calls/Q 0.06 vs 0.04 (+0.02),
  hop-2 rows 10→0, hop-2 calls 78→0. Gate as written fails on the
  live-calls measure only (6 vs 4 live calls — replay noise). The
  user chose the learned continuation policy instead of deciding
  the gate: step 5 closes SUPERSEDED (not passed, not failed),
  archived as `2026-11-09-tune-hop2-sc-cap`; `max_hops` stays 2 as
  a ceiling. Step 7 change `learned-continuation-policy` drafted
  (proposal/design/tasks/spec; validate 9 passed, 0 failed) — a
  learned draft-correctness model (logistic regression on hop-0
  features, dev only) replacing the fixed hop-0 continuation
  decision.

### 2026-11-09 — Step 7 Phase A + Gate A verdict PASS (marginal)

- Phase A built by subagent, verified by the parent by independent
  re-run (extraction + training scripts re-executed, composition
  recomputed from the stored traces, fast suite run, `--policy`
  section run on the baseline). Extraction reproduces every
  verification number exactly (hop-0 EM 0.4800, final 0.5100, fixed
  6, broke 3, hops {0:45, 1:45, 2:10}, abstained 15, draft-unknown
  6, 4.65 calls/Q; accounting violations 0 — invariant exact).
  Oracle ceiling: included 83, excluded 17, EM 0.6506, calls/Q
  4.61 (saves only 0.04/Q — the static fast path already stops on
  28 of the 48 correct drafts). LR, τ = 0.30, 5-fold CV, OOF only:
  simulated EM 0.5000, F1 0.5837, calls/Q 3.98 (saved +0.67),
  coverage 0.766, STOP 70 / CONTINUE 24, excluded 6/100 (6.0%).
  OOF AUROC 0.6546 (c0 alone 0.484). **Gate A: PASS, exactly at
  the floor** (0.5000 = 47/94; one fewer correct row fails it).
  Composition (parent): the policy STOPs on 4 of the 6 fix-rows
  (loses 4 fixes) and saves 1 of 3 breaks; F1 and coverage dip
  below baseline. No Test-400 data in training/features/τ. Fast
  suite 126 passed, 1 failed (known retry mismatch). `--policy`
  analyzer §15 reproduces the theta_a baseline exactly (EM 0.5100,
  4.65 calls/Q, all 100 rows unknown). Files: scripts
  `extract_continuation_training.py`, `train_continuation_policy.py`,
  `data/continuation_training_dev.jsonl`,
  `data/continuation_simulation_dev.json`, tests
  `test_continuation_policy.py` (8), `test_analyzer_policy.py`
  (7), analyzer §15. **Final-model training + artifact: the user
  chose to proceed — see the retrain entry below (the tau = 0.30
  artifact from commit d0fb457 was superseded by the retrain).**

### 2026-11-09 — Step 7: user chose "Wire it in"; final model trained, then RETRAINED (Gate A re-check PASS with margin)

- User chose to wire it in (options-widget tap). Final model trained
  by the parent (`--write-artifact`, commit `d0fb457`): artifact
  `configs/continuation_policy_dev.json`, tau = 0.30, OOF AUROC 0.6546,
  verified to 2.2e-16; design.md artifact-format section added.
- **BLOCKER found by the B.1 subagent before writing any code,
  verified independently by the parent:** `draft_unknown` was trained
  on the row `draft` field — the FINAL draft (last hop, possibly
  re-read-replaced, `erag.py:354`), not the hop-0 draft. The two
  definitions diverge on 16/100 dev rows (15 hop-0-unknown to final
  real answer, 1 real to unknown, row 5abd44d9); hop-0-unknown count
  is 20 vs row-draft-unknown 6; the other 11 features agree exactly.
  `draft_unknown` carries the largest coefficient (-0.767), so the
  original Gate A pass rested on a definitionally wrong feature.
  B.1 stopped before writing any code; no files changed.
- **User chose the retrain (options-widget tap 2026-11-09).**
  Re-extraction with the hop-0 definition + re-training, same
  pre-registered gate (commit `7872b24`): extraction reproduces all
  verification numbers + hop0_draft_unknown 20; LR, tau = 0.05,
  simulated EM 0.5152, F1 0.6238, calls/Q 3.92 (saved +0.73),
  coverage 0.869, STOP 81 / CONTINUE 18, excluded 1/100 (1.0%);
  OOF AUROC 0.6775; composition STOP on 2/6 fix-rows, 2/3 broke
  rows saved; tau curve smooth (tau=0.10: EM 0.5204, 3.97 calls).
  **Gate A re-check: PASS with margin.** New artifact written
  (tau = 0.05, `draft_unknown` coef -1.489), verified to 2.2e-16;
  the tau = 0.30 artifact is SUPERSEDED and must not be used for
  wiring. Suite 127 passed, 1 failed (known retry mismatch). B.1
  re-spawned with the corrected brief (hop-0 definition + CONTINUE
  on a fast-path row picks the weakest claim; policy governs at hop
  0 under `no_conf`); C.1 live A/B awaits B.1 + a Groq key. The
  retrain is a methods disclosure for the paper, not a footnote.

- **B.1 DONE 2026-11-09, committed `a0eb216`, verified by the parent
  by independent re-read of the module + diff, full-suite re-run,
  genuineness check (stash wiring → 5 behavior tests fail), and a
  probability cross-check (module matches the fitted pipeline to
  1.1e-16 on all 100 dev rows; decisions STOP 81 / CONTINUE 19).
  12 new mocked tests; suite 139 passed, 1 failed (known retry
  mismatch). C.1 live A/B awaits a Groq key.

### 2026-11-09 — Step 7 C.1 live A/B + Gate B PASS; change closed (4c9576f)

- Live Dev-100 A/B (detached, ~35 s, mostly cache replays; 100/100,
  0 failed; output
  `results/trueadaptive/erag_trueadaptive_bm25_dev_policy.jsonl`):
  EM 0.5000, F1 0.6114, calls/Q 4.07 (live 0.11, recorded not
  gated), coverage 0.83, selective EM 0.6024, recall 0.765,
  retrievals 1.32/Q. Baseline theta_a: EM 0.5100, 4.65 calls/Q.
  Agreement vs retrained simulation (EM 0.5152, 3.92/Q): dEM
  −0.0152, dCalls/Q +0.15. STOP 81 (EM 0.5679) / CONTINUE 19 (EM
  0.2105); hops {0:82, 1:15, 2:3}. **Gate B: PASS** — live EM
  exactly at the floor, calls/Q below 4.65, agreement within the
  pre-registered ±0.02 / ±0.2, N=100 deduped, 0 failed. The policy
  ENTERS the frozen Test-400 system. Honest reading: live EM is 1
  row below baseline; Test-400 is the real judge.
- **Analyzer casing bug found during C.1 and fixed the same day:**
  §15 compared `policy_decision` against uppercase STOP/CONTINUE
  while the runner writes lowercase per the design contract — the
  first analysis reported 0/0/100 unknown on a file whose rows all
  carry the field. Fixed by case-normalizing; tests switched to the
  lowercase contract + a case-insensitivity regression test; full
  suite 140 passed, 1 failed (known retry mismatch). The fixed §15
  reproduces every C.1 number exactly (independent recompute
  agrees).
- Change archived (`openspec archive learned-continuation-policy
  -y` → `openspec/changes/archive/2026-11-09-learned-continuation-policy/`,
  spec → `openspec/specs/learned-continuation/spec.md`); validate
  --all 9 passed, 0 failed. Step 7 CLOSED. Remaining Phase 1 work:
  step 6 stream A/B (runs on the post-step-7 tuned system, needs a
  Groq key), hypothesis hygiene, freeze, push.

### 2026-11-09 — Paper-readiness audit (docs/paper-readiness-plan.md)

- The user asked for a rigorous audit of the current plan to make the
  paper ready. Verdict: the evidence core is real (v1 Test-400
  significant; H1/H6 supported), but Phase 1 is unfinished, Phase 2
  and Phase 3 have not run, no manuscript exists, no venue is
  confirmed, and the plan documents had drifted from reality (8
  findings F1-F8; F1-F4 fixed in the same commit as the plan doc).
  The plan lists the ordered work (W0-W5) and the seven asks from
  the user (Groq key, GitHub token, dataset choice, missing papers,
  venue confirmation, hypothesis hygiene, MiniLM confirmation).

### 2026-11-10 — Step 6 stream A/B (C.1–D.1, gate verdict: instrument too weak)

- C.1 ran on the post-step-7 tuned system (three arms, fresh
  namespaces, N=30 fallback after the raw-file fetch failed a third
  time): nomem EM 0.6000, F1 0.6614, 4.73 calls/Q; mem EM 0.6667,
  F1 0.7354, 4.60 calls/Q; planted EM 0.6333, F1 0.7284, 4.67
  calls/Q — all N=30 deduped, 0 failed. C.2 tripwire PASSES (live
  calls/Q ≈ llm_calls/Q; cache_hits/Q 0.07 nomem, 0.00 mem, 0.00
  planted). Outputs:
  `results/trueadaptive/stream_tuned_{nomem,mem,planted}_v1.jsonl`.
- D.1 gate: (1) FAILS — mem fired on 1/30 (floor ≥5/30); (2) would
  pass (ΔEM +0.0667, Δcalls/Q −0.13, fired-row paired difference
  0/0) but is unattributable — the single fired row (5abbb065, Li
  Yitong passage) changed nothing, so the +2 EM rows are noise
  inside the usual ±3-row band; (3) override 1/1 retrieved (Becker
  purged); the checker's 2 false-claim flags are substring false
  positives (gold-correct 'German' and 'private' on rows where
  nothing was retrieved). **Verdict: "instrument too weak" — memory
  stays OFF, H5 stays NOT SUPPORTED (dated note in the status doc),
  Phase 1 is now complete (all steps 1–7 closed).**
- Two interruptions on the way: the VM restarted overnight (first
  launch died at nomem 24/30; transient keys lost and re-sent by the
  user), and the first resume used a doubled `--set` (overwrites —
  ran the DEV split, wrote 2 dev rows into the stream file; killed,
  rows removed, file restored to 24, relaunched with one `--set`).
  Lesson recorded in `AGENTS.md`: always check the progress bar's
  split/count before walking away from a launch.
- Same day: hypothesis hygiene committed (`10cbfef`); D2 ablations +
  H7 written (`acb1585`); MiniLM namespaces (`9f5321c`); H8–H11
  pre-registered (`bdf3e32`); Adaptive-RAG Gate AR-1 PASSED
  (held-out 0.9318, routes A0/B45/C55) and wiring C.1–C.3 committed
  (`bae3018`, `b033602`, 15 tests pass). Branch 35 commits ahead of
  origin, unpushed. Remaining: freeze, push, D.1 sanity run, Phase 2.

### 2026-11-11 — Phase 2 verdict: INCONCLUSIVE + rest-of-Phase-2 chain complete

**§4.2 verdict (pre-registered): INCONCLUSIVE.** Tuned TrueAdaptive
(frozen `configs/erag_trueadaptive_tuned.yaml`, namespace
`test_tuned_v1_bm25`) EM 0.4500, F1 0.5905, 4.13 calls/Q vs fresh
IRCoT v2 (namespace `test_ircot_v2_bm25`) EM 0.4225, F1 0.5643,
2.48 calls/Q; dEM +0.0275, 95% CI [−0.0075, +0.0625], McNemar b=31,
c=20, p=0.1608 (N=400 deduped, 0 failed, cache_hits/Q 0.020 tuned /
0.000 IRCoT). Per the decision table: report "no significant gain",
Phase 3 proceeds with the TUNED system, no further tuning. Tuned vs
v1 (reported, not gated): EM 0.4500 vs 0.4750, dEM −0.0250, p=0.2678
— tuning cut calls (4.13 vs 4.78) but did not improve Test-400
accuracy. Files:
`results/trueadaptive/erag_trueadaptive_tuned_test.jsonl` (401 lines,
1 resume-retry duplicate),
`results/ircot_test_v2_bm25.jsonl`; verdict script
`scripts/phase2_verdict.py`; analyzer sections 1–9;
`verify_results.py` 10/10.
- **H1 confirmatory re-run: SUPPORTED.** Tuned vs Standard-BM25 dEM
  +0.0475, CI [+0.0150, +0.0800], McNemar b=34, c=15, p=0.0094.
  Holm across H1/H4: adjusted p 0.0188 — H1 survives.
- **H4 (Test-400 ablation): NOT SUPPORTED.** No-adaptive ablation EM
  0.4350, F1 0.5781, 2.28 calls/Q (N=400, 0 failed, cache_hits/Q
  0.000;
  `results/trueadaptive/erag_ablate_no_adaptive_test.jsonl`). dEM
  +0.0150, CI [−0.0150, +0.0450], McNemar b=21, c=15, p=0.4050;
  dF1 +0.0124, CI [−0.0190, +0.0439] (includes 0); cost/correct
  9.18 vs 5.25 — both legs fail. Holm: H4 adjusted p 0.405. The
  paper drops adaptive-beats-no-adaptive; keeps E-RAG-beats-Standard.
- **H10: NOT SUPPORTED on the IRCoT leg.** Calls/correct: tuned
  9.18, IRCoT v2 5.88, Balanced 20.11.
- **H11: tie (directional).** Wrong-answer rate tuned 0.4495
  (147/327) vs IRCoT 0.4566 (142/311) at better coverage (0.818 vs
  0.777). The criterion's two legs are technically met but the gap
  (0.7pts, ~2 questions) is inside noise and the criterion carries
  no significance test — reported as a tie, not a win.
- **D2 (a) SC-off: cost win, not accuracy win.** SC-fixed-5 EM
  0.4425, F1 0.5748, 6.00 calls/Q vs tuned 0.4500, 4.13 calls/Q;
  dEM +0.0075, CI [−0.0125, +0.0275], p=0.6072. Sequential SC saves
  ~31% of calls at the same accuracy.
- **D2 (b) Fast-Path pair (SC eager in both arms):** control (fast
  path on) EM 0.4675, F1 0.5939, 4.83 calls/Q vs off EM 0.4500,
  F1 0.5802, 4.86 calls/Q; dEM +0.0175, CI [−0.0050, +0.0425],
  p=0.2100 — directional only, inside noise. **H7 NOT SUPPORTED:**
  neither component shows a significant accuracy contribution (SC's
  is cost, FP's is directional).
- **Observation (not pre-registered):** FP-control vs tuned (the
  SC-deferral gate): EM 0.4675 vs 0.4500, dEM +0.0175, CI [−0.0100,
  +0.0450], p=0.2810, at 4.83 vs 4.13 calls/Q — eager SC is +1.75pts
  at +0.70 calls, also inside noise. Recorded as a post-hoc
  observation to test later, not a verdict.
- **MiniLM second check (BM25 verdict stands):** tuned EM 0.4450,
  F1 0.5750, 4.08 calls/Q vs IRCoT EM 0.4250, F1 0.5597, 2.54
  calls/Q; dEM +0.0200, CI [−0.0100, +0.0500], p=0.2559 — same
  direction as BM25, also inconclusive. Files:
  `results/trueadaptive/erag_trueadaptive_tuned_test_minilm.jsonl`,
  `results/ircot_test_v2_minilm.jsonl`.
- **E.1 Adaptive-RAG Test-400 (Gate AR-2 PASS: N=400, 0 failed,
  fresh namespace):** EM 0.4275, F1 0.5572, 1.68 calls/Q, coverage
  0.760; routes B 210 / C 190 (A 0, as predicted); route B EM 0.3714
  at 1.00 call/Q, route C EM 0.4895 at 2.44 calls/Q. **H8 NOT
  SUPPORTED:** tuned beats AR on EM (0.4500 vs 0.4275, dEM +0.0225,
  CI [−0.0100, +0.0550], p=0.2327 — not significant) AND uses more
  calls (4.13 vs 1.68), so the equal-or-fewer-calls leg fails
  outright. AR vs IRCoT: 0.4275 vs 0.4225, p=0.8238 — a tie at fewer
  calls. File: `results/adaptive_rag/adaptive_rag_test_bm25.jsonl`;
  analyzer section 16.
- **Interruptions:** the rest-chain was killed by repeated VM
  restarts (H4 + SC-off finished; FP-control failed at startup on an
  HF Hub outage, FP-off wrote 0 rows, MiniLM + E.1 unstarted).
  Recovery chain (`~/workspace/phase2_recovery_chain.sh`,
  HF_HUB_OFFLINE=1 + skip-if-complete) finished all 5 remaining
  runs; a further restart killed MINILM-TUNED at 201/400 and the
  relaunch resumed at 202/400. Groq ran slow in the recovery window
  (~10s/it vs ~2s/it). No rows lost; all namespaces fresh;
  cache_hits/Q ≈ 0 throughout.

### 2026-11-11 — Phase 2.5 decided + diagnosis (user: improve first, then Phase 3)

User challenged the plan: if nothing is improving, why run the same
system on a new dataset? Decision: improve first. Diagnosis from stored
Test-400 rows only (`scripts/diagnose_phase25.py`,
`docs/phase25-improvement-diagnosis.md`): 53 gold-in-claims wrong rows,
34/53 with the final answer inside a WRONG supported claim, re-read
never fired on 41/53; 33 never-claimed rows with hop-0 recall 1.0 on
27/33; FP-control 19 gains / 12 losses, net +7, churning the
answer/abstain boundary both ways. Pre-registered before any new run:
H12 contested-claim resolution, H13 second extraction pass, H14 eager
SC (dev replication, circularity noted). theta_abs explicitly NOT a
lever. Dated clarification: the pre-registered T1 trigger covers 2/53
target rows on stored data — redefined to T2 (covers 16/53, 36%
false-trigger rate). Committed ad97293.

### 2026-11-11 — Phase 2.5 H12 A/B: GATE PASS (dev smoke test)

OpenSpec change `improve-contested-claims` (validate 11/11);
implementation behind `erag.contested_resolution` (default false), 9
new tests, full suite 168 passed / 1 known pre-existing failure.
Committed b1c30e4. Dev-100 BM25 A/B, fresh namespaces, both arms
re-run fresh (chain `~/workspace/phase25_h12_chain.sh`, ~15 min):
baseline EM 0.5200 / F1 0.6430 at 3.99 calls/Q vs contested EM 0.5500 /
F1 0.6397 at 4.38 calls/Q — dEM +0.0300, 95% CI [−0.02, +0.08],
McNemar b=5, c=2, p=0.4531 (not significant on N=100, expected);
dF1 −0.0033; +0.39 calls/Q (inside the +0.5 budget). Trigger fired
25/100; fixed 3, broke 1, net +2 on triggered rows (untriggered +1 is
temp-0.0 noise). Cache_hits/Q 0.00 both arms (all live). Gate PASSES
on all three legs; H12 enters the improved system. Baseline is 2 rows
above the step-7 Gate B file (0.5200 vs 0.5000) — noise/drift,
controlled by the paired fresh baseline. Files:
`results/trueadaptive/erag_p25_h12_{base,contested}_dev.jsonl`.

### 2026-11-11 — Phase 2.5 H13 A/B: GATE FAIL, MECHANISM DROPPED (dev smoke test)

OpenSpec change `improve-extraction-recall` (validate 12/12);
implementation behind `erag.second_extraction` (default false):
unconditional second extraction pass over the hop-0 pool, merged
claims, 8 new tests, full suite 176 passed / 1 known pre-existing
failure. Committed 8f215e0. Dev-100 BM25 A/B, fresh namespaces, both
arms re-run fresh on the H12-improved system (chain
`~/workspace/phase25_h13_chain.sh`, ~25 min, both arms rc=0):
baseline (tuned + contested) EM 0.5400 / F1 0.6400 at 4.35 calls/Q
vs second-pass EM 0.5600 / F1 0.6656 at 5.95 calls/Q — dEM +0.0200,
95% CI [−0.03, +0.08], McNemar b=3, c=5, p=0.7266 (not significant
on N=100, expected); dF1 +0.0256; dcalls +1.60, 95% CI [+1.33,
+1.88]. Gold-in-claims rate among full-recall wrong rows FELL:
0.625 (10/16) → 0.533 (8/15) — independently re-checked with the
repo `normalize_answer`, same counts. Gate FAILS on two of three
legs: rate did not rise, and calls rose +1.60, above the +1.0
guardrail (whole CI above 1.0). EM did not fall, but that leg alone
does not pass the gate. The pass fires heavily (second_pass_added
median 4.0, mean 3.88, only 10/100 rows added 0) yet adds the wrong
claims: it does not surface the gold sentence the first pass
skipped. Finding worth recording: of the 5 gained rows, 4 were
base-'unknown' → answered correctly — the pass un-blocks reader
refusals more than it fixes claim selection — but it also flipped 3
previously-correct rows to 'unknown', so net +2 EM is churn inside
noise. Cache_hits/Q 0.00 both arms (all live). H13 is NOT
SUPPORTED; the mechanism is DROPPED and stays OFF; the improved
system remains tuned + contested (H12 only). No further tuning on
dev for this mechanism. Files:
`results/trueadaptive/erag_p25_h13_{base,second}_dev.jsonl`;
verdict `scripts/phase25_h13_verdict.py`.

### 2026-11-11 — Phase 2.5 H14 A/B: GATE PASS, MECHANISM ENTERS THE IMPROVED SYSTEM (dev smoke test)

OpenSpec change `eager-sc-replication` (validate 13/13); config-only,
no code: `erag.gate_sc_behind_fast_path=false` on the post-H13
improved system (tuned + contested; NO second extraction — H13
failed). Dev-100 BM25 A/B, fresh namespaces, both arms re-run fresh
(chain `~/workspace/phase25_h14_chain.sh`, ~12 min, both arms rc=0):
baseline (tuned + contested) EM 0.5300 / F1 0.6488 at 4.30 calls/Q
vs eager EM 0.5400 / F1 0.6380 at 5.11 calls/Q — dEM +0.0100,
95% CI [−0.03, +0.05], McNemar b=2, c=3, p=1.0 (not significant on
N=100, expected — the gate is directional, dEM > 0); dF1 −0.0108,
95% CI [−0.056, +0.0345]; dcalls +0.81, 95% CI [+0.55, +1.08].
Gate PASSES on its pre-registered terms (dEM > 0 AND dcalls ≤ +1.0
on the point estimate). Honest caveat recorded: the cost CI
straddles the +1.0 guardrail (upper 1.08), so the +0.81 is not a
tightly-bounded cost win — the mechanism costs roughly +0.8 calls/Q
for +1 noisy EM row. Cache_hits/Q 0.00 both arms (all live). The
direction replicates the Test-400 FP-control finding on dev
(0.4675 vs 0.4500, +0.0175) — smaller here (+0.0100) and likewise
inside noise, which is consistent with the circularity note: dev
was a replication check, not a fresh discovery. H14 is a GATE PASS
(dev smoke test); eager SC enters the improved system. Phase 2.5
closes with the improved system = tuned + contested (H12) + eager
SC (H14); second extraction stays OFF (H13). Files:
`results/trueadaptive/erag_p25_h14_{base,eager}_dev.jsonl`;
verdict `scripts/phase25_h14_verdict.py`.

Note on the baseline: fresh baseline EM 0.5300 vs H13 baseline 0.5400
vs H12 contested arm 0.5500 — ±2 rows of temp-0.0 noise between fresh
runs, controlled by the paired fresh baseline.

### 2026-11-11 - Phase 2.6 H16 threshold sweep: NOT SUPPORTED on the eval leg, thresholds stay 0.5/0.5 (offline, no live calls)

OpenSpec change `tune-verifier-thresholds` (validate 15/15 at creation);
sweep script `scripts/sweep_nli_thresholds.py` (committed `d02b97d`).
Eval built from stored traces only: 486 claims from the H14-baseline
Dev-100 file (`results/trueadaptive/erag_p25_h14_base_dev.jsonl`),
passages reconstructed from the dev manifest, proxy labels by
gold-supporting-fact containment (32 proxy-supported / 454
not-supported - the proxy UNDER-labels support, so supported recall is
a lower bound and precision is a lower bound; the bar is harder on
this eval than on clean labels, which is why the 60-pair H2 set
arbitrates). Split: first 70 rows selection, last 30 held out. Grid:
theta_s {0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60} x theta_c {0.40,
0.50, 0.60, 0.70} = 28 combos, each via the exact production call
`nli.verify(text, passages, theta_s, theta_c, pre_filter=True)`.
Sweep ran offline 2026-11-11 (~4 min, session proc_e3cbdf89e9e4, exit
0); output `results/nli_threshold_sweep.json`. GATE: NO pair clears
binary macro-F1 >= 0.70 AND supported recall >= 0.70 on held-out
claims (clearing list empty). Best on selection: theta_s=0.6,
theta_c=0.4 - sel macro-F1 0.2746, held macro-F1 0.2901, held
supRec 1.0000. At the production point (0.5/0.5): sel macro-F1
0.2674, held macro-F1 0.2857, sel supRec 0.8333, held supRec 1.0000,
supported precision 0.081/0.068, pred-supported fraction 0.76/0.73.
The surface is FLAT: held macro-F1 moves 0.2768 -> 0.2901 across
the whole theta_s range, and held supRec is 1.0 at EVERY grid
point - lowering theta_s gains no supported recall. The 60-pair
check (reported alongside, never used for selection): at 0.5/0.5
macro-F1 0.6376, supported recall 0.40, contradicted recall 0.80;
best grid point (0.55-0.60/0.4) macro-F1 0.6532, contradicted
recall 0.85 - still below the 0.70 bar, and below H2's 0.6825.
Method note: H2's run used pre_filter=False (0.6825, supRec 0.60);
the sweep uses pre_filter=True, the tuned config's production
setting. Pre-filtering costs supported recall on the labeled pairs
(0.60 -> 0.40) - the pre-filter, not the thresholds, is part of the
verifier's conservatism. CONCLUSION: the thresholds are NOT the
lever. The verifier's errors sit in the NLI model's judgment and
the pre-filter, not the cutoffs; tuning theta_s/theta_c cannot fix
H2. **H16 NOT SUPPORTED on the eval leg; thresholds stay 0.5/0.5;
no Dev-100 A/B runs.** The remaining Phase 2.6 levers are H15
(support-ranked re-read, A/B running) and the H17 candidate
(calibrated abstention, not yet pre-registered).

### 2026-11-11 — Phase 2.5 Test-400 confirmation: INCONCLUSIVE (improved vs fresh IRCoT v3)

Chain `~/workspace/phase26_confirmation_chain.sh` (session
proc_9d5f72e58336, exit 0; both arms rc=0), on the send-9 Groq key.
Improved system = frozen `configs/erag_trueadaptive_improved.yaml`
(tuned + contested H12 + eager SC H14; second extraction OFF).
Namespace `test_improved_v1_bm25`, output
`results/trueadaptive/erag_trueadaptive_improved_test.jsonl`; fresh
IRCoT v3 namespace `test_ircot_v3_bm25`, output
`results/ircot_test_v3_bm25.jsonl`. Both files N=400 deduped, 0
failed, cache_hits/Q 0.00 (all live, fresh namespaces). Verdict by
`scripts/phase26_confirmation_verdict.py` (§4.2 shape + H11/H10):
**improved EM 0.4600, F1 0.5893, 5.08 calls/Q, wrong-answer rate
138/322 = 0.4286, calls/correct 11.04; IRCoT v3 EM 0.4350, F1 0.5697,
2.52 calls/Q, wrong rate 136/310 = 0.4387, calls/correct 5.78; dEM
+0.0250, 95% CI [-0.0075, +0.0575], McNemar b=28, c=18, p=0.1839
→ INCONCLUSIVE** (improved > IRCoT but p>=0.05). The Phase 2.5
improvement round bought +0.0100 EM over the tuned system (0.4500)
on Test-400 — inside noise — and the improved system is still below
v1 (0.4750). Wrong-answer rate is down 1.0pt vs IRCoT (0.4286 vs
0.4387) but the win bar needs p<0.05 too, so it is not a win. Cost
vs IRCoT is still adverse: 5.08 vs 2.52 calls/Q, 11.04 vs 5.78
calls/correct. Note: IRCoT itself drifted up across days (v1 0.4200,
v2 0.4225, v3 0.4350) — same-window paired comparisons are
protected, but the drift is a reminder that cross-day absolute
numbers carry model-drift risk. The improved system enters Phase 3
only after the Phase 2.6/2.7 rounds judge it; the next step is the
H15 verdict, then the final Test-400 confirmation.

### 2026-11-11 — Phase 2.6 H15 support-ranked final re-read: GATE PASS (dev smoke test)

OpenSpec change `improve-support-ranked-reread` (validate 14/14 at
creation); implementation behind `erag.support_ranked_reread`
(default false, top_k 3), 10 new tests. When the final draft is not
backed by the top-3 supported claims (by eff), a re-read grounded
ONLY on those top-3 claims (plus the context block) chooses the
answer. Dev-100 BM25 A/B, fresh namespaces, both arms re-run fresh
(chain `~/workspace/phase26_h15_chain.sh`, session proc_9d5f72e58336,
exit 0, both arms rc=0): baseline (frozen improved system) EM 0.5400
/ F1 0.6422 at 5.02 calls/Q vs ranked EM 0.5600 / F1 0.6400 at 5.21
calls/Q — dEM +0.0200, 95% CI [-0.05, +0.09], McNemar b=5, c=7,
p=0.7744 (not significant on N=100, expected); dF1 -0.0022; dcalls
+0.19, 95% CI [+0.01, +0.37]. Trigger fired 9/100 (lower than the
24/53 target-row rate predicted from the tuned Test-400 diagnosis —
the dev baseline is the improved system, not the tuned one); on
triggered rows fixed 3, broke 0. Gate PASSES on all three legs (dEM
>= +0.02 exactly at the bar, dcalls <= +0.5, fixes > broke).
**H15 enters the system.** Honest caveat: the +0.02 gain is exactly
at the gate bar and only 3 of the 7 net gained rows were on
triggered rows (the other 4 are temp-0.0 noise, as in the H12 A/B);
the mechanism is real but small on dev. Cache_hits/Q 0.00 both arms
(all live).

### 2026-11-11 — Phase 2.7 H19 extractive final read: GATE FAIL, MECHANISM DROPPED (dev smoke test)

OpenSpec change `extractive-final-read` (validate 16/16);
implementation behind `erag.extractive_final_read` (default false),
6 new tests. The final read is claims-only: the reader sees the
supported claims by eff desc and NO context block, always on when
supported claims exist, replacing the unknown/disagree/contested/
support-ranked triggers for that row; row field `extractive` only
when the flag is on; flag-off byte-identical. Dev-100 BM25 A/B,
fresh namespaces, both arms re-run fresh (chain
`~/workspace/phase26_h19_chain.sh`, session proc_7b7d222165d8, exit
0, ~13 min, both arms rc=0): baseline (frozen improved system) EM
0.5300 / F1 0.6256 at 5.05 calls/Q vs extractive EM 0.5200 / F1
0.6146 at 5.65 calls/Q — dEM -0.0100, 95% CI [-0.07, +0.05],
McNemar b=5, c=4, p=1.0; dF1 -0.0110; dcalls +0.60. Trigger fired
96/100; fixed 3, broke 5 on triggered rows. Wrong-answer rate
26/78 = 0.3333 vs 27/80 = 0.3375 (down 0.4pts — the only leg that
passes, and barely). Gate FAILS on two of three legs (dEM < +0.02,
dcalls > +0.5). **H19 NOT SUPPORTED; extractive mechanism DROPPED,
stays OFF.** Reading: the claims-only restriction churns the answer
rather than fixing it — the reader still composes a short answer
from claim sentences, and when the gold claim is not in the
supported set the re-read picks a wrong supported claim instead.
The supported set is the bottleneck (as H16 showed for the
verifier), not the reader's access to context. The round moves to
H18 (the full evidence-first inversion). Baseline calls/Q 5.05 here
vs 4.30 in the H14 baseline — SC sample counts are stochastic
(temp-0.7 sampling); controlled by the paired fresh baseline.
Cache_hits/Q 0.00 both arms (all live).

### 2026-11-13 — Phase 2.7 H18 Dev-300 A/B setup (pre-run record, no verdict yet)

User challenge 2026-11-13 (honest assessment requested): work since
v1 has been parameter tweaks and small bolt-ons around the same
draft-first pipeline, not architecture change — and Dev-100 A/Bs
cannot decide the mechanisms being tested. The numbers agree: v1
Test-400 EM 0.4750 still beats tuned (0.4500) and improved (0.4600);
H15's gate pass was dEM exactly +0.02 with 95% CI [−0.05, +0.09],
p=0.7744 — noise-level. Decision, user-confirmed 2026-11-13:
H18 (the one structural change built, `ddb18c1`) is tested first,
on Dev-300, then H20/H21 if it fails. Protocol change, recorded
BEFORE the run (dated amendment, HARKing rule): decision set
Dev-100 → Dev-300 (first 300 rows of
`data/manifests_dev500/dev.jsonl`; the Dev-500 manifest was built
2026-11-13 from the re-downloaded full official dev set — 7,405
rows, HuggingFace parquet, CMU URL dead — 500 fresh Qs, seed 29,
stratified bridge/hard 400 + comparison/hard 100, disjoint from
debug-50/dev-100/test-400, sha256 ae030ccd...; corpus = Dev-500 +
Test-400 passages, 8,812 after dedupe; committed + pushed
`7486fa2`). Gate unchanged (dEM ≥ +0.02 AND wrong-answer rate not
up AND dcalls ≤ +0.5), plus a pre-registered extend rule: dEM in
[+0.01, +0.04] with the 95% CI straddling 0 → AMBIGUOUS, extend to
the full Dev-500 instead of calling it. Verdict script updated
(`scripts/phase26_h18_verdict.py` prints the extend assessment;
dry-run on the H12 pair reproduces the recorded numbers exactly:
dEM +0.0300, dF1 −0.0033, dcalls +0.39, McNemar p=0.4531, GATE
PASS — and flags AMBIGUOUS on N=100, as the rule intends). Chain
updated (`~/workspace/phase26_h18_chain.sh`: manifest
`data/manifests_dev500`, `--limit 300`, fresh namespaces
`dev300_p27_h18_{base,evidence}_bm25`). Cache split, same commit:
`run.cache_path` wired through the runner into the LLM client
(`configs/base.yaml` default `results/cache.sqlite`; 2 new tests in
`tests/test_cache.py`, all 7 pass); H18 writes its own file
`results/cache/cache_p27_h18.sqlite`; the shared
`results/cache.sqlite` (16.7MB, 49,272 rows, zero lock errors) and
`results/nli_memo.pkl` are untracked from git (files stay on disk;
the namespace is hashed into each key, so one experiment's entries
cannot be pruned from the shared file — the reason for the split).
Groq key re-sent 2026-11-13 (smoke-tested 200, live; used
transiently only, never saved; rotation advised since pasted in
chat) and the 15-commit backlog pushed (`af77d52` → `ddb18c1`,
verified, 0 ahead). A/B launching now; verdict goes here when it
lands. Expected ~40 min for both arms (~3,000 calls); the run also
calibrates the new key's throughput/rate limits.

## Appendix — Key numbers (frozen)

**TrueAdaptive v1, Test-400 BM25 (N=400, 0 failed, 0 cache hits):**
EM 0.4750, F1 0.6192, 4.78 calls/Q, coverage 0.8075, recall 0.8975.
Calls {2:86, 4:59, 5:126, 6:75, 7:23, 8:18, 9:13}; hops {0:160, 1:198, 2:42}.

**IRCoT fresh, Test-400 BM25:** EM 0.4200, F1 0.5674, 2.545 calls/Q,
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
