# Design: Tune-Theta-Abs — Selective answering for hallucination reduction (tuning step 4)

## Mechanism (pre-registered)

The mechanism is the existing config value `erag.theta_abs`, set to
`0.50` (candidate A) and `0.65` (candidate B) in the A/Bs' `--set`
flags. No new flag, no `src/` change.

The abstention rule (`src/systems/erag.py:346`) runs after the hop
loop, the step-1 re-read, and the post-hop confidence resolution:

```python
abstain = "no_conf" not in ablate and (ans.eff < e.get("theta_abs", 0.4))
answer = "unknown" if (active and abstain) else draft
```

`ans.eff` is the final answer claim's confidence, stored per row as
`answer_conf`. With a higher threshold, rows whose final answer claim
is below the threshold are withheld instead of answered. Nothing else
in the pipeline changes: the hop loop, the Fast-Path gate, the claim
graph, the re-read, and the retrieval all run identically — the
threshold only decides, at the end, whether the draft is shown or
withheld. That is why the A/Bs' calls/Q should be unchanged (the
threshold costs no calls) and why the gate's calls measure is a sanity
check, not a target.

What does NOT change under either candidate:

- **The hop loop and Fast Path.** Identical. A row that stops at hop 0
  or hop 1 under `theta_abs=0.4` produces the same drafts, claims, and
  calls under 0.50/0.65 — only the final withhold decision differs.
- **The re-read (step 1).** Runs before abstention, on the final graph,
  unchanged. A re-read that fixes a draft can lift its `answer_conf`
  above the threshold; a re-read that breaks one can drop it below.
  The A/B's final EM is the real measure — the stored-row
  counterfactual in the proposal cannot see re-read interactions,
  because the re-read runs live.
- **The model-unknown population.** Rows whose draft is literally
  "unknown" stay "unknown" at any threshold: their answer is already
  "unknown", so withholding changes nothing (EM 0 either way). The
  threshold cannot recover them — step 3 established this, and its
  mechanism was dropped for it.
- **The `abstained` flag on model-unknown rows.** A reporting artifact
  to watch: at t=0.50, one dev model-unknown row (`answer_conf` 0.424)
  would flip `abstained=True` in a live run; at t=0.65, two (0.424,
  0.629). Their answers stay "unknown" and their EM stays 0 — but the
  analyzer's §2/§3 split counts `abstained` first, so those rows would
  move from "model-said-unknown" to "system-abstained" in the report.
  The `--theta` section (tasks.md A.1) classifies the two populations
  by draft text (`draft == "unknown"`), not by the flag, so the split
  stays honest.

Expected magnitudes (counterfactuals from stored dev rows, proposal.md
Why): at t=0.50, selective EM +1.03 pts (0.6353 → 0.6456),
wrong-answer rate −1.03 pts (0.3647 → 0.3544), EM −3.0 pts (0.54 →
0.51), coverage −6.0 pts (0.850 → 0.790). At t=0.65 the counterfactual
is identical (plateau — no answered rows with `answer_conf` in
(0.492, 0.667]). These are expectations, not gate thresholds — the
gate only requires the direction and the EM guardrail.

## Selection rule (pre-registered, before any run)

Two A/Bs, one gate each (tasks.md D.1). A candidate proceeds only if
it passes its gate. If both pass, the one with the larger
wrong-answer-rate fall proceeds; tie → candidate A (`theta_abs=0.50`,
smaller coverage loss and smaller EM cost). If exactly one passes, it
proceeds. If neither passes, `theta_abs` stays 0.4, the step is
recorded as a negative result, and NO third value is tried inside this
change — a threshold re-tried until it passes on dev is overfitting
with extra steps. The result is reported regardless of outcome. The
chosen value (if any) is recorded for the frozen tuned config at end
of Phase 1; the frozen v1 config is never edited.

## Guardrails

- The frozen v1 config (`configs/erag_trueadaptive.yaml`) is NOT edited.
  The tuned value lives in the frozen tuned config at end of Phase 1.
- No threshold other than `theta_abs`, no retriever, graph, NLI,
  prompt, or re-read change in this change. Step 5 owns `max_hops`;
  step 3 owned the unknown prompt (dropped).
- The A/B baseline is the step-2 tuned dev file (EM 0.5400, selective
  EM 0.6353, wrong-answer rate 0.3647, coverage 0.850, 4.65 calls/Q).
  Step 4 is the FIRST threshold step, so its baseline is step 2's —
  unlike step 5, whose baseline is this step's.
- Cache: the namespace is reused deliberately (as in steps 1–3), and
  the threshold changes no prompt and no call. Report `cache_hits`/Q
  and live calls/Q (`llm_calls − cache_hits`) for both files; a run
  with ~0 live calls/Q would be a replay, not a test — discard it, do
  not analyze it.
- Dev has only 100 rows and the gate's selective-EM move is ~1 pt (1
  row). Do not over-read a 1–2 row move in either direction. The gate
  is a smoke test; the verdict is confirmed on Test-400 at the end of
  tuning (§4 of the master plan).

## Correction note (applies the step-2/3 lesson)

Steps 2 and 3 each found their measurement path broken or assumed. For
this change, verify the measurement path BEFORE the live A/B:

- The analyzer (`scripts/analyze_trueadaptive_test400.py`) already
  reports EM, F1, mean `llm_calls`, and coverage for a dev file (§1
  Overall) and a `theta_abs` counterfactual sweep (§4) — but §4
  reports only EM and coverage, only up to t=0.4, and NOTHING in the
  analyzer reports selective EM or wrong-answer rate. The gate needs,
  for the `--ta-dev` file: N (deduped), failed count, EM, selective EM
  (correct / answered), wrong-answer rate among answered, wrong answers
  among all rows, coverage, mean `llm_calls`/Q, mean `cache_hits`/Q,
  mean live calls/Q, abstained count, model-unknown count (by draft
  text) — plus the counterfactual table at t = 0.40–0.80 for the same
  file, computed the same way as §4. That is the `--theta` section
  (tasks.md A.1). All of its inputs are fields the runner already
  writes on every stored row (`answer_conf`, `abstained`, `unknown`,
  `draft`, `em`, `gold`, `llm_calls`, `cache_hits`, `failed` — verified
  against the stored step-2 dev file). No new trace field is needed.
- If the `--theta` section cannot reproduce the known stored-file
  numbers (step-2 tuned dev: EM 0.5400, selective EM 0.6353,
  wrong-answer rate 0.3647, coverage 0.850, 4.65 calls/Q,
  2.53 cache_hits/Q; counterfactual t=0.50: EM 0.5100, selective EM
  0.6456, wrong 0.3544, coverage 0.790; t=0.65 identical to 0.50;
  t=0.75: EM 0.4700, selective EM 0.6351, wrong 0.3649, coverage
  0.740), stop and fix the measurement before running — do not run
  and report zeros.
- The gate's two headline measures are complements, stated plainly so
  nobody mistakes them for two independent wins: with binary EM and
  "answered" defined as "final answer is not literally unknown",
  wrong-answer rate among answered = 1 − selective EM. The binding
  constraints are selective EM (direction) and the EM guardrail (cost).
  Coverage is reported ungated — it is the known price of the
  mechanism, and the frozen config records it alongside the value.

## Threats to validity

- **Overfitting a 100-row dev set with a threshold — the step's central
  risk, stated in the plan (§3.4).** The gate's selective-EM move is
  ~1 pt (1 row) and the EM guardrail is 3 pts (3 rows). A single
  live-call flip (temp-0.0 nondeterminism flipped 8 untouched rows in
  step 1) can move either measure by more than the gate's margin. The
  threshold is therefore NOT selected by maximizing dev selective EM —
  the candidates are pre-registered from the counterfactual, the gate
  is direction-plus-guardrail (not "best of N"), and no third value is
  tried if both fail. Mitigation: the verdict is confirmed on Test-400
  at the end of tuning — dev is a smoke test, not the verdict.
- **The marginal rows do not separate right from wrong.** On dev, the
  6 rows a 0.50 threshold newly abstains are 3 correct / 3 wrong; on
  the test diagnostic, the 25 rows a 0.50 threshold newly abstains are
  14 correct / 11 wrong. `answer_conf` at the margin is close to a coin
  flip. The mechanism can therefore raise selective EM only slightly
  while costing more EM than it saves in wrong answers. Mitigation: the
  gate requires the direction on dev AND the EM guardrail; the
  Test-400 confirmation measures the same trade on 400 rows, where a
  1-pt move is 4 rows, not 1.
- **Selective EM on dev is noisy by construction.** The denominator
  (answered rows) shrinks as the threshold rises, so a 1-row change in
  the numerator moves selective EM by ~1.3 pts at coverage 0.79. A
  candidate can "pass" on one row's luck. Mitigation: the gate also
  requires the EM guardrail (which the same row would breach if it were
  a correct answer withheld) and the wrong-answer-rate fall (the same
  condition, not an independent one — see the correction note).
- **Live-call noise vs the counterfactual.** The proposal's expected
  magnitudes are computed on STORED `answer_conf` values. The live
  A/Bs re-run the pipeline, so drafts, graphs, and `answer_conf`
  values shift — the plateau that makes candidates A and B identical
  on stored rows may not hold live, and the EM cost may land above or
  below the 0.03 bound for either candidate. Mitigation: the gate is
  applied to the LIVE A/B files, not to the counterfactual; the
  counterfactual is an expectation, never the verdict.
- **Cache-replay confounding.** The A/Bs reuse the namespace, so rows
  that stop at hop 0/1 replay their baseline calls from cache. The
  threshold changes no prompt, so replay cannot change any answer —
  but a run with ~0 live calls/Q would still be a replay, and its
  `answer_conf` values would be the baseline's, not the candidate's.
  Mitigation: report live calls/Q per file; discard a ~0-live-call
  run, do not analyze it.
- **The goal is stated, not formal.** The user decided the objective
  (reduce hallucination first, cost second) but the formal paper-goal
  statement is still open. If the formal statement later refines what
  "hallucination" means (e.g. wrong answers vs unsupported claims vs
  abstention rate), this step's gate — selective EM and wrong-answer
  rate — may need a dated clarification before Phase 2. The step does
  not invent a formal goal; it builds on the stated objective and says
  so.
- **Generality (single retriever, single LLM).** The diagnosis is on
  BM25 + `openai/gpt-oss-20b` only. The `answer_conf` distribution —
  and therefore which thresholds bite — could differ on another
  retriever or model. The claim is scoped to this system; Phase 3 (new
  dataset, same retriever first) is where generality is tested.
