# Design: Tune-Hop2-SC-Cap — Cap the hop-2 call tail (tuning step 5)

## Mechanism (pre-registered)

The cap is the existing config value `erag.max_hops`, set to `1` in the
A/B's `--set` flags. No new flag, no `src/` change.

The hop loop in `src/systems/erag.py` (`run_erag`) stops when
`hop >= e.get("max_hops", 2)` (line 240), checked after each hop's trace
entry is appended. With `max_hops=1`, a row that would have gone to hop 2
instead breaks after hop 1: its final draft is the hop-1 draft, its graph
is the hop-1 graph, and the post-loop machinery (step-1 re-read,
post-hop confidence, abstention) reads the hop-1 state. Per skipped
hop-2 row the saving is exactly the hop-2 iteration's calls: 1 draft
call + 1 claim-extraction call iff the hop-2 draft would have differed
from the hop-0 draft (under the `incremental` claim strategy, extraction
is skipped when the draft is unchanged).

What does NOT change under the cap:

- **Self-consistency.** SC runs at most once per question, at hop 0
  (Step 3: only while `c0 is None`), and is Fast-Path-gated there. The
  cap touches no SC call, because no SC call exists at hop 2.
- **Fast-Path gate.** Unchanged; hop-0 Fast-Path skips (86 rows on test,
  2.00 calls, EM 0.5465) are unaffected.
- **Claim-grounded re-read (step 1).** Runs after the loop on the final
  graph, unchanged. It still triggers on unknown/disagree drafts.
- **Abstention (`theta_abs`).** Unchanged (step 4 owns it). Note the
  interaction the A/B measures: on a capped row the abstention rule reads
  the hop-1 graph's answer claim, not the hop-2 one. The stored-row
  counterfactual in the proposal is draft-level only and cannot see this
  — the A/B's final EM is the real measure.
- **Hop 0 and hop 1.** Identical. A row that stops at hop 0 or hop 1
  under `max_hops=2` produces byte-identical behavior under
  `max_hops=1`.

Expected magnitudes (counterfactuals from stored rows, proposal.md Why):
dev ≈ −0.15 calls/Q (15 calls/100, 10 hop-2 rows); test ≈ −0.19
calls/Q (74 calls/400, 42 hop-2 rows). These are expectations, not gate
thresholds — the gate only requires calls/Q to fall.

## Selection rule (pre-registered, before any run)

One A/B, one gate (tasks.md D.1). If it passes, the frozen tuned config
(written at end of Phase 1) records `max_hops: 1`. If it fails, the
tuned system keeps `max_hops: 2`, the step is recorded as a negative
result, and the cap is NOT narrowed inside this change — candidate B
(forced incremental reuse at hop 2) becomes its own follow-up change.
The result is reported regardless of outcome.

## Guardrails

- The frozen v1 config (`configs/erag_trueadaptive.yaml`) is NOT edited.
  The tuned value lives in the frozen tuned config at end of Phase 1.
- No threshold, retriever, graph, NLI, prompt, or re-read change in this
  change. Step 4 owns `theta_abs`; this change must not re-tune it.
- The A/B baseline is the post-step-4 tuned dev file. Do NOT compare
  against step-2's 0.54 unless step 4 was skipped. Verify the `--set`
  flags against the step-4 change's frozen values before running.
- Cache: the namespace is reused deliberately (as in steps 1–3), and the
  cap removes calls rather than changing prompts. Report `cache_hits`/Q
  and live calls/Q (`llm_calls − cache_hits`) for both files; a saving
  that appears in `llm_calls` but not in live calls is a cache artifact,
  not a win.
- Dev has only 10 hop-2 rows: do not over-read a 1–2 row EM move in
  either direction. The gate's EM allowance is 1 pt (1 row) for exactly
  this reason; the calls measure is the primary one.

## Correction note (applies the step-2/3 lesson)

Steps 2 and 3 each found their measurement path broken or assumed. For
this change, verify the measurement path BEFORE the live A/B:

- The analyzer (`scripts/analyze_trueadaptive_test400.py`) already
  reports EM, F1, and mean `llm_calls` for a dev file (§1 Overall) and
  a per-hop call breakdown (§6 Call tail) — but §6 is computed on the
  TEST file only, and NOTHING in the analyzer reports `cache_hits`.
  The gate needs, for the dev file: EM, calls/Q, `cache_hits`/Q, live
  calls/Q, the hops distribution (n, mean calls, EM per hops value),
  and the hop-2 row count. That is the `--hopcap` section (tasks.md
  A.2). All of its inputs are fields the runner already writes on every
  stored row (`llm_calls`, `cache_hits`, `hops`, `trace[i].answer`,
  `em`, `gold`, `failed` — verified against the stored Test-400 and
  step-2 dev files). No new trace field is needed.
- If the `--hopcap` section cannot reproduce the known stored-file
  numbers (step-2 tuned dev: EM 0.5400, 4.65 calls/Q, 10 hop-2 rows,
  78 hop-2 calls; Test-400 v1: 42 hop-2 rows, 334 hop-2 calls, tail
  54 rows / 422 calls), stop and fix the measurement before running —
  do not run and report zeros.

## Threats to validity

- **Dev is a weak instrument for this step.** Only 10 of 100 dev rows
  reach hop 2, so the expected dev saving (0.15 calls/Q) rests on 10
  rows and the EM guardrail on 1 row. A single live-call flip (temp-0.0
  nondeterminism flipped 8 untouched rows in step 1) can move the EM
  guardrail. Mitigation: the gate's calls measure is precise even at
  N=100, and the verdict is confirmed on Test-400 at the end of tuning
  (§4 of the master plan) — dev is a smoke test, not the verdict.
- **Draft-level counterfactual ≠ final EM.** The −2-row test estimate
  compares hop-1 vs hop-2 drafts; final answers pass through abstention
  (11 of 42 hop-2 rows are abstained) and the re-read. On hop-2 rows the
  hop-2 draft EM (0.5238) already exceeds final EM (0.4048), so the
  interaction cuts both ways: skipping hop 2 could lose fewer than 2
  rows (abstention would have withheld some hop-2 fixes anyway) or more
  (the hop-1 graph's answer claim could withhold a row hop 2 would have
  answered). Mitigation: the gate is on the A/B's final EM, not on the
  counterfactual.
- **Step-4 baseline risk.** Step 4 is undecided when this change is
  drafted. If step 4 changes `theta_abs`, the baseline EM moves (the dev
  sweep says t=0.0 → 0.58 vs t=0.4 → 0.56) while calls/Q does not move
  (abstention costs no calls). The gate is written against the baseline
  file, not against fixed numbers, so it survives either outcome — but
  the A/B MUST use the post-step-4 file as its baseline, and the
  comparison MUST be re-derived from that file, not copied from step 2.
- **Live-call noise vs the saving.** The expected dev saving is 15
  calls; a live re-run of the same system at temp 0.0 can flip ~8 rows'
  drafts (step-1 evidence). A flipped row can change its hop count and
  its call count by ±2–3 calls. The saving is therefore visible only in
  aggregate (mean calls/Q), never row-by-row — do not report per-row
  call deltas as evidence.
- **Cache-replay confounding.** The A/B reuses the namespace, so rows
  that stop at hop 0/1 replay their baseline calls from cache. `llm_calls`
  counts replays, so the mean still falls by the skipped calls — but the
  LIVE saving (Groq calls, the actual cost) is smaller than the
  `llm_calls` saving whenever the baseline's hop-2 calls were replays.
  Mitigation: the gate requires live calls/Q to fall as well, and both
  files' `cache_hits`/Q are reported.
- **Generality (single retriever, single LLM).** The diagnosis is on
  BM25 + `openai/gpt-oss-20b` only. Hop-2 rows are 10.5% of test here;
  on another retriever or model the hop distribution — and therefore
  the saving — could differ. The claim is scoped to this system; Phase 3
  (new dataset, same retriever first) is where generality is tested.
- **The cap is a blunt instrument.** `max_hops=1` skips hop 2 for every
  row, including the 4 test rows hop 2 fixed. A conditional cap would
  save less (candidate A: 10 calls/400) and lose 2 of those 4 fixes
  anyway. The bluntness is the price of the saving, and the gate is the
  check that the price is worth it.
