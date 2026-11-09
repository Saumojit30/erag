# Proposal: Tune-Theta-Abs — Selective answering for hallucination reduction (tuning step 4)

## Status

Draft — prepared 2026-11-09 from `docs/tuning-master-plan.md` (§3.4),
`docs/trueadaptive-test400-error-analysis.md` (§2–§4), and a fresh
diagnosis of the abstention threshold from the stored step-2 tuned dev
file (see Why; all numbers recomputed with the repo's `exact_match`,
rows deduplicated by id keeping the last row). Branch `trueadaptive`.
No code written yet. Fourth of five tuning changes; one OpenSpec change
per tuning step ("for each step use openspec along the way", user
2026-11-09). Steps 1 (reader grounding) and 2 (claim extraction) are
built, gated, and archived. Step 3 (unknown prompt) is built, gated, and
archived — both variants failed their gate and the mechanism was dropped.
Steps 5 (`tune-hop2-sc-cap`) and 6 (`tune-memory-effectiveness`) are
drafted; their A/Bs run AFTER this step.

**Decisions — resolved:**
1. **The paper's goal, decided by the user 2026-11-09:** the main
   objective is to REDUCE HALLUCINATION of RAG, with reduced LLM cost
   second. So this step is SELECTIVE ANSWERING: the system should abstain
   rather than guess. It is judged by selective EM and wrong-answer rate,
   with EM as a guardrail (not the maximand). The formal paper-goal
   statement is still open and can be refined later; this step is built
   on the stated objective, and the proposal says so.
2. Direction is therefore HIGHER `theta_abs` values (more abstention →
   fewer wrong answers among the answers given), not lower. The dev
   sweep in the error analysis already shows lower thresholds raise EM
   (t=0.00 → 0.58 vs t=0.40 → 0.56 on dev) — that is the maximum-EM
   direction, and it is the direction this step does NOT take.
3. Tune on Dev-100 only (BM25, k=3, distractor). One Test-400
   confirmation run at the END of tuning, not after this step.
4. Two pre-registered candidate values (A: `theta_abs=0.50`,
   B: `theta_abs=0.65`), each its own Dev-100 BM25 A/B, each reported.
   No fishing through thresholds on dev and picking the best — that is
   selection on a 100-row set.

## Why

The abstention rule is the system's only hallucination control:
`src/systems/erag.py:346` withholds the answer (`"unknown"`) when the
final answer claim's confidence `ans.eff` falls below `theta_abs`
(currently 0.4). On Test-400 BM25 v1 the rule fires on 37 rows
(`answer_conf` median 0.214, max 0.368); 17 of the 37 have a *correct*
draft, so the rule already trades correct answers for safety. The
question this step answers is whether a higher threshold trades better:
fewer wrong answers among the answers the system does give, at the cost
of answering fewer questions and a lower headline EM.

**Diagnosis — the dev counterfactual** (step-2 tuned dev file,
`results/trueadaptive/erag_trueadaptive_bm25_dev_claims.jsonl`, N=100
deduped, 0 failed; baseline t=0.40: EM 0.5400, selective EM 0.6353,
wrong-answer rate among answered 0.3647, coverage 0.850, 4.65 calls/Q,
2.53 cache_hits/Q, 8 abstained, 7 model-unknown). Counterfactual rule,
as in the analyzer §4: abstained rows stay abstained; model-unknown
rows (draft literally "unknown") stay unknown; answered rows with
`answer_conf < t` become abstained. Definitions: selective EM = correct
/ answered; wrong-answer rate = wrong answered / answered; coverage =
answered / N. Note: with binary EM, wrong-answer rate = 1 − selective
EM — the two gate measures are one condition stated two ways (see
design.md).

| t | EM | Selective EM | Wrong-answer rate | Coverage | Newly abstained |
|---|---|---|---|---|---|
| 0.40 (current) | 0.5400 | 0.6353 (54/85) | 0.3647 (31/85) | 0.850 | — |
| 0.45 | 0.5200 | 0.6420 (52/81) | 0.3580 (29/81) | 0.810 | 4 (2 correct / 2 wrong) |
| **0.50** | **0.5100** | **0.6456 (51/79)** | **0.3544 (28/79)** | **0.790** | 6 (3 correct / 3 wrong) |
| 0.55–0.65 | 0.5100 | 0.6456 | 0.3544 | 0.790 | identical to 0.50 (plateau) |
| 0.67 | 0.5000 | 0.6410 (50/78) | 0.3590 (28/78) | 0.780 | 7 (4 correct / 3 wrong) |
| 0.75 | 0.4700 | 0.6351 (47/74) | 0.3649 (27/74) | 0.740 | 11 (7 correct / 4 wrong) |

**The honest finding: the confidence signal does not separate right
from wrong at the margin on dev.** Raising t from 0.40 to 0.50 abstains
6 rows — 3 correct, 3 wrong, a coin flip. Raising it to 0.75 abstains
11 rows — 7 correct, 4 wrong: the marginal rows are *more* often
correct than wrong. The best selective EM on dev is 0.6456 at t=0.50,
a gain of +1.03 pts over baseline, bought with −3.0 pts EM and −6.0 pts
coverage. Past 0.50, selective EM falls again (0.6410 at 0.67, 0.6351
at 0.75 — back below baseline). The threshold is a blunt lever on
N=100, and this step is justified by the stated paper goal, not by a
measured dev win. The Test-400 confirmation (§4 of the master plan) is
where the claim is actually tested.

**Why the plateau exists.** The answered rows' `answer_conf` values
have a gap: after 0.492 the next value is 0.667, then four rows at
0.721–0.745, then 74 rows at ≥0.844. Every threshold in (0.492, 0.667]
abstains exactly the same 6 rows. Candidates A (0.50) and B (0.65) are
therefore IDENTICAL on the stored-row counterfactual. They are still
both run, because the live A/Bs re-generate `answer_conf` (live-call
noise moves values across the boundary) and because on Test-400 the
distribution is continuous, so the two values differ there. The dev
A/B is a smoke test; the selection rule (design.md) picks between them.

**Test diagnostic — context only, NEVER the selection basis.**
Test-400 BM25 v1 (N=400): t=0.40 EM 0.4750, selective EM 0.5882,
wrong 0.4118, coverage 0.807; t=0.50 EM 0.4400, selective EM 0.5906
(+0.24), wrong 0.4094, coverage 0.745, 25 newly abstained (14 correct /
11 wrong); t=0.65 EM 0.4275, selective EM 0.5897 (+0.15), wrong 0.4103,
coverage 0.725, 33 newly abstained (19 correct / 14 wrong). Same story
as dev: the marginal rows are majority correct, the selective-EM gain
is ~0.2 pts, the EM cost is 3.5–4.75 pts. Quoted here only so the
Test-400 confirmation is not a surprise — no value is selected on it.

**Candidates (pre-registered):**
- **A — `theta_abs=0.50`.** The selective-EM peak on the dev
  counterfactual. Predicted: EM 0.5100 (−0.03, exactly at the guardrail
  bound), selective EM 0.6456 (+1.03), wrong-answer rate 0.3544 (−1.03),
  coverage 0.790.
- **B — `theta_abs=0.65`.** Same counterfactual as A (plateau). The
  higher value; the live A/B is what distinguishes it from A. Predicted
  (counterfactual): identical to A.

**What this step does NOT touch.** The 40 Test-400 model-unknown rows
are a different population (draft literally "unknown",
`answer_conf` median 0.875) — `theta_abs` cannot touch them; step 3
confirmed this and its mechanism was dropped. The 17 Test-400
abstained rows with correct drafts are the mirror image: lowering the
threshold would answer them, and the dev sweep says that gains EM —
but that is the maximum-EM direction, rejected by the goal decision
above. Both populations are reported in the A/Bs, neither is re-tuned
here.

## What Changes — step 4

**A config-only threshold change: run the tuned system with
`erag.theta_abs` set to 0.50 (candidate A) and 0.65 (candidate B), one
Dev-100 BM25 A/B each against the step-2 tuned dev baseline.** No
`src/` change is expected — `theta_abs` is already a config value,
read once at the abstention rule (`src/systems/erag.py:346`,
`e.get("theta_abs", 0.4)`). The analyzer gains a `--theta` section
reporting the gate measures (tasks.md A.1) — the measurement path is
verified against stored files before any live run (design.md
correction note). If a candidate passes its gate, the frozen tuned
config (written at end of Phase 1) records that `theta_abs` value; if
neither passes, `theta_abs` stays 0.4 and the step is recorded as a
negative result.

## Considered alternatives

- **Lower the threshold (t=0.0–0.3) for maximum EM.** Rejected: the dev
  sweep shows it gains +1–2 pts EM on dev (0.58 at t=0.00) and the test
  diagnostic agrees (0.5175 at t=0.00) — but it answers more wrong
  answers too (coverage rises, selective EM falls), which is the
  opposite of the stated goal. The goal decision rules it out, not the
  numbers.
- **Abstain on `c0` (hop-0 self-consistency) instead of `answer_conf`.**
  Rejected: `c0` is hop-0 confidence; the abstention rule reads the
  *final* answer claim's confidence (`ans.eff`), which is what the
  re-read and the graph produce after all hops. H3 already showed `c0`
  discriminates worse for TrueAdaptive (AUROC 0.5915) than `answer_conf`
  (0.6286). Changing the abstained quantity would be a new mechanism,
  not a threshold tune.
- **A per-row adaptive threshold (e.g. scale with hops or recall).**
  Rejected: more parameters, no evidence any of them separates right
  from wrong — the marginal-row analysis above shows even the single
  threshold does not. A fancier rule on N=100 dev would be overfitting
  with extra steps.
- **Keep 0.4 (no change).** This is the outcome if neither candidate
  passes its gate — not a rejected alternative, the default. The gate
  decides; the step does not force a change.

## Non-goals (step-4 scope guard)

- Not a retriever, prompt, graph, NLI, or re-read change. `theta_abs`
  is the only value that moves; `ground_final_read`, `max_claims`,
  `unknown_prompt`, `max_hops`, and the Fast-Path gate are untouched.
  Step 5 owns `max_hops`; step 3 owns the unknown prompt (dropped).
- Not a change to the model-unknown population (draft "unknown") — no
  threshold touches it, and no prompt change is in this step.
- Not the H4 latency-bound clarification (master plan open decision 3c
  — the 3× Standard bound needs a dated clarification before Phase 2,
  e.g. 3× IRCoT or cost-per-correct-answer). That is a hypothesis
  clarification, not a tuning step, and it is not decided here.
- Not a Test-400 run. The confirmation run comes once, after all tuning
  steps, on the frozen system.

## Impact

- **Code:** none expected. `theta_abs` is an existing config value
  (`configs/base.yaml:31`, `configs/erag_trueadaptive.yaml:49`, both
  0.4). The A/Bs set it in the `--set` flags. The frozen v1 config
  (`configs/erag_trueadaptive.yaml`) is NOT edited (step-3 lesson: the
  frozen file stays frozen); the chosen value is recorded for the frozen
  tuned config at end of Phase 1.
- **Tests:** none for the mechanism (no code change). The analyzer
  `--theta` section is verified against stored files before any live
  run (tasks.md A.1) — a measurement verification, not a mocked-LLM
  test. The fast test suite runs green before any live run.
- **Evaluation:** two Dev-100 BM25 A/Bs on top of the step-2 tuned
  system, in the reused namespace (as in steps 1–3). Gate (per
  design.md, pre-registered): selective EM rises AND wrong-answer rate
  falls vs the step-2 tuned dev baseline, EM not below baseline by more
  than 0.03 (EM ≥ 0.51), calls/Q reported (threshold costs no calls).
  Expected dev moves (counterfactual): selective EM +1.03 pts, EM
  −3.0 pts, coverage −6.0 pts at t=0.50. Test-400 is NOT run for this
  step.
- **Cache:** the threshold changes no prompt and no call, so the
  namespace reuse is safe — but the A/Bs' rows are still checked for
  `cache_hits`/Q and live calls/Q (step-1/2 lesson: never assume cache
  replay; a run with ~0 live calls would be a replay, not a test).
- **Branches:** work on branch `trueadaptive`. Nothing is pushed.

## Follow-up changes (one per tuning step)

- `tune-hop2-sc-cap` (step 5) — drafted; its A/B runs AFTER this
  step, on the post-step-4 tuned dev baseline (NOT step-2's 0.54 —
  step 4 moves EM, so the step-5 baseline numbers are this step's,
  whatever they are).
- `tune-memory-effectiveness` (step 6) — drafted; stream A/B on the
  tuned system; gated before the Test-400 freeze.

## References

- Master plan: `docs/tuning-master-plan.md` (§3.4 — the goal decision
  is recorded there 2026-11-09; §8 measurement discipline; §9 open
  decision 2, now decided)
- Error analysis: `docs/trueadaptive-test400-error-analysis.md`
  (§2 the two unknown populations, §3 reasoning-not-retrieval, §4 the
  theta_abs sweep — dev selection set, test diagnostic only)
- Hypotheses: `docs/hypotheses-h1-h6-assessment.md` (H4 — adaptive vs
  no-adaptive, confirmatory, NOT TESTED on Test-400; its 3× latency
  bound is a separate dated clarification, not this step)
- Step-3 change (archived):
  `openspec/changes/archive/2026-11-09-tune-unknown-prompt/` — its
  gate-failed-then-drop discipline and its analyzer-section pattern
  (`--unknown`) are the model for this change's `--theta` section.
- Abstention rule: `src/systems/erag.py:346`
  (`abstain = "no_conf" not in ablate and (ans.eff < e.get("theta_abs", 0.4))`);
  row fields `answer_conf`, `abstained`, `would_abstain`,
  `unknown`, `em`, `llm_calls`, `cache_hits`.
- Baselines: step-2 tuned dev EM 0.5400 / selective EM 0.6353 /
  wrong-answer rate 0.3647 / coverage 0.850 / 4.65 calls/Q /
  2.53 cache_hits/Q (N=100, 8 abstained, 7 model-unknown); Test-400
  BM25 v1 EM 0.4750 / selective EM 0.5882 / wrong 0.4118 /
  coverage 0.807 (N=400, 37 abstained, 40 model-unknown).
