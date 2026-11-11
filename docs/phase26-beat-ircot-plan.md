# Phase 2.6 — Beat-IRCoT round (pre-registered 2026-11-11)

User direction 2026-11-11 15:44 IST: make the paper/research work good —
a model that reduces hallucination and beats IRCoT first, then
Adaptive-RAG. Approach choice is the assistant's ("whatever you do I
don't care"). This round is the response. Old verdicts stay frozen
(HARKing rule); H15–H16 are new claims about new mechanisms, written
BEFORE any new run.

## Where we stand

- Tuned system, Test-400 BM25: EM 0.4500 vs IRCoT 0.4225, dEM +0.0275,
  McNemar p=0.1608 — INCONCLUSIVE. Wrong-answer rate 0.4495 vs 0.4566 —
  a tie (H11). The improved system (tuned + contested H12 + eager SC
  H14) is frozen but NOT yet confirmed on Test-400.
- Adaptive-RAG is at EM 0.4275, ~tied with IRCoT at far fewer calls
  (1.68 vs 2.48 calls/Q). Beating IRCoT on EM almost certainly beats
  Adaptive-RAG on EM too — but Adaptive-RAG stays cheaper, so the
  paper must not claim a cost win over it. The claim is accuracy +
  hallucination reduction, at a stated cost.
- What "beaten" means (pre-registered): on the one Test-400
  confirmation at the end of this round, improved system EM > IRCoT EM
  AND paired McNemar p < 0.05, with the wrong-answer rate down vs
  IRCoT. Roughly: IRCoT is at 0.4225, so the system needs ~0.475+
  (about +20 net rows on N=400) for significance.

## Headroom (measured from stored tuned Test-400 rows, no live calls)

Diagnosis (`scripts/diagnose_phase25.py` definitions: `gold` = gold
answer, `answer` = final answer, claims across all hops, wrong rows =
em 0, answered, recall 1.0):

- 53 gold-in-claims wrong rows (full-recall). 34/53 have the final
  answer inside a WRONG supported claim — the system is confidently
  wrong, and the gold evidence is in the graph.
- Gold evidence out-supports the wrong answer on 24/53 rows
  (max-eff over supported claims, gold > wrong; 25 ties, 1 wrong-higher,
  3 gold in no supported claim). So the information to fix ~half the
  target rows is already in the graph with higher support.
- A naive pick over answer-bearing claims only fixes 4/53 — the
  answer-bearing flag follows the draft, and on 32/53 rows the gold is
  in NO answer-bearing supported claim. The mechanism must look at ALL
  supported claims, not just answer-bearing ones.
- Gold is in the top-3 supported claims by eff on 48/53 rows, top-5 on
  50/53. A re-read grounded only on the top-k supported claims has the
  gold evidence in front of it almost every time.
- Trigger "draft not in top-3 supported claims by eff" fires on 24/53
  target rows and only 39/180 correct rows (top-5: 21/53 and 34/180) —
  selective enough to bound the break risk. The dev A/B measures the
  actual break rate; the gate requires fixes > breaks on triggered rows.

## Order

0. **Confirmation first** (already planned, needs the Groq key):
   improved system vs fresh IRCoT on Test-400, §4.2 verdict shape.
   This is the baseline this round must beat.
1. **H15** — support-ranked final re-read (below).
2. **H16** — verifier threshold sweep (below).
3. One Test-400 confirmation of the final system vs fresh IRCoT.
   Then Phase 3 with that system.

## H15 — support-ranked final re-read

- **Claim:** when the final draft is not supported by the top-3
  supported claims (by eff), a re-read grounded ONLY on those top-3
  claims raises Dev-100 BM25 EM ≥ +0.02 vs the improved-system
  baseline at ≤ +0.5 calls/Q, and fixes more triggered rows than it
  breaks.
- **Mechanism:** at the final read, rank supported claims by eff.
  If the draft (normalized) appears in none of the top-3, run one
  extra LLM call presenting ONLY those top-3 claims and asking for the
  answer from them; replace the draft only on a non-unknown reply.
  Behind a flag (default off); flag-off runs byte-identical.
- **Gate (dev smoke test, paired fresh baseline):** dEM ≥ +0.02,
  dcalls ≤ +0.5, fixes > breaks on triggered rows. Same lifecycle as
  Phase 2.5: diagnose → OpenSpec change with Threats → tests first →
  flag → Dev-100 BM25 A/B.
- **Why this and not a pure pick:** the pick is the LLM, not a string
  rule — the top-1 supported claim does NOT contain gold on 100/180
  correct rows, so taking the top claim's answer would break correct
  rows. The re-read lets the reader choose among the top-3, where gold
  sits on 48/53 target rows.

## H16 — verifier threshold sweep

- **Claim:** the NLI verifier's thresholds (theta_s / theta_c, both
  0.5, never tuned) are the reason gold claims stay out of the
  supported set (H2: supported recall 0.60, macro-F1 0.6825 < 0.70).
  A sweep on a claim-level eval built from dev traces finds thresholds
  with macro-F1 ≥ 0.70 AND supported recall ≥ 0.70 on held-out claims
  — the same bar H2 missed — and the winning thresholds do not lower
  Dev-100 EM in the A/B.
- **Eval construction (pre-registered):** claims from the improved
  system's Dev-100 traces, labelled by matching claim text against the
  question's gold supporting facts from the manifest (supported if the
  claim's text matches a gold fact, contradicted if it matches a
  distractor fact that contradicts the gold — operationalised in the
  OpenSpec change; the 60-pair H2 set is kept as a second check, not
  the gate). Thresholds are chosen on a dev split, judged on a held-out
  split of the same eval — never on Test-400.
- **Gate:** the chosen thresholds pass the eval bar AND the Dev-100
  BM25 A/B (improved + new thresholds vs improved baseline) has
  dEM ≥ 0 at ≤ +0.2 calls/Q (thresholds cost no extra calls, so the
  cost leg is a guardrail, not a budget).

## H17 (candidate, not yet written)

Calibrated abstention: replace the abstention signal with the step-7
logistic predictor's P(final correct) — AUROC 0.6775 vs c0's 0.5915 —
targeting the H11 wrong-answer rate. To be written as a full hypothesis
BEFORE any run touching it, only if H15+H16 leave H11 a tie. It is NOT
part of this round's pre-registration.

## Rules

- No tuning against Test-400 (diagnosis only, as in Phase 2.5).
- theta_abs stays 0.50 (not a lever — would raise the wrong-answer rate).
- No v1 substitution; the improved system stays the base.
- One OpenSpec change per mechanism; Dev-100 BM25 A/Bs, gates as smoke
  tests; one Test-400 confirmation at the end, judged on its own.
- If the confirmation is still inconclusive, the paper reports it
  straight and leads with H6 + the honest negatives — no new mechanism
  is bolted on to escape the verdict without a new pre-registered round.
