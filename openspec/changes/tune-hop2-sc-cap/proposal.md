# Proposal: Tune-Hop2-SC-Cap — Cap the hop-2 call tail (tuning step 5)

## Status

Draft — prepared 2026-11-09 from `docs/trueadaptive-test400-error-analysis.md`
(§5) plus a fresh diagnosis of the hop-2 tail from the stored Test-400 and
step-2 tuned dev files (see Why; all numbers recomputed with the repo's
`exact_match`, rows deduplicated by id keeping the last row). Branch
`trueadaptive`. No code written yet. Fifth of five tuning changes; one
OpenSpec change per tuning step ("for each step use openspec along the way",
user 2026-11-09). Steps 1 (reader grounding), 2 (claim extraction), and 3
(unknown prompt — gate failed, mechanism dropped) are built, gated, and
archived. Step 4 (`tune-theta-abs`) runs BEFORE this step's A/B and is
undecided at the time of writing — see the step-4 dependency below.

**Decisions — resolved:**
1. Tuning order: (1) reader/graph — done, (2) claim extraction — done,
   (3) model-unknown prompt — done, mechanism dropped, (4) theta_abs —
   undecided, runs first, (5) hop-2 cap — THIS change.
2. Tune on Dev-100 only (BM25, k=3, distractor). One Test-400 confirmation
   run at the END of tuning, not after this step.
3. This change is a pure cost lever: it must buy fewer calls without losing
   accuracy. A cost step that costs accuracy is a trade, not a win, and the
   trade is decided at the Test-400 verdict (§4 of the master plan), not on
   dev.
4. **Step-4 dependency.** This change's A/B runs on the tuned system as it
   stands AFTER step 4, and its baseline is the post-step-4 tuned dev file —
   NOT step-2's EM 0.54. Step 4 only moves `theta_abs`, which costs no
   calls and does not touch the hop loop, so the hop-2 population is
   expected to be nearly identical — but the baseline numbers (EM, calls/Q)
   are step 4's, whatever they are, and are NOT assumed here. If step 4 is
   skipped (theta_abs goal undecided), the baseline is the step-2 tuned dev
   file (EM 0.5400, F1 0.6391, 4.65 calls/Q). The A/B command in tasks.md
   must be verified against the step-4 change's frozen values before
   running.

## Why

The tail is real, measured, and concentrated in hop 2. Test-400 BM25 v1
(N=400, 1,910 calls, EM 0.4750), deduplicated:

| Hops reached | Rows | Calls | Mean calls/Q | EM |
|---|---|---|---|---|
| 0 | 160 | 483 | 3.02 | 0.5062 |
| 1 | 198 | 1,093 | 5.52 | 0.4646 |
| 2 | 42 | 334 | 7.95 | 0.4048 |

Rows with ≥7 calls: 54 (14%) consume 422 calls (22.1% of all) at EM
0.3333; 38 of the 54 are hop-2 rows. Hop-2 rows are the most expensive
and the least accurate — but they are only 42 rows (10.5%), so the
saving is bounded: the whole hop-2 population costs 334 calls (17.5%).

**Correction to the plan's sketch (§3.5).** The plan suggests capping
"self-consistency work on hop 2 (e.g. skip post-hop resampling on hop 2,
or cap SC samples on hop 2 at 1)". Neither exists in the v1 code:

- Self-consistency runs at most ONCE per question, at hop 0
  (`src/systems/erag.py` Step 3: SC runs only while `c0 is None`, and `c0`
  is set at hop 0 — by SC, by the Fast-Path gate, or by the `no_conf`
  ablation). There is no SC call at hop 1 or hop 2 to cap.
- Post-hop resampling is ALREADY off: the frozen v1 config sets
  `post_hop_resample: never`, so the post-loop resample (erag.py, after
  the loop) never fires.
- `targeted_retrieve` makes no LLM call either (`eig_strategy: direct`
  uses the claim text as the query; no query-proposal call).

The only LLM calls in the hop loop are the draft (1 per hop) and claim
extraction (1 per hop — skipped when the draft is unchanged, under the
`incremental` claim strategy). So a hop-2 row's marginal cost is 1 draft
call + 1 extraction call iff its hop-2 draft differs from its hop-0
draft. The cap must target the hop-2 iteration itself, not SC.

**Diagnosis of the three candidate caps** (counterfactual on stored
rows; draft-level EM only — the A/B's final EM is the real measure,
because abstention and the re-read act after the loop):

| Candidate | Mechanism | Calls saved /400 test | Calls saved /100 dev | Draft-level EM cost |
|---|---|---|---|---|
| A — stable-draft skip | Skip hop 2 when the hop-1 draft equals the hop-0 draft | 10 (0.03/Q) | 5 (0.05/Q) | −2 rows test, 0 dev |
| B — forced incremental reuse at hop 2 | Skip the hop-2 extraction call even when the draft changed | 32 (0.08/Q) | 5 (0.05/Q) | Unmeasurable from stored rows (graph-dependent) |
| C — max_hops = 1 | Skip hop 2 for every row | 74 (0.19/Q, 3.9%) | 15 (0.15/Q, 3.2%) | −2 rows test, 0 dev |

- **A is dead on diagnosis.** The trigger fires on only 8/42 test rows
  (5/10 dev) — hop 1 usually changes the draft (34/42) — and 2 of the 4
  hop-2 fixes sit inside those 8 rows: the draft was stable through
  hop 1, but hop 2's new evidence fixed it. It saves almost nothing and
  loses the very rows hop 2 helps. Rejected; not run.
- **B saves less than C and its EM effect cannot be computed from stored
  rows.** Forcing claim reuse at hop 2 leaves the graph holding the old
  draft's claims while the final answer is the new draft — the answer
  claim (which drives abstention and the re-read trigger) would be stale,
  and the re-read would then fire on "disagree" and spend a call back.
  It is the follow-up if C fails, as its own change — not tried here.
- **C is the mechanism.** It is also the simplest: `erag.max_hops` is
  already the loop's stop condition (erag.py:240) and already a config
  value (frozen v1 config: 2). The A/B sets it to 1 in the `--set` flags.
  No code change is expected; no new flag.

**What hop 2 actually earns.** On hop-2 rows, hop 2 fixed 4 drafts and
broke 2 (net +2); hop 1 on the same rows fixed 17 and broke 3 (net +14).
Hop 2 is worth far less than hop 1 — but it is not worthless, which is
why the cap is gated, not forced. Note the final-EM caveat on those rows:
their hop-2 draft EM is 0.5238 but their final EM is 0.4048 — abstention
withholds 11 of the 42 (13 end unknown). Skipping hop 2 changes the
graph the abstention rule reads, so the stored-row counterfactual
(−2 rows, draft-level) is an estimate, not the verdict. The A/B decides.

**Dev is a weak instrument for this step, stated up front.** The step-2
tuned dev file has only 10 hop-2 rows (78 calls). The expected dev
saving is 0.15 calls/Q — small against the ±3-row live-call noise band
— but calls are measured precisely (unlike EM on dev), and the gate's
calls measure is the primary one. The EM guardrail is 1 pt (1 row).

## What Changes — step 5

**A config-only cap: run the tuned system with `erag.max_hops=1`, one
Dev-100 BM25 A/B against the post-step-4 tuned dev baseline.** No `src/`
change is expected. The analyzer gains a `--hopcap` section reporting
the gate measures (tasks.md A.2) — the measurement path is verified
against stored files before any live run (design.md correction note).
If the gate passes, the frozen tuned config (written at end of Phase 1)
records `max_hops: 1`; if it fails, the tuned system keeps
`max_hops: 2` and the step is recorded as a negative result.

## Considered alternatives

- **Candidate A (stable-draft skip).** Rejected on diagnosis (above):
  10 calls/400 saved, loses 2 of the 4 hop-2 fixes.
- **Candidate B (forced incremental reuse at hop 2).** Follow-up only:
  32 calls/400, EM effect unmeasurable from stored rows, stale answer
  claim risks the abstention/re-read path. Its own change if C fails.
- **Cap sequential SC at M=2.** Rejected: SC runs once, at hop 0, and
  the tail rows that are not hop-2 (16 rows ≥7 calls at hop 1) reach ≥7
  only by running the full 3-sample SC plus two extractions. Capping M
  at 2 would save at most ~1 call on those rows while coarsening the
  confidence signal the whole system runs on — H3 already showed
  TrueAdaptive's confidence discriminates worse than Reference (AUROC
  0.5915 vs 0.6519), partly because sequential SC coarsens it. Wrong
  trade.
- **Cap the tail by call count (stop a row at 7 calls).** Rejected: a
  call budget is not a hop, and it would cut rows mid-hop (draft written,
  claims not extracted — an inconsistent state). Hop count is the clean
  unit; the loop already stops on it.
- **A new `erag.hop2_cap` flag instead of `max_hops`.** Rejected:
  `max_hops` already is the cap, already plumbed, already tested. A new
  flag would duplicate it and add a second stop condition to keep in
  sync. The frozen tuned config records `max_hops: 1` — same meaning.

## Non-goals (step-5 scope guard)

- Not a retriever, threshold, graph, NLI, prompt, or re-read change.
  `theta_abs`, the abstention rule, the Fast-Path gate, and the
  sequential-SC settings are untouched. Step 4 owns `theta_abs`.
- Not a change to what a hop costs (draft + extraction stay as they
  are) and not a change to hop 1. Only hop 2 is skipped.
- Not a Test-400 run. The confirmation run comes once, after all tuning
  steps, on the frozen system.

## Impact

- **Code:** none expected. The cap is `erag.max_hops=1` in the A/B's
  `--set` flags. The frozen v1 config (`configs/erag_trueadaptive.yaml`)
  is NOT edited (step-3 lesson: the frozen file stays frozen); the tuned
  value is recorded for the frozen tuned config at end of Phase 1.
- **Tests:** one mocked-LLM test proving the cap binds
  (`run_erag` with `max_hops=1` never reaches hop 2 — tasks.md A.1).
- **Evaluation:** one Dev-100 BM25 A/B on top of the post-step-4 tuned
  system, in the reused namespace (as in steps 1–3). Gate (per design.md,
  pre-registered): calls/Q falls; live calls/Q falls; EM not below the
  post-step-4 baseline by more than 1 pt; 0 failed rows. Expected dev
  saving ≈ 0.15 calls/Q (15 calls/100, counterfactual); test
  counterfactual ≈ 0.19 calls/Q (74 calls/400). Test-400 is NOT run for
  this step.
- **Cache:** the cap removes calls rather than changing prompts, so the
  namespace reuse is safe — but the skipped calls never happen, so the
  A/B's saving is visible in `llm_calls` regardless of replay. The
  `--hopcap` section reports `cache_hits`/Q and live calls/Q so a cache
  artifact cannot masquerade as a saving (step-1/2 lesson).
- **Branches:** work on branch `trueadaptive`. Nothing is pushed.

## Follow-up changes (one per tuning step)

- `tune-memory-effectiveness` (step 6) — stream A/B on the tuned system;
  gated before the Test-400 freeze.
- Possible step-5 follow-up if C fails: `tune-hop2-claim-reuse`
  (candidate B, forced incremental reuse at hop 2), as its own change.

## References

- Error analysis: `docs/trueadaptive-test400-error-analysis.md` (§5)
- Master plan: `docs/tuning-master-plan.md` (§3.5 — the plan's ~100
  calls/400 estimate is corrected here to 74 by the counterfactual)
- Step-3 change (archived):
  `openspec/changes/archive/2026-11-09-tune-unknown-prompt/` — its
  gate-failed-then-drop discipline and its analyzer-section pattern
  (`--unknown`) are the model for this change's `--hopcap` section.
- Hop loop: `src/systems/erag.py` (`run_erag`, esp. Step 3 SC gating
  and the `hop >= e.get("max_hops", 2)` stop at line 240); SC:
  `src/epistemic/confidence.py` (`sequential_consistency`, cap M=3);
  frozen config `configs/erag_trueadaptive.yaml`
  (`max_hops: 2`, `sc_samples: 3`, `sc_mode: sequential`,
  `post_hop_resample: never`, `eig_strategy: direct`).
- Baselines: step-2 tuned dev EM 0.5400 / F1 0.6391 / 4.65 calls/Q,
  10 hop-2 rows (78 calls); Test-400 BM25 v1 EM 0.4750, 4.78 calls/Q,
  42 hop-2 rows (334 calls). Step-4 baseline unknown until step 4 closes.
