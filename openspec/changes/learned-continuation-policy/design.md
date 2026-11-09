# Design: Learned continuation policy (tuning step 7)

## The decision point (exact)

In `run_erag` (`src/systems/erag.py`), after the hop-0 draft,
claim extraction, and NLI verification — at the point where the
current code decides whether to enter the retrieval loop (the
theta_fast fast-path check and the first gap/EIG continuation
check) — the policy is consulted instead, when
`erag.continuation_policy` names a policy artifact file. When the
flag is absent (the default), behavior is exactly today's static
system: no code path changes, no flag, no behavior change. The
policy's output is binary: STOP (answer the hop-0 draft now, no
retrieval) or CONTINUE (enter the retrieval loop as today, with EIG
gap selection unchanged). At hop 1 and beyond, the existing static
rules govern (max_hops=2 ceiling). Abstention at the end is
unchanged (theta_abs=0.5, step 4).

## Features (all from the stored hop-0 trace, nothing new to run)

For each dev row, from `results/trueadaptive/erag_trueadaptive_bm25_dev_theta_a.jsonl`:

- `c0` (row field; range on dev 0.333–1.0) and `c0_source`
  (fast_path_min_eff vs sequential)
- claim-status counts from `trace[0]['graph']` (each claim carries
  `status` in {supported, contradicted, unresolved}, `conf`,
  `answer_bearing`, `conflict`, `source`): n_supported,
  n_unresolved, n_contradicted, n_conflict, answer-bearing claim
  status (supported / unresolved / contradicted / none), mean claim
  `conf`
- hop-0 recall, recomputed from `data/manifests/dev.jsonl`
  supporting_facts vs `trace[0]['pool']` titles (the H6 method —
  the row's `recall` field is final recall, not hop-0 recall, and
  must NOT be used as a hop-0 feature)
- question `type` (bridge / comparison), `draft == 'unknown'`,
  `sc_skipped_fast_path`
- **AMENDMENT 2026-11-09 (user chose retrain):** the `draft_unknown`
  feature is the HOP-0 draft (`trace[0]['answer']`) being literally
  'unknown' — NOT the row `draft` field. The original build used the
  row draft field (the established discipline for FINAL-answer
  classification), but the row draft is the final draft (last hop,
  possibly re-read-replaced; `src/systems/erag.py:354`) and does not
  exist at the hop-0 decision point. The two definitions diverge on
  16/100 dev rows (15 hop-0-unknown → final real answer, 1
  hop-0-real → final unknown, row 5abd44d9); hop-0-unknown count is
  20 vs row-draft-unknown 6; the other 11 features agree exactly.
  `draft_unknown` carries the largest coefficient, so the original
  Gate A pass (sim EM 0.5000, τ = 0.30) rested on a definitionally
  wrong feature and is SUPERSEDED by the re-check below. The
  row-draft discipline stands for final-answer classification only.

Label: hop-0 draft correct by repo `exact_match`
(`trace[0]['answer']` vs `gold`).

## Model

Logistic regression on the features above (standardized), one
model, no hidden layers, no text embeddings — N=100 admits nothing
bigger. The decision is CONTINUE iff P(draft correct) < τ, with τ
chosen by 5-fold cross-validation on dev to maximize saved calls
at EM ≥ baseline − 0.01 (the gate shape). The policy artifact is a
small committed JSON: model type, feature list (in order),
coefficients, intercept, τ, training provenance (file, N, date,
cross-validated scores). If logistic regression's cross-validated
counterfactual does not beat the static baseline, try ONE
alternative — a depth-2 decision tree (interpretable, paper-friendly)
— and take the better cross-validated result; no third model, no
feature search after seeing results.

### Final-model artifact (written 2026-11-09, after Gate A passed; REWRITTEN after the retrain — see below)

`configs/continuation_policy_dev.json`, written by
`scripts/train_continuation_policy.py --write-artifact` (which
refuses to write unless Gate A passes, and refuses non-logistic
winners — the format is linear-only). Contents: `model`
(logistic_regression), `features` (the 12 MODEL_FEATURES in order —
`sc_skipped` excluded, perfectly collinear with `fast_path`),
`coefficients` (12, in feature order), `intercept`,
`scaler_mean` / `scaler_scale` (12 each, from the final fit on all
100 rows), `tau`, `decision` (CONTINUE iff P < τ), and
`provenance` (training file, N=100, labels 48 correct / 52 wrong,
date, CV method, OOF AUROC, simulated EM, simulated calls/Q, Gate A
PASS). Inference is dependency-free: z =
intercept + Σ coefᵢ·(xᵢ − meanᵢ)/scaleᵢ, P = sigmoid(z) — no
sklearn import in `src/`.

**Superseded artifact (commit `d0fb457`, τ = 0.30, OOF AUROC
0.6546, simulated EM 0.5000, calls/Q 3.98):** written after the
original Gate A pass; verified by the parent (pure-arithmetic
recomputation matched the fitted pipeline to 2.2e-16; final
in-sample model at τ=0.30 would STOP 74 / CONTINUE 26 vs OOF
70/24). It is SUPERSEDED by the retrain below and must NOT be
used for wiring — it was trained on the wrong `draft_unknown`
definition.

**Current artifact (retrain, 2026-11-09):** τ = 0.05, OOF AUROC
0.6775, simulated EM 0.5152, calls/Q 3.92, provenance records the
retrain (hop-0 `draft_unknown` definition). `draft_unknown`
coefficient −1.489 (was −0.767). Verified by the parent the same
way (pure-arithmetic recomputation matches the fitted pipeline to
2.2e-16; final in-sample model at τ=0.05 would STOP 81 / CONTINUE
19 vs OOF 81/18 — the in-sample fit agrees closely with OOF).
The live Dev-100 run is in-sample for the final model by
construction, so Gate B's agreement check, not the raw live
numbers, is the wiring test.

## Counterfactual simulation (Phase A, no LLM calls)

For each dev row, the policy's action is determined by hop-0
features (all stored), so its path can be simulated from the stored
trace: STOP → answer = hop-0 draft (`trace[0]['answer']`), calls =
hop-0 calls; CONTINUE → the stored final answer and stored total
calls (the static system continued, so its outcome is the outcome
under CONTINUE — for rows the static system stopped at hop 0, see
the validity rule below). EM is repo `exact_match` throughout.

### Call accounting (must be exact)

Reconstructed hop-0 calls per row MUST sum, with the stored
hop-1/hop-2 calls, to the row's stored `llm_calls` — checked as an
invariant for every row before the simulation is believed. The
implementer determines the reconstruction from the code
(`src/systems/erag.py`, `src/epistemic/confidence.py`) and the
stored rows (draft 1 + extraction 1 + SC samples from `c0_source` /
trace + EIG probe if any). If an exact reconstruction is impossible,
the simulation must use a documented conservative approximation
(overestimate stopped rows' calls, never underestimate) and say so.

### Prefix-validity rule

The simulation is valid only where the policy's path is a prefix of
the stored path. Rows where the policy says CONTINUE but the stored
trace stopped at hop 0 (fast-path rows — no hop-1 draft exists) have
NO simulable outcome: they are counted, reported, and EXCLUDED from
the simulated EM/calls (not counted as correct, not counted as
wrong). If they exceed 10% of rows, the simulation is not a usable
gate and Phase A stops — the policy must be evaluated live instead,
with that recorded.

## Verification numbers (must reproduce exactly, Phase A)

On the theta_a dev file (N=100 deduped, 0 failed): hop-0 draft EM
0.4800, final EM 0.5100, fixed by hops 6, broke 3, hops {0:45,
1:45, 2:10}, abstained 15, draft-unknown 6 (row-draft count, kept as
an input-file check), hop-0 draft-unknown 20 (the feature's count
since the 2026-11-09 amendment), baseline EM 0.5100, 4.65 calls/Q.
The A.1 extraction MUST reproduce these before any training. The oracle ceiling (perfect draft-correctness model) is
computed in A.1 and recorded — it bounds what any policy can win
here, so a policy near the oracle is suspicious, not impressive.
(Computed 2026-11-09: included 83, excluded 17, EM 0.6506, calls/Q
4.61 — the ceiling saves only 0.04 calls/Q, because 28 of the 48
correct drafts already stop at hop 0 under the static fast path; the
oracle's EM is on the 83 included rows only, so it is not directly
comparable to the baseline EM 0.5100 on 100 rows.)

## Gate A (offline, pre-registered)

Cross-validated counterfactual on dev (out-of-fold predictions
only — never in-sample): simulated EM ≥ 0.5000 (baseline − 0.01)
AND simulated calls/Q strictly below 4.65. If it fails, the policy
does not proceed to wiring — no live run, no threshold re-picking.
If it passes, the final model is trained on all 100 dev rows and
the artifact is written.

### Re-check 2026-11-09 (supersedes the original pass)

The original Gate A pass (τ = 0.30, simulated EM 0.5000, calls/Q
3.98, STOP 70 / CONTINUE 24, excluded 6/100 — commit `fc1a428`)
rested on the wrong `draft_unknown` definition (row draft, not
hop-0 draft; see the Features amendment above). The B.1 subagent
caught the gap before writing any code; the parent verified it
independently (16/100 rows diverge; other 11 features agree
exactly). The user chose the retrain. Re-extraction +
re-training with the hop-0 definition, same pre-registered gate
(no threshold, gate, or feature change beyond the definition
fix): LR, τ = 0.05, simulated EM 0.5152, F1 0.6238, calls/Q 3.92
(saved +0.73), coverage 0.869, STOP 81 / CONTINUE 18, excluded
1/100 (1.0%). OOF AUROC 0.6775 (was 0.6546). **Gate A: PASS with
margin** (EM +0.0152 above the floor, not exactly at it; F1 and
coverage now ABOVE baseline 0.5969 / 0.790, previously below).
Composition (parent): STOP on 2/6 fix-rows (lost 2, was 4), STOP
on 2/3 broke rows (saved 2, was 1); STOP rows 47 correct at
hop-0, CONTINUE rows 4 correct at final = 51/99. The τ curve is
smooth (τ=0.10: EM 0.5204, 3.97 calls; τ=0.20–0.40: EM 0.5312–
0.5368, 4.10–4.20 calls) — the result is not knife-edge on τ.
The `draft_unknown` coefficient strengthened to −1.489 (was
−0.767): a hop-0 "unknown" is a near-perfect marker of a wrong
draft (label 0 always), so the model leans on it hard — which is
legitimate at decision time, since an "unknown" hop-0 draft means
the evidence did not support an answer. The `d0fb457` artifact
(τ = 0.30) is SUPERSEDED and must not be used for wiring; the new
artifact below replaces it.

## Gate B (live, pre-registered)

Dev-100 BM25, tuned system + policy, reused dev namespace
(`dev_trueadaptive_v1_bm25` — the policy changes which calls happen,
not the prompts, so cached calls still count as calls and the run is
fast; live calls/Q is reported but NOT gated, because the baseline
is a 99% replay and the comparison would be noise — the step-5
lesson). Live EM ≥ 0.5000 AND live calls/Q strictly below 4.65 AND
live numbers within ±0.02 EM / ±0.2 calls/Q of the simulation (else
the wiring is wrong, not the policy — fix the wiring, do not
re-tune). N=100 deduped, 0 failed.

## Threats to validity

- **Thin positives, thin data.** N=100; the value concentrates in
  6 fix-rows and 3 break-rows. The draft-correctness framing
  (48/100 positives) is what makes this learnable at all; a policy
  that merely reproduces the static system's hop pattern has
  learned nothing.
- **Dev gate is cross-validated, live dev is in-sample.** The final
  model trains on all 100 dev rows, so the live Dev-100 A/B is
  optimistic by construction. Test-400 is the real judge; dev is a
  smoke test, as always.
- **Simulation ≠ run.** The counterfactual assumes the stored
  hop-1 outcome is the outcome under CONTINUE — true only because
  the static system continued the same way. Any wiring difference
  (feature computed differently live than from the stored trace)
  breaks the equivalence; Gate B's agreement check exists for
  exactly this.
- **Contamination.** Test-400 rows must not appear in training,
  feature selection, τ choice, or model selection. The training
  script asserts its input file is a dev file and refuses test
  files. Any run that touches Test-400 before the Phase 2 freeze
  invalidates the verdict.
- **Step-5 precedent.** The step-5 gate failed on a replay-noise
  live-calls comparison (6 vs 4 live calls). This change does not
  gate on live calls/Q for exactly that reason; the design records
  the reasoning here so the omission is a decision, not an oversight.
- **Simulation STOP branch ignores the end-of-run steps.** STOP is
  simulated as hop-0 draft + hop-0 calls, but a live stopped row
  still runs the grounded re-read (+1 call, may change the answer —
  23/100 dev rows triggered it in the stored run) and abstention (9
  rows have hop-0 answer-claim eff < 0.5 and would be withheld live).
  The simulation therefore slightly misstates both the EM and the
  calls of stopped rows; Gate B's agreement check exists to catch a
  wiring-level mismatch, but this modeling gap is a reason the live
  numbers may sit slightly off the simulation even with correct
  wiring.
- **Simulated live calls/Q is an upper bound, not a measurement.**
  Hop-level cache hits are not stored, so the simulation reports the
  stored live calls/Q over included rows; STOP can only remove calls,
  so the true simulated live calls/Q is at or below the reported
  number.
- **A.2 reconstruction was exact — no approximation was needed.**
  The invariant (reconstructed hop-0 calls + stored later-hop calls
  == stored llm_calls) holds for all 100 dev rows with the rule:
  hop-0 = 1 draft + 1 extraction + SC samples (0 if Fast Path
  skipped, 2 if c0 == 1.0, else 3); later hops = 1 draft +
  1 extraction iff the draft changed vs hop 0, +1 for a triggered
  re-read. EIG probes cost 0 (direct) and post-hop resample costs 0
  (never).
