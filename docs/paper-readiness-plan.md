# Paper-readiness plan — ERag

Date: 2026-11-09. Branch: `trueadaptive`, HEAD `7872b24` (16 commits ahead
of origin, unpushed). Companion documents: the master plan
(`docs/tuning-master-plan.md`, the pre-registered record for Phase 2),
the hypotheses status doc (`docs/hypotheses-current-status.md`), the
retrospective changelog (`docs/retrospective-changelog.md`).

This file is the audit of where the paper stands and the ordered list of
work left to make it ready. It was written because the user asked for a
rigorous audit of the current plan before the paper work starts.

## 1. Audit verdict

**The evidence core is real, and the paper is writable — but it is not
ready, and the plan documents have drifted from reality.**

What is solid (verified against stored files/commits, not memory):

- TrueAdaptive v1 vs IRCoT on Test-400 is significant (EM 0.4750 vs
  0.4200, McNemar p=0.0043), fresh systems, all live calls.
- H1 SUPPORTED (interim, v1), H6 SUPPORTED strongly — the mechanism
  result (all gain in the hop-0-incomplete subset, ΔEM +0.1146) is the
  paper's lead.
- H2 NOT SUPPORTED (narrow miss), H5 NOT SUPPORTED on retrieval
  reduction (and the E5 test is now known to be cache-confounded —
  uninformative, not a real null), H4 NOT TESTED on Test-400. An honest
  scoreboard: 3 supported, 2 not, 1 untested.
- The audit remediation is complete (verify script 10/10), the OpenSpec
  trail is clean (validate 9 passed, 0 failed), and every tuning step has
  a gated, committed record.
- The step-7 retrain (commit `7872b24`) fixed a real definition bug
  (`draft_unknown` was the final draft, not the hop-0 draft) and Gate A
  re-passed with margin (sim EM 0.5152, calls/Q 3.92, τ=0.05).

What is NOT ready — the gaps, in order of blocking power:

1. **Phase 1 is unfinished.** Step 6's stream A/B has never run; step 7's
   wiring (B.1) is in flight, its live A/B and Gate B are pending; the
   frozen tuned config does not exist.
2. **Phase 2 has not run.** No Test-400 confirmation of the tuned system,
   no H4 ablation, no H1 confirmatory re-run, no Holm. The paper's
   headline numbers are still v1's.
3. **Phase 3 has not started.** No dataset chosen, no manifests, no
   baselines.
4. **No manuscript exists.** No abstract, introduction, or conclusion
   text. Related work cannot close (FlashRAG + papers not supplied).
5. **No venue is confirmed.** The user said Springer at Sri Sri
   University, Cuttack — but the likely match (GreenAI-2027) had a
   full-paper deadline of 15 Oct 2026, already passed when checked
   2026-11-09. No backup venue list exists.
6. **Three hypothesis-hygiene items are open** and each has a deadline
   (they must be settled BEFORE the run they affect): the H2 0.70
   threshold (dated confirmation), the H4 3× latency bound (dated
   clarification — as written it is unmeetable), and open decision 3c
   (whether the confirmatory H1/H4 analyses join Phase 2).
7. **The plan documents are stale.** The audit found the master plan
   and the status doc contradict current reality in at least eight
   places (§2 below). A paper built from a stale plan will misstate its
   own methods.
8. **Nothing is backed up remotely.** 16 commits on `trueadaptive` and
   the master `.mailmap` commit are unpushed. The paper's evidence lives
   on one VM.

## 2. Audit findings — where the plan documents are wrong

Each finding names the file, the stale/wrong text, and the correction.
Fixes for F1–F4 were made in the same commit as this file; F5–F8
were fixed in a follow-up commit the same day (status doc §2/§3
rewritten to current reality; master plan §2.1 H5 cache-confounding
note, §10 hypothesis pointer, §2.3/§11 branch state and untracked
list refreshed). All eight findings are now closed.

- **F1 — master plan §2.1, step 2: "proposed, not built".** Wrong. Step 2
  was built, A/B'd, gated 3/4, kept by user decision, and archived
  (commits `8c9f25e`, `c062baf`). Correction: step 2 DONE.
- **F2 — master plan §2.1/§3.7/§12 and status doc §2: step 7 records
  only the original Gate A pass (marginal, τ=0.30, sim EM 0.5000).**
  The retrain (commit `7872b24`) superseded it: Gate A re-check PASS
  with margin (τ=0.05, sim EM 0.5152, F1 0.6238, calls/Q 3.92, OOF
  AUROC 0.6775). The `d0fb457` artifact is superseded and must never be
  used for wiring. Correction: §3.7 and §12 record the retrain; the
  changelog step-7 entry is amended in the same commit as this file.
- **F3 — master plan §4.1: the Phase 2 system list says "all gated
  tuning steps (1–5) plus the memory decision from step 6".** It omits
  step 7 (the learned continuation policy) and the frozen-config list
  omits `erag.continuation_policy`. Correction: §4.1 is amended by a
  dated note (allowed — no Phase 2 result has been seen) to include
  step 7's outcome in the tuned system and its artifact in the frozen
  config. The amendment must land BEFORE the Phase 2 run.
- **F4 — master plan §6 and §9 #6: "Springer was the forwarded prompt's
  suggestion, not a decision" / venue undecided.** Wrong. The user
  stated (2026-11-09) the venue is a Springer conference at Sri Sri
  University, Cuttack — NOT IEEE. The forwarded prompt is not the
  source of the Springer choice. Correction: §6 and §9 record the
  user's statement, plus the GreenAI-2027 deadline fact (passed
  15 Oct 2026) and the open question of which SSU conference.
- **F5 — status doc §2: "Step 2 — NOT BUILT", "Steps 3–5 — planned,
  not designed", step-4 decision "still open".** All wrong now (steps
  3, 4, 5 are closed; step 4's decision was made 2026-11-09). The doc's
  header says HEAD `348735c`. Correction: rewrite §2's tuning
  progress when step 7 closes (work item W1.6).
- **F6 — master plan §2.1 H5: "NOT SUPPORTED on retrieval reduction
  (E5 identical EM, 0 calls saved)".** True but incomplete: the E5 test
  is now known to be cache-confounded (mem arm served cache_hits ==
  llm_calls on 30/30 rows), so the verdict rests on an uninformative
  test, not a real null. Correction: the H5 line carries the
  cache-confounding note, and H5 is revisited with a dated note after
  step 6 (work item W1.5).
- **F7 — master plan §10: "the hypothesis in §3.6 is inferred from code
  and repo docs".** Stale: the hypothesis now comes from the Nov 4
  report (§2.1), and §3.6 is step 6, not the hypothesis. Correction:
  reword when §2 is corrected (W1.6).
- **F8 — master plan §11: untracked list ("docs/, openspec/project.md")
  and §2.3 branch state ("never pushed").** Stale: most of `docs/` is
  committed, `openspec/project.md` is committed, and the branch is 16
  commits ahead of origin. Correction: refresh §2.3/§11 with the
  push (W5.1).

## 3. The work — ordered

Work items are ordered by dependency. A `→` means "unblocks". Items
marked **USER** need a user decision or supply (key/token/file/choice)
before they can start or finish. No item is started before its
dependency is verified, and no gate is re-judged after its result is
seen.

### W0. Close out the retrain (already done except the paperwork)

- W0.1 — Retrain committed (`7872b24`). DONE 2026-11-09.
- W0.2 — B.1 wiring re-spawned with the corrected brief (hop-0
  definition + the two secondary clarifications: CONTINUE on a
  fast-path row picks the weakest claim; policy governs at hop 0
  under `no_conf`). In flight. → W1.1.

### W1. Finish Phase 1 (tuning) — the tuned system must exist before anything else

- W1.1 — Step 7 B.1/B.2: wire the policy, verify (suite + feature
  agreement), commit. Then C.1 live Dev-100 A/B (needs a Groq key,
  transient), D.1 Gate B (live EM ≥ 0.5000, live calls/Q < 4.65,
  within ±0.02 EM / ±0.2 calls/Q of the simulation), D.2 commit,
  E.1 archive with `-y`, E.2 plan/status updates incl. the H3 note.
  → W1.4, W2.1.
- W1.2 — Step 6 C.1 stream A/B (3 arms, fresh namespaces, N=30
  fallback, fire-rate floor ≥5/30; runs on the post-step-7 tuned
  system if the policy passes Gate B, else post-step-4). Needs a Groq
  key, transient. Then C.2 tripwire check FIRST, D.1 gate, D.2 commit,
  E.1 archive, E.2 H5 revisit with a dated note. → W1.4.
- W1.3 — Hypothesis hygiene, all BEFORE the runs they affect:
  (a) dated confirmation of the H2 0.70 threshold (or a stated reason
  for keeping it); (b) dated clarification of the H4 3× latency bound
  (e.g. 3× IRCoT, or cost-per-correct-answer) — as written it is
  unmeetable by any multi-call system; (c) decision 3c — whether the
  confirmatory H1/H4 analyses join Phase 2 (H4 needs its own Test-400
  ablation run, prepared: frozen config + `erag.ablate=[no_adaptive]`,
  namespace `test_noadaptive_v1_bm25`, ~20–30 min). **USER** for (a)
  and (c); (b) is a proposal the user approves. → W2.1.
- W1.4 — Freeze `configs/erag_trueadaptive_tuned.yaml`
  (max_claims: 8, unknown_prompt: base, theta_abs: 0.50, max_hops: 2,
  memory on/off per W1.2, continuation_policy per W1.1). Nothing
  changes after freeze without a dated amendment. → W2.1.
- W1.5 — H5 revisit: after W1.2, a dated note in the status doc and
  the master plan revising the H5 verdict (the E5 null was
  cache-confounded; the step-6 result is the evidence now). → W4.1.
- W1.6 — Correct the stale plan documents (F1, F5, F7 + §2.1/§2.3/§11
  refresh) in the same commit as the step-7 close-out, so the plan
  matches reality before Phase 2 starts. → W2.1.

### W2. Phase 2 — Test-400 confirmation (the verdict)

- W2.1 — Dated amendment to master plan §4.1 (F3): include step 7's
  outcome and `erag.continuation_policy` in the tuned system and the
  frozen-config list. Must land BEFORE any Phase 2 run. → W2.2.
- W2.2 — Run the pre-registered Phase 2: tuned system (frozen) vs
  fresh IRCoT, BM25 k=3, N=400, fresh namespaces
  (`test_tuned_v1_bm25`, `test_ircot_v2_bm25`), tuned first then IRCoT,
  detached, checkpoint resume. Needs a Groq key, transient. One run
  per system; no re-runs to chase significance. → W2.3.
- W2.3 — If decision 3c says yes: the H4 Test-400 ablation run and
  the H1 confirmatory re-run on the tuned system, then Holm across
  H1/H4. Needs a Groq key, transient. → W2.4.
- W2.4 — Analysis + verdict: error analysis on the tuned file,
  `scripts/verify_results.py` 10/10, McNemar + the pre-registered
  decision table (Win → tuned is the paper's system; Inconclusive →
  MiniLM Test-400, then report honestly; Loss → revert to v1, report
  tuning as a negative result). Commit results, frozen config,
  analysis. → W3.1, W4.1.

### W3. Phase 3 — new dataset (generalization)

- W3.1 — **USER**: choose 2WikiMultiHopQA (safer comparability) or
  MuSiQue (harder, stronger claim). The deciding question is what the
  paper claims. → W3.2.
- W3.2 — Dataset prep (OpenSpec change): manifests, overlap check vs
  HotpotQA test (zero overlap required), distractor corpus, baseline
  reproduction. → W3.3.
- W3.3 — Frozen baselines on the new dataset (Standard, IRCoT, tuned
  TrueAdaptive; BM25 first), then the head-to-head (tuned vs IRCoT,
  same pre-registered verdict shape as §4.2, dataset named up front)
  and error analysis. No tuning on the new test split. → W4.1.

### W4. Phase 4 — the manuscript

- W4.1 — **USER**: supply the missing papers (FlashRAG + any others)
  or confirm them out of scope (open decision 8). Related work cannot
  close without this. → W4.2.
- W4.2 — Regenerate the paper's tables and figures from the FINAL
  results (`research/tables/`, `research/figures/` are Phase-5-era and
  stale) and recompute the cost analysis on final numbers. → W4.3.
- W4.3 — Write the manuscript (its own OpenSpec change if the user
  wants the same discipline): abstract, introduction, methods (the
  OpenSpec changes are the methods record — each change's
  proposal/design is effectively a methods paragraph with its gate
  result), results, limitations, conclusion. The methods must state:
  the hop-0 `draft_unknown` definition and the superseded artifact
  (the retrain is a methods disclosure, not a footnote); Test-400 is a
  held-out dev slice, not the official test set; the adaptive system
  was tested on one retriever (BM25); dev gates carry ±3-row noise;
  the empty-draft robustness gap and the re-read formatting break.
  Report H2/H5 as not supported and H6 as the lead mechanism. Titans
  wording: "surprise-gated write idea only", never test-time training.
  → W4.4.
- W4.4 — **USER**: confirm the venue. The user stated Springer at Sri
  Sri University, Cuttack (NOT IEEE). GreenAI-2027 (Jan 29–30 2027,
  SSU Cuttack, Springer AISSE) had a full-paper deadline of 15 Oct
  2026 — already passed when checked 2026-11-09. Needed: confirm
  whether GreenAI-2027 is the target (and whether a late/short-paper
  route exists) or pick another SSU Springer conference with an open
  deadline (HITA 2027 was a candidate: submissions open soon, venue
  TBD). Re-verify every deadline at submission time. A shortlist of
  Springer conferences with open deadlines is a separate, small piece
  of work on request.

### W5. Housekeeping (do early — it protects everything above)

- W5.1 — Push `trueadaptive` (16 commits ahead, HEAD `7872b24`) and
  master `88f2512` (.mailmap) to `Saumojit30/erag`. Needs a fresh
  GitHub token, transient only. Never push to ManojAdapakala/ERag
  (fetch-only, push URL `no_push`). **USER** supplies the token.
  Do this as soon as the step-7 close-out lands — the paper's evidence
  should not live on one VM.
- W5.2 — Keep the plan documents current: every completed experiment
  gets a §2 entry in the retrospective changelog the same day it is
  verified (standing rule), and the master plan §12 log the same day.
  The retrain entry (W0.1) is amended in the same commit as this file.

## 4. What the user is being asked for (all of it, in one place)

1. **Groq key** (transient, pasted when asked) — for W1.1 (step-7 live
   A/B), W1.2 (step-6 stream A/B), W2.2/W2.3 (Phase 2 + H4 ablation).
   Three separate runs; one key can cover them if it is still valid.
2. **GitHub token** (transient) — for W5.1 (push 16 + 1 commits).
3. **Dataset choice** — 2WikiMultiHopQA or MuSiQue (W3.1).
4. **Missing papers** — supply FlashRAG + others, or confirm out of
   scope (W4.1).
5. **Venue confirmation** — GreenAI-2027 or another SSU Springer
   conference (W4.4).
6. **Hypothesis hygiene** — confirm the H2 0.70 threshold; approve the
   H4 bound clarification; decide 3c (W1.3).
7. **MiniLM Test-400** — not required per the agreed rule (BM25 v1
   result is significant); the user has not explicitly confirmed this
   yet. Only matters if Phase 2 is inconclusive.

## 5. What "paper ready" means (the exit criteria)

- Phase 1 closed: all steps gated/archived, tuned config frozen.
- Phase 2 run and judged by its pre-registered verdict; H1/H4
  confirmatory status settled (run or explicitly out, with Holm or a
  stated reason).
- Phase 3 run on the chosen dataset; both datasets' results committed.
- Manuscript drafted with the methods disclosures in W4.3, tables and
  figures regenerated from final results, related work closed.
- Venue confirmed with a live, open deadline.
- Everything pushed to `Saumojit30/erag`; the plan documents match
  reality (no finding in §2 left open).
