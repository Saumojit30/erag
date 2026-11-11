# Phase 2.5 — Improvement diagnosis (stored data only, 2026-11-11)

User decision 2026-11-11: improve first, then Phase 3. This document is the
diagnosis that motivates the improvement round, and the pre-registration of
its hypotheses. **Everything below the hypotheses was written before any new
run was launched.** The diagnosis uses stored Test-400 rows only (diagnostic,
never selection): `results/trueadaptive/erag_trueadaptive_tuned_test.jsonl`
(deduped N=400) vs `results/trueadaptive/erag_fp_control_test.jsonl` (N=400).
Script: `scripts/diagnose_phase25.py` (reproduces every number here).

## What the tuned system loses, and where

Error budget (tuned, Test-400): right 180, wrong-answered 147, system-abstained
43 (15–16 drafts correct), model-unknown 30.

### Q1 — Eager SC (FP-control) vs tuned: 19 gains, 12 losses, net +7

- Gains (FP-control right, tuned wrong, n=19): in the tuned file 9 were
  system-abstained and 14 model-unknown — eager SC *answers* rows the tuned
  system left unanswered (0 abstained / 0 unknown in FP-control on these
  rows). 14/19 were hop-0 rows in the tuned file; the tuned policy said
  STOP on 12/19, yet FP-control got them right (6 of them by continuing to
  hop 1–2). Cost on gains: 5.11 vs 5.16 calls — the same.
- Losses (FP-control wrong, tuned right, n=12): in FP-control 7 abstained
  and 9 unknown — eager SC *pushes* rows into abstain/unknown that the tuned
  system answered correctly. Cost on losses: tuned 4.58 vs FP-control 5.58.
- Reading: eager SC churns the answer/abstain boundary in **both**
  directions. Net +7 rows (dEM +0.0175, p=0.28) at +0.70 calls/Q overall.
  That is weak, directional evidence — a dev replication check, not a sure
  thing. See H14 and its circularity note.

### Q2 — The 53 gold-in-claims wrong rows: the system picks the wrong claim

Full-recall wrong (answered): 86. Gold in some trace claim: 53.
Gold never a claim: 33.

- The re-read did **not** trigger on 41/53. It fires only on 'unknown' (2)
  or 'disagree' (10) — a draft that agrees with its (wrong) claims never
  gets a second look.
- **34/53 rows: the final answer sits inside a WRONG supported claim.**
  The gold-bearing claims are also there (100 supported, 14 unresolved, 9
  contradicted; 41 answer-bearing) — the system holds both answers and
  picks the wrong one.
- The system is confidently wrong: mean c0 0.94, mean answer_conf 0.90.
  The confidence signal cannot separate these rows.
- 41/53 never left hop 0.
- Reading: the failure is **claim selection at the final read**, not
  extraction and not retrieval. The re-read as built cannot see it,
  because its trigger is disagreement, and these rows agree — with the
  wrong claim.

### Q3 — The 33 never-claimed rows: extraction failed, retrieval did not

- Hop-0 recall 1.0 on 27/33, 0.5 on 6/33. The evidence was retrieved at
  hop 0 and never became a claim. 25/33 stayed at hop 0.
- Reading: an **extraction-recall** failure. A second extraction pass over
  the hop-0 pool (or question-entity-targeted extraction) is the candidate
  mechanism.

### Bonus — the 43 abstained rows

- 15 drafts correct by repo EM; 26/43 have gold in claims; re-read did not
  trigger on 34/43.
- Lowering theta_abs would recover EM here (test diagnostic t=0.00 → EM
  0.4900) but it would raise the wrong-answer rate — against the paper's
  stated first objective (reduce hallucination). **theta_abs is NOT an
  improvement lever for this phase.** Recorded as a trade-off, not a fix.

### Bonus — the 30 model-unknown rows

- Reader refuses from hop 0; 0/30 had any hop produce a real answer.
  Step 3 prompt variants already failed their gate. No mechanism is
  proposed for this population in this phase.

## Pre-registered hypotheses (written 2026-11-11, before any new run)

Judged on **Dev-100 BM25** (the tuning split), one OpenSpec change per
mechanism, in order. Each gate is a smoke test, not a verdict. The improved
system gets **one** Test-400 confirmation at the end of the phase; Phase 3
follows that confirmation.

### H12 — Contested-claim resolution at the final read (primary)

**Claim:** when the final graph holds ≥2 supported answer-bearing claims
with different answers, a contested-resolution step — a re-read grounded on
the competing claims, choosing by evidence rather than by draft agreement —
raises EM on Dev-100 BM25 vs the tuned baseline at ≤ +0.5 calls/Q.
**Target population:** the 53-row pattern (gold in claims, wrong supported
claim chosen). **Criterion:** Dev-100 EM gain ≥ +0.02 with calls/Q within
+0.5 of baseline; the mechanism must fire on the contested rows and fix
more than it breaks on them (net + on triggered rows).

### H13 — Extraction recall (second pass over the hop-0 pool)

**Claim:** a second extraction pass over the hop-0 pool raises the
gold-in-claims rate among full-recall wrong rows on Dev-100 BM25 vs the
tuned baseline, without lowering EM.
**Target population:** the 33-row pattern (gold retrieved, never claimed).
**Criterion:** gold-in-claims rate among full-recall wrong rows rises vs
the tuned dev baseline (0.333 on the step-2 dev set), EM does not fall.

### H14 — Eager SC (dev replication of the Test-400 FP-control direction)

**Claim:** making SC eager (`gate_sc_behind_fast_path=false`) reproduces the
FP-control direction on Dev-100 BM25: EM gain vs the tuned baseline at
≤ +1.0 calls/Q.
**Circularity note (read before judging):** the direction was observed on
Test-400 first (FP-control 0.4675 vs tuned 0.4500). Dev is therefore a
**replication check**, not a fresh discovery, and the Test-400 FP-control
number is already known — it cannot be re-judged. If H14 replicates on
dev, the mechanism enters the improved system, and the *system as a whole*
gets its one fresh Test-400 confirmation. If it does not replicate on dev,
the mechanism is dropped.

## Order of work

1. H12: OpenSpec change → tests → implementation behind a flag → Dev-100
   BM25 A/B vs the tuned baseline.
2. H13: same lifecycle, on top of whatever H12 leaves.
3. H14: same lifecycle (config-only: `gate_sc_behind_fast_path=false`).
4. Freeze the improved config; **one** Test-400 confirmation (tuned-improved
   vs fresh IRCoT, same pre-registered verdict shape as §4.2); then Phase 3.

## What this phase does NOT do

- No tuning against Test-400. Test-400 rows above are diagnosis only; no
  mechanism is selected because its Test-400 number is higher.
- No theta_abs change (see the abstention note above).
- No v1 substitution: the tuned system stays the base, per the
  pre-registered Phase 2 rule. If the improved system beats v1 on the
  confirmation run, that is reported as a result, not used to pick the
  system post-hoc.
