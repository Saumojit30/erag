# Publication-Ready Plan for ERag

**Written:** 2026-11-10. **Status:** plan document — not a manuscript.
**Question it answers:** can the current work be published, what is it really,
does the current plan hold, and what must change for a Springer-conference
(or journal) paper?

**Bottom line up front:** yes, it can be published at a mid-tier Springer
conference — the evidence core is real and the mechanism result is strong.
Not yet, and not at a flagship venue on the current plan. The topic does not
need to change. The plan needs five additions (one reframing, one ablation
set, stronger baselines, a cost-analysis upgrade, and Phase 3 as already
decided) plus honest disclosure of two weaknesses. Earliest realistic
submission: **February 2027**. Every December 2026 deadline is out of reach
on the current pace — that is stated plainly in §3.9, not hidden.

---

## 1. What I think the work is

### 1.1 The work in one paragraph

ERag is a retrieval-augmented generation system that verifies its own
reasoning with natural-language inference and spends LLM effort only where
the evidence demands it. Each question produces a belief graph of
NLI-verified claims; the system retrieves further only when a claim gap
remains, samples self-consistency only until the answer stabilises, skips
work entirely when the first retrieval already supports the answer, and
abstains rather than guessing when confidence is low. The newest piece is a
learned continuation policy: a small logistic regression on hop-0 features
that replaces the hand-set stop/continue threshold. The research question,
from the Nov 4 report, is: *"Can evidence-aware uncertainty estimation and
claim-level verification guide adaptive retrieval in multi-hop RAG, improving
answer reliability at a reasonable computational cost?"* The user's stated
objective is **reduce hallucination first, reduced LLM cost second**.

### 1.2 The contribution, in one sentence

**An adaptive control layer for multi-hop RAG — Fast Path, sequential
self-consistency, gap-driven hops over NLI-verified claims, abstention, and
a learned continuation policy — that beats a fixed interleaved
retrieve–reason baseline on accuracy while using about half the LLM calls
of the non-adaptive system, with the gain concentrated exactly where the
first retrieval was incomplete.**

Supporting points:

- **Mechanism, not just a score.** H6 shows all of the gain over IRCoT
  sits in the hop-0-incomplete subset (+11.5 EM points, n=192); zero gain
  where retrieval was complete (n=208). The adaptivity does what it claims.
- **A cost–accuracy frontier, not a single number.** The paper reports
  calls/question AND wrong-answer rate for every system: the tuned system
  dominates Balanced on both and beats IRCoT on accuracy with abstention.
- **A learned decision boundary, not only calibrated constants.** Step 7
  replaces the hand-set hop-0 rule with a model trained on dev traces
  (retrain after the hop-0 definition fix; Gate B passed live).

### 1.3 What the work is NOT — say this in the paper, or a reviewer will

- **Not a new retriever.** BM25 and MiniLM are off-the-shelf; the work is
  the control layer around them. The multi-retriever drop is a disclosed
  limitation, returning as a frozen-system check in Phase 3.
- **Not a new LLM, and no LLM finetuning.** The model is Groq
  `openai/gpt-oss-20b`, used as a black box. "Finetune" in this project
  means the ERag architecture.
- **Not test-time training.** The Titans borrowing is the surprise-gated
  write *idea* only. ERag's BeliefMemory is symbolic (verified belief
  strings, no gradients, no test-time training). The paper must say exactly
  that, never imply gradient-based test-time learning.
- **Not a new reasoning model.** The hop loop is IRCoT's structural
  template; ERag replaces free-text CoT with a belief graph over
  NLI-verified claims and the fixed step cap with confidence/gap/EIG-driven
  stopping plus abstention.
- **Not a comparison against the current state of the art.** IRCoT is a
  2023 baseline (GPT-3 era). The paper must not claim to beat "SOTA RAG";
  it beats a fixed interleaved baseline and a non-adaptive ablation. §3.3
  addresses the baseline gap.

### 1.4 Paper type and claim structure

- **Type:** empirical systems paper (experiments + ablations + error
  analysis), 12–15 pages in Springer LNCS format. Not a theory paper, not
  a dataset paper, not a survey.
- **Primary claim (H1, confirmatory):** E-RAG beats Standard RAG on answer
  quality (paired McNemar, Holm across H1/H4).
- **Secondary claim (H4, confirmatory):** adaptive retrieval beats the
  no-adaptive ablation at acceptable cost — where "acceptable cost" needs
  the dated clarification (cost per correct answer, see §3.1).
- **Mechanism claim (H6, exploratory, leads the paper):** gains
  concentrate where initial retrieval missed a needed paragraph.
- **Honest negatives reported, not hidden:** H2 (verifier too conservative,
  macro-F1 0.6825 vs 0.70) and H5 (memory null on a cache-confounded test)
  strengthen credibility; a paper that reports only wins reads as
  untrustworthy.

### 1.5 Working title (pick one at manuscript time)

- "Evidence-Aware Adaptive Retrieval for Multi-Hop RAG: Claim-Level
  Verification, Learned Continuation, and the Cost–Accuracy Frontier"
- "Making RAG Spend Where It Matters: Adaptive Retrieval Guided by
  NLI-Verified Claims"
- "Reducing Hallucination in Multi-Hop RAG with Adaptive Retrieval and
  Selective Answering"

---

## 2. Validation of the current plan

### 2.1 What is strong — the plan holds here

- **A real significant result.** TrueAdaptive v1 vs IRCoT, Test-400 BM25,
  frozen systems, 0 cache hits: EM 0.4750 vs 0.4200, F1 0.6192 vs 0.5674,
  McNemar b=38, c=16, p=0.0043. This is the first significant frozen-system
  E-RAG vs IRCoT Test-400 result; the earlier post-hoc re-thresholded
  significance (audit H3) is labelled as such and superseded.
- **A clean mechanism result (H6).** The gain's location is exactly where
  the theory predicts. This is rarer and more persuasive than a bare EM
  win.
- **Pre-registration discipline.** Phase 2's verdict is pre-registered
  (Win/Loss/Inconclusive, McNemar α=0.05); gates are written before runs;
  the step-4 counterfactual acceptance and step-5 supersede are dated
  decisions, not silent edits. Reviewers in this area notice this.
- **Frozen systems, deduped rows, cache hygiene.** The audit remediation
  (cache-key v2, row-level retriever provenance, verify script 10/10) is
  done and committed. The numbers recompute exactly.
- **Honest negatives already in hand.** H2 and H5 as not-supported, with
  causes diagnosed (verifier too conservative on multi-hop claims; E5
  memory test was a cache replay). A paper with diagnosed negatives is
  stronger than one with hidden ones.
- **Tuning is gated and logged.** Every step has an OpenSpec change, a
  pre-registered gate, and a same-day entry in the master plan §12 log and
  the retrospective changelog.

### 2.2 Gaps — what is weak, and what closes each one

| # | Gap | Severity | What closes it | Cost |
|---|---|---|---|---|
| G1 | **Single dataset.** All headline numbers are HotpotQA dev-slice (Test-400 is a held-out *dev* slice, not the official test set). A single-dataset paper is the most common rejection reason in this area. | High — blocks a strong claim | Phase 3 as decided: BOTH 2Wiki and MuSiQue, each BM25 then MiniLM | Weeks of runs; §3.5 |
| G2 | **Single retriever for the headline.** BM25 only on Test-400; MiniLM conditional on inconclusiveness. Reviewers will ask whether the result is a retriever artefact. | High | MiniLM HotpotQA head-to-head (user decision pending) + MiniLM second check per Phase 3 dataset | ~2,500–3,000 calls for HotpotQA MiniLM; §3.3 |
| G3 | **Thin baselines.** IRCoT is 2023. No comparison to a recent adaptive system (Adaptive-RAG's classifier, CRAG's corrective loop) as a *running* baseline — only as related work. | High for flagship; medium for mid-tier | Implement Adaptive-RAG's routing as a baseline, OR report the gap honestly as a limitation with published numbers framed as non-comparable | Days of implementation, or 0 (limitation) — §3.3 |
| G4 | **No component ablation on test.** H4's no-adaptive ablation is planned, but nothing shows *which* adaptive piece carries the gain (Fast Path? SC? EIG gaps?). "Which part matters?" is the first reviewer question. | High | Fast-Path-off and SC-off ablations on Test-400, added to Phase 2 | ~5,000–7,000 calls, 2 runs; §3.2 |
| G5 | **Policy evaluated in-sample.** The learned policy's live Dev-100 test trains on the same 100 questions it is evaluated on (final model on all dev rows). Gate B's agreement check, not the raw EM, is the wiring test — but the paper must disclose this, and Test-400 is the real judge. | Medium | Disclose in the methods (§3.4); do not oversell the dev number; optionally a 70/30 dev split (weak at N=100 — not recommended as the fix) | Writing only |
| G6 | **Tuning decisions on N=100 dev, gates at the floor.** Gate B passed exactly at EM 0.5000; step-2's gate failed on EM by 2 rows (inside ±3-row noise). Dev is a smoke test, not a verdict — the plan already says this, but the paper must too. | Medium | Nothing to re-run; disclose the ±3-row noise band and let Test-400 judge | Writing only |
| G7 | **H5 unresolved.** Memory is implemented and wired but disabled; the only effectiveness test was a cache replay. The paper cannot claim memory helps, and cannot cleanly claim it does not, until step 6 runs. | Medium | Run step 6 (needs the Groq key); then either claim a real result or report "implemented, not effective on the stream instrument" and drop it from the claims | 3 stream arms; §3.7 |
| G8 | **Cost measured in calls, not money/energy.** For a green-AI framing, calls/Q is a proxy. No dollars, no wall-latency comparison on equal footing, no energy estimate. | Medium for GreenAI; low otherwise | Cost-analysis upgrade: $/correct answer, wall latency, estimated energy per correct answer (§3.6) | Small — recompute from stored rows + Groq pricing |
| G9 | **No human evaluation, thin qualitative analysis.** The error analysis is automated (recall/claim-based). No error taxonomy with examples, no human-judged sample. | Low–medium | Add a qualitative error taxonomy (100-row sample, categories + 3–5 worked examples) from stored traces | Half a day of analysis, no new runs |
| G10 | **Venue unconfirmed; manuscript missing; tables/figures stale.** GreenAI-2027's deadline passed (15 Oct 2026). No manuscript exists; `research/tables/` and `research/figures/` are Phase-5-era. | Blocking for submission | Venue strategy (§3.9) + manuscript plan (§3.10) | Writing + regeneration from final results |

### 2.3 Verdict by venue tier

- **Mid-tier Springer conference (LNCS/CCIS/LNNS tier):** publishable
  AFTER G1, G2, G4 and G7 are closed and G5/G6 are disclosed. This is the
  realistic target. The H6 mechanism result + the significant Test-400 win
  + the cost frontier is a credible package at this tier.
- **Flagship venue (top-tier conference or high-impact journal):** not on
  this plan. It would need G3 fully closed (a running recent baseline),
  a larger-scale evaluation (more datasets or a bigger test split), and
  probably a stronger method novelty story. Do not aim here first.
- **Springer journal (e.g. applied-AI / intelligent-systems journals):**
  possible as a fallback — no deadline pressure, but 3–6 months of review
  and a higher completeness bar (G3 and G9 matter more). Only if the
  conference route stalls.
- **What would kill the paper outright:** submitting with only HotpotQA
  (G1 open), or claiming the policy generalises from an in-sample dev
  result (G5 undisclosed), or implying test-time training (the Titans
  wording trap). All three are avoidable by following §3.

---

## 3. What must change — the delta from the current plan

### 3.1 What stays the same (do not re-litigate)

- The topic, the research question, and the two objectives (hallucination
  first, cost second).
- The order: adaptive → architecture tuning → Test-400 → new datasets →
  paper. No BGE now, no LLM finetuning, no manuscript before results.
- Pre-registration, frozen systems, one retriever first, tune on dev /
  judge on test, never select on test.
- Phase 3 as decided: BOTH datasets, 2Wiki first then MuSiQue.
- The push policy (origin only, upstream fetch-only) and transient-only
  credentials.

### 3.2 D2 — Component ablation on Test-400 (highest-value addition)

**What:** add two ablation runs to Phase 2, on the tuned system, Test-400
BM25: (a) Fast Path OFF (every question goes through SC + hops), (b)
sequential SC OFF (fixed 5-sample SC, i.e. the Reference behaviour for the
confidence step). The existing H4 no-adaptive ablation stays as (c).
**Why:** answers "which adaptive piece carries the gain" — the first
reviewer question, currently unanswerable from stored data.
**Cost:** ~2,500–3,500 calls per run, ~1–1.5 h each detached, no new code
(both are config flags). **Paper section:** Ablation study, one table +
one paragraph each. **Gate:** pre-register before Phase 2: each ablation
is reported with EM/F1/calls/Q and a McNemar vs the full tuned system;
no ablation result changes the frozen system.

### 3.3 D3 — Stronger baselines

**What:** (1) HotpotQA MiniLM head-to-head for the tuned system vs fresh
IRCoT (user decision pending — recommended: run it, ~2,500–3,000 calls).
(2) One recent adaptive baseline as a *running* system: implement
Adaptive-RAG's complexity-classifier routing (their paper's method, code
is public) as a baseline on HotpotQA, OR — if that implementation costs
more than ~3 days — report it as an explicit limitation: "we compare
against the published Adaptive-RAG numbers only as context; they are not
directly comparable (different model and setup)".
**Why:** IRCoT-2023 alone invites "why not compare to recent adaptive
RAG?" **Paper section:** Baselines + Limitations. **Decision needed:**
user picks implementation vs limitation framing (see §3.11).

### 3.4 D4 — Policy evaluation honesty (methods disclosure, no new runs)

**What:** the manuscript's methods section states, verbatim in substance:
the continuation policy is trained on all 100 dev questions and its live
Dev-100 test is in-sample by construction; Gate B's agreement check
(dEM −0.0152, dCalls/Q +0.15, within ±0.02/±0.2) is the wiring test, not
proof of generalisation; the policy's real test is the Phase 2 Test-400
run. Also disclose: the retrain (hop-0 `draft_unknown` definition, the
τ=0.30 artifact superseded), the dev ±3-row noise band, and that Test-400
is a held-out dev slice, not the official HotpotQA test set.
**Why:** this is the difference between a credible paper and one a
reviewer rejects for overselling. **Cost:** writing only.

### 3.5 D5 — Phase 3 as decided (already in the plan, now load-bearing)

Both datasets, 2Wiki first then MuSiQue, each BM25 first then MiniLM as a
second check, new hypotheses written before touching either dataset, each
dataset judged on its own pre-registered verdict (McNemar α=0.05). This
closes G1 and G2 together. No tuning on the new test splits. (Master plan
§5 now states the phase boundary, entry conditions, run list and verdict
explicitly — the 2026-11-09 clarification.)

### 3.6 D6 — Cost-analysis upgrade

**What:** recompute cost as dollars per correct answer (Groq pricing for
`openai/gpt-oss-20b`: $0.10/$0.20 per 1M tokens in/out — verify at
manuscript time), wall-latency per correct answer on equal footing, and an
estimated energy figure per correct answer (calls × mean tokens × a
published per-token energy factor, labelled as an estimate). One table:
system × (EM, calls/Q, $/correct, s/correct, est. Wh/correct).
**Why:** the paper's second objective is cost, and the green-AI framing
needs more than calls/Q. **Cost:** half a day of recomputation from stored
rows; no new runs. **Paper section:** Cost analysis + (if GreenAI) the
framing paragraph.

### 3.7 D7 — Resolve H5 cleanly (step 6)

Run the stream A/B (3 arms, fresh namespaces, N=30 fallback). Outcomes:
(a) memory helps → it enters the frozen system and the paper claims a
small memory result; (b) clean null → memory stays OFF, H5 stays NOT
SUPPORTED, and the paper reports "implemented, not effective on the
stream instrument" in one paragraph; (c) instrument too weak (fires
<5/30) → report as under-powered, not a null. Any of the three is
publishable; leaving it ambiguous is not.

### 3.8 D8 — Qualitative error analysis (no new runs)

From stored Test-400 traces: a 100-row taxonomy (retrieval miss /
reader failure / claim-extraction miss / abstention / formatting) with
counts, plus 3–5 worked examples showing the belief graph's role in a fix
and in a failure. This is the material reviewers actually read, and it is
currently missing. Half a day.

### 3.9 D9 — Venue strategy (verified 2026-11-10; re-verify every date at submission)

The work cannot be ready for a December 2026 deadline: Phase 2 and Phase 3
are unrun and the manuscript does not exist. Do not chase one.

| Venue | Dates | Proceedings | Deadline | Fit / verdict |
|---|---|---|---|---|
| GreenAI-2027, Sri Sri Univ. Cuttack | Jan 29–30, 2027 | Springer AISSE | **15 Oct 2026 — PASSED** | The user's first choice; missed. Do not submit. |
| ICAISC 2027, Zakopane | Jun 20–24, 2027 | Springer LNAI | 15 Nov 2026 | Too soon. |
| NEXAI 2027, Gurugram | Mar 4–5, 2027 | Springer LNNS | 22 Nov 2026 | Too soon. |
| ICSSG-AI 2027 | Mar 11–13, 2027 | Springer AI-SSE | 17 Nov 2026 | Too soon. |
| ICIAI 2027, Bangkok | Apr 26–29, 2027 | Springer | 10 Dec 2026 | Not realistic on current pace. |
| IEA/AIE 2027, Naples | Jul 20–22, 2027 | Springer LNCS/LNAI | 15 Dec 2026 | Only if Phase 2/3 compress — do not plan on it. |
| ICHCSC 2027, Jaipur | Feb 12–13, 2027 | Springer SIST | 19 Dec 2026 | Not realistic. |
| **ICAIIT 2027, Junagadh (Gujarat)** | Sep 2027 | Springer LNNS (proposed) | **Feb 2027 (first deadline)** | **Realistic target.** India-based, AI track, timeline fits. 1st edition — weaker prestige, higher acceptance odds. |
| HITA 2027 | TBD | TBD | Submissions open soon | The other SSU possibility — watch for the CFP; venue TBD. |

**Strategy:** target the February 2027 deadlines (ICAIIT first) and keep
scouting mid-2027 Springer conferences after Phase 2. If the user wants
the Sri Sri University venue specifically, HITA 2027 is the only live
option — its CFP must be checked before committing the manuscript to an
LNCS template. Journal fallback: a Springer applied-AI journal (no
deadline, 3–6 month review) only if the conference route stalls.

### 3.10 D10 — Manuscript plan (structure, tables, figures)

**Format:** Springer LNCS, 12–15 pages incl. references. LaTeX (LNCS
template) — the repo has no manuscript yet; start from the LNCS class,
not from the Nov 4 report's prose.

**Outline:**

1. Introduction — RQ, the two objectives, the frontier framing, the
   headline numbers (tuned Test-400 vs IRCoT + H6).
2. Related work — IRCoT (template + baseline), Adaptive-RAG (thesis
   borrowed, classifier not implemented), CRAG (verification-gating
   borrowed, corrective loop not implemented), DRAGIN (information-need
   timing; RIND/QFS impossible via black-box API), Titans
   ("surprise-gated write idea only"), FlashRAG + others (arrive or
   confirmed out of scope).
3. Method — belief graph + NLI verification, Fast Path, sequential SC,
   gap/EIG hops, abstention, reader grounding, learned continuation
   policy (with the retrain disclosure), memory (if kept).
4. Experimental setup — datasets (HotpotQA dev slice + 2Wiki + MuSiQue),
   retrievers, systems, frozen configs, metrics, pre-registered verdicts,
   the cache/dedupe discipline, the dev ±3-row noise note.
5. Results — Test-400 head-to-head (BM25 + MiniLM), Phase 3 per-dataset
   results, H1–H6 verdicts table, cost analysis (D6).
6. Ablation study — H4 no-adaptive + Fast-Path-off + SC-off (D2).
7. Error analysis — error budget, the two unknown populations, the
   qualitative taxonomy (D8).
8. Limitations — single-model (gpt-oss-20b), dev-slice test set, N=100
   dev tuning, in-sample policy test, no recent running baseline (unless
   D3 implements one), memory unresolved/ineffective.
9. Conclusion.

**Tables to regenerate from FINAL results (current `research/tables/` and
`research/figures/` are Phase-5-era and stale):** main results table
(systems × EM/F1/calls/Q/coverage/selective EM, per dataset × retriever);
H1–H6 verdict table; ablation table; cost table ($/s/Wh per correct
answer); H6 subgroup table. **Figures:** cost–accuracy Pareto frontier;
risk–coverage curve; calibration (reliability diagram, c0); hops/calls
distribution. All regenerated by script from the final result files, not
hand-made.

### 3.11 Revised timeline (from 2026-11-10)

| When | What | Needs |
|---|---|---|
| Nov 2026 | Step 6 stream A/B → gate → freeze tuned config; push (25 commits + master) | Groq key + PAT (the file); step-6 gate as written |
| Nov–Dec 2026 | Phase 2: tuned vs fresh IRCoT Test-400 (BM25) + H4 ablation + Fast-Path-off + SC-off ablations + H1 re-run + Holm; MiniLM HotpotQA if the user says yes | Groq key; hygiene decisions (H2, H4, 3c) BEFORE the runs |
| Dec 2026–Jan 2027 | Phase 3: 2Wiki (prep → BM25 → MiniLM → error analysis), then MuSiQue the same way; new hypotheses first | Groq key; dataset manifests |
| Jan–Feb 2027 | Cost analysis (D6), qualitative taxonomy (D8), regenerate tables/figures, write manuscript (D10) | Final results; missing papers or out-of-scope confirmation |
| Feb 2027 | Submit to the February-deadline target (ICAIIT first deadline, or a scouted equivalent) | Venue confirmed; manuscript complete |

### 3.12 Exit criteria — "ready to submit" means ALL of these

- Phase 1 closed (step 6 judged) + config frozen + everything pushed.
- Phase 2 run and judged by its pre-registered verdict; H1/H4 confirmatory
  status settled (Holm applied if 3c says yes).
- Phase 3 run on both datasets, each judged on its own verdict; both
  reported including any split.
- Ablations (D2) run and reported; cost table (D6) computed.
- Manuscript drafted in LNCS format with the §3.4 disclosures, tables and
  figures regenerated from final results, related work closed.
- Venue confirmed with a live open deadline; submission checklist (page
  limit, anonymity if double-blind, author list) verified against the
  venue's CFP.

### 3.13 Decisions needed from the user

1. **Venue tier:** aim at the February 2027 mid-tier conference target
   (ICAIIT-class), or hold out for a stronger venue later (delays
   submission by months)?
2. **Baseline D3:** implement Adaptive-RAG's routing as a running baseline
   (days of work), or report it as a limitation (no extra work)?
3. **MiniLM HotpotQA:** run it regardless of the §4.3 rule (recommended —
   closes G2 on the home dataset)?
4. **H4 bound:** cost per correct answer (recommended) vs 3× IRCoT latency
   — needed before the Phase 2 ablation runs.
5. **H2 threshold:** confirm 0.70 as-is (recommended) — needed before
   Phase 2.
6. **Decision 3c:** do the confirmatory H1/H4 analyses join Phase 2
   (recommended: yes)?
7. **Missing papers:** supply FlashRAG + others, or confirm them out of
   scope (blocks related work closing)?
