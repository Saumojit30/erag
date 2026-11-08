# TrueAdaptive v1 — Test-400 BM25 error analysis

**Source files:** `results/trueadaptive/erag_trueadaptive_test_bm25.jsonl` (deduplicated
by id, keeping the last row: the resume retried 1 failed question, leaving a stale
failed row — 401 lines → 400 questions), `results/ircot_test_bm25.jsonl`,
`results/trueadaptive/erag_trueadaptive_bm25_dev.jsonl`.
**Reproduce:** `.venv/bin/python scripts/analyze_trueadaptive_test400.py`
(no LLM calls, read-only). All EM figures use the repo's `exact_match`.

**Headline (for reference):** TrueAdaptive v1 EM 0.4750, F1 0.6192, 4.78 calls/Q;
IRCoT EM 0.4200, F1 0.5674, 2.54 calls/Q; McNemar p = 0.0043. N = 400, 0 failed.

## Method notes — read before citing any number here

- **`unknown` and `abstained` are different fields. Do not conflate them.**
  `abstained` = the system withheld an answer because `ans.eff < theta_abs` (0.4).
  `unknown` = the final answer text is literally "unknown" — which also happens
  when the reader model itself says "unknown" (40 rows) despite high confidence.
  An earlier draft of this analysis mixed the two and produced wrong abstention
  figures; everything below keeps them separate.
- **The theta_abs sweep is a counterfactual on stored rows** (draft + `answer_conf`
  are stored, so no re-run is needed). **Selection must use the DEV sweep only;
  the TEST sweep is a diagnostic and must never be used to pick a threshold.**
  Picking a threshold on test would be the H3 error all over again.

## 1. Error budget (400 questions)

| Outcome | N | Share |
|---|---|---|
| Right | 190 | 47.5% |
| Wrong (answered) | 133 | 33.3% |
| System-abstained | 37 | 9.3% |
| Model-said-unknown | 40 | 10.0% |

## 2. The two unknown populations

**System-abstained: 37 rows.** `answer_conf` median 0.214, max 0.368 — consistent
with `theta_abs = 0.4`. 17 of 37 have a *correct* draft (repo EM), and 25 of 37 had
full recall. Ceiling for relaxing abstention: +17 questions (+4.25 pts EM) if every
abstained draft were answered — but the threshold admits wrong drafts too, so the
realistic gain is what the sweep shows (§4), not the ceiling.

**Model-said-unknown: 40 rows.** The draft is literally "unknown" at (nearly) every
hop — only 3 of 40 had any hop produce a real answer, and hop 0 was a real answer
in just 2 (0 correct). The reader refuses from hop 0; the hop machinery does not
overwrite a good answer. Yet `answer_conf` median is 0.875 and `c0` median is 1.000:
the confidence system says "confident" while the reader says "I don't know". These
rows burn the full budget (mean 4.78 calls, same as overall) and return nothing.
16 of 40 had full recall. This is a *reader-prompt* failure, not a confidence
failure, and `theta_abs` cannot touch it — the draft IS "unknown".

## 3. Wrong answers: reasoning, not retrieval

Of the 133 wrong answers, **107 (80%) had recall = 1.0** — all gold paragraphs were
in the pool and the answer was still wrong. Only 26 were retrieval misses.

Of the 107 full-recall wrong answers:
- **70 (65%)** — the gold answer appears in some trace claim, but the final answer
  is still wrong. **Reader/graph bottleneck** (the evidence was extracted and then
  misused or overridden).
- **37 (35%)** — the gold never appears in any trace claim. **Claim-extraction
  bottleneck** (the evidence was retrieved but never extracted as a claim).
- Control: on correct rows the gold appears in the claims 185/190 (97%), so the
  containment check is a usable proxy.

**Hops earn their keep:** hop-0 draft EM 0.4050 → final EM 0.4750. Hops fixed 42
questions and broke 14 (net +28). The multi-hop machinery is not the problem.

## 4. theta_abs sweep (counterfactual, stored rows)

| t | DEV EM (selection) | DEV coverage | TEST EM (diagnostic) | TEST coverage |
|---|---|---|---|---|
| 0.00 | 0.5800 | 0.920 | 0.5175 | 0.900 |
| 0.10 | 0.5700 | 0.860 | 0.5025 | 0.873 |
| 0.20 | 0.5700 | 0.850 | 0.5025 | 0.860 |
| 0.30 | 0.5700 | 0.810 | 0.4775 | 0.823 |
| 0.40 (current) | 0.5600 | 0.800 | 0.4750 | 0.807 |

Direction agrees on dev and test (lower threshold → higher EM), but the dev gain
is +1–2 pts at N = 100 — inside the ±10 pt noise bar. **theta_abs is a small,
uncertain lever.** Decide it on the paper's goal, not on this sweep: keep 0.4 if
selective answering is a claim; test t = 0.2 on dev if maximum EM is the goal.
Do not select on test.

## 5. Call tail: expensive and low-yield

54 rows (14%) use ≥ 7 calls and consume 422 of 1,910 calls (22%). Their EM is
0.3333 (vs 0.4750 overall) and 20 of 54 end unknown. Mean calls by hops:
0 → 3.02, 1 → 5.52, 2 → 7.95. The tail is mostly 2-hop questions (38/54) where the
system spends the most and still often fails. This is the most *reliably measurable*
cost lever (calls are measured precisely, unlike EM on dev): e.g. capping SC on hop 2
should save ~100 calls per 400 with small EM risk — to be tested on dev.

## 6. Fast-path SC gate works

86 skipped rows: 2.00 calls, EM 0.5465, 4 unknown. 314 non-skipped rows: 5.54 calls,
EM 0.4554, 73 unknown. The gate correctly identifies the easy questions — higher EM
at a third of the cost. No change indicated.

## 7. TA vs IRCoT pairs

TA-only correct: 38 (mean recall 0.987, mean 6.68 calls, mostly 1–2 hops).
IR-only correct: 16 (mean recall 0.781). When TA loses, it is usually a retrieval
miss. IRCoT ends unknown on 88 rows vs TA's 77.

## 8. The one failed row

Question `5abae499…`: Groq `APITimeoutError` after 6 attempts in the first run;
retried successfully on resume. Transient infrastructure failure, not a system bug.

## Tuning plan (ordered by expected value)

1. **Reader/graph bottleneck (70 rows, 17.5% of test).** Gold is in the claims but
   the final answer is wrong. Candidates: stronger grounding instruction in the
   reader prompt, claim ranking/selection before the final read, or extra SC samples
   on low-confidence answers. Biggest EM lever that needs no new retrieval.
   Measure on dev: EM (guardrail) + calls.
2. **Claim extraction (37 rows).** Gold retrieved, never claimed. Candidates:
   `claim_strategy` incremental → exhaustive on hop 0, lower NLI thresholds
   (`theta_s`/`theta_c`), or raise `max_claims` above 5. Measure on dev.
3. **Model-unknown reader behavior (40 rows).** Needs a *live* dev experiment —
   nothing stored can estimate it, since the drafts are all "unknown". Candidates:
   soften/remove the "say unknown" instruction, or gate the reader's "unknown" on
   `c0` (only allow it when the graph is also unconfident). Even a 50% recovery is
   +5 pts EM, but the value is unmeasured until the experiment runs.
4. **theta_abs.** Dev sweep says t = 0.0–0.3 gains +1–2 pts on dev (noise). Decide
   by the paper's goal (selective answering vs max EM); if changed, test on dev and
   confirm once on test. Never select on test.
5. **Call-tail cap (cost lever).** Cap SC on hop 2 (e.g. M = 1, or skip SC when `c0`
   is very low — those answers are likely wrong/abstained anyway). Saves ~100 calls
   per 400; verify EM on dev (calls are precise, EM is not).
6. **Closed-book gate (v2, deferred).** NOT indicated by this analysis: retrieval
   is the bottleneck in only ~62/400 rows, and hops help net +28. Keep v2 as a cost
   lever for later, not an accuracy lever now.

## What not to do

- Do not tune any threshold on Test-400 EM. Dev is the selection set; test is the
  judge, run once per tuned config.
- Do not treat the 77 "unknown" rows as one population. 37 are system abstentions
  (theta_abs), 40 are reader refusals (prompt) — different fixes, different files.
- Do not "fix" the call tail by cutting hop 2. Hops fix 42 and break 14; the tail's
  problem is SC spend on already-lost questions, not hopping itself.
