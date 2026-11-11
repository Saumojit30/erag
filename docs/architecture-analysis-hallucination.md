# Architecture analysis: why the current ERag cannot reduce hallucination much further, and what a superior architecture looks like

Date: 2026-11-11. Status: ANALYSIS ONLY — no code changed. Written at the
user's request after the H16 verdict, in response to: "we need to modify
the code not just the simple parameters… why should we not change what we
have thought previously, and make a superior architecture?"

Source of record for the numbers cited: `docs/tuning-master-plan.md` §12,
`docs/hypotheses-current-status.md`, `docs/assumptions-vs-outcomes.md`,
`docs/phase25-improvement-diagnosis.md`, `results/nli_threshold_sweep.json`.
Every code claim below cites a file and the construct, so it can be checked.

## 0. The short answer

The user is right, with one correction. We HAVE changed code in the last
four days (the continuation policy, the memory module, the contested
re-read H12, the support-ranked re-read H15, the second-extraction pass
H13) — but all of those are **additions bolted onto a fixed pipeline
shape**. None of them changed the shape itself. The shape is:

> retrieve → **draft the answer** → sample more drafts → extract claims
> from the draft → verify the claims → maybe re-read → **the draft is the
> answer unless abstention fires**

The answer is produced BEFORE any verification exists, and verification
is advisory: it can veto (abstain) or trigger a re-read in narrow cases,
but it cannot construct the answer. That is the ceiling. The measurements
say so:

- Tuned system Test-400 EM 0.4500 vs v1 0.4750 — tuning bought cost, not
  accuracy. Wrong-answer rate tuned 0.4495 vs IRCoT 0.4566 — a tie (H11).
- H16: the verifier threshold surface is flat (held macro-F1 0.2768 →
  0.2901 across the whole grid; supported recall 1.0 at every setting).
  Thresholds were never the lever.
- H13: a second extraction pass added the wrong claims (gold-in-claims
  rate 0.625 → 0.533, +1.60 calls/Q). More extraction is not the lever.
- H4: the adaptivity claim failed (dEM +0.0150, p=0.405; cost/correct
  9.18 vs 5.25). H7: sequential SC is a cost win only.
- The diagnosis: 107/133 wrong answers had full recall; 53 had the gold
  answer inside an extracted claim and were still answered wrong, 34/53
  because the final answer sits inside a WRONG supported claim, with
  mean confidence 0.94. The system is confidently wrong, not
  under-informed.

A researcher whose assumption fails does not re-tune the same knobs.
They change the architecture and test the new one with new hypotheses
written BEFORE the runs. The HARKing rule survives the architecture
change: old verdicts stay frozen (H1–H16), new mechanisms get new
hypotheses (H18+). What follows is (1) the code-level diagnosis,
(2) the superior architecture, (3) the research program to test it.

## 1. What the code actually does (verified by reading)

### 1.1 The draft anchors everything downstream

`src/systems/erag.py`, `run_erag()`:

- Step 2: the draft is generated first, from the raw pool, temp 0.0,
  with `answer_messages()` (`src/llm/prompts.py`, `ANSWER_SYSTEM`:
  "Answer the question using only the context. Reply with only the short
  answer, no explanation."). No verification exists yet.
- Step 3: self-consistency samples MORE drafts from the same prompt
  (`src/epistemic/confidence.py`, `sequential_consistency()`). SC
  measures agreement among drafts, not grounding. A model confidently
  wrong from context is consistently wrong — this is why c0's AUROC is
  0.5915 (H3) and why the step-7 predictor (0.6775) beats it.
- Step 4: `extract_claims(llm, q, draft, pool, ...)` (`src/epistemic/
  claims.py`, `CLAIM_SYSTEM`: "You list the short factual claims that
  must be true for an answer to be correct"). The claims are derived
  FROM the draft. A hallucinated draft yields hallucinated claims, and
  the one claim marked `"answer": true` is the draft's claim.
- With `claim_strategy: incremental` (frozen config), when the draft is
  unchanged across hops the claims are REUSED (`prev_claims`) — the
  graph is frozen to the hop-0 draft. The draft's first guess locks in
  the entire epistemic state.
- The final line: `answer = "unknown" if (active and abstain) else draft`
  (`erag.py`, Step 12). The draft IS the answer unless abstention fires.

### 1.2 The verifier cannot verify the thing that matters most

`src/epistemic/nli.py`, `NLI.best()`: entailment/contradiction are the
MAX over 2-sentence sliding windows of a single passage. `verify()`
then thresholds those per-passage scores into sup/con lists.

A HotpotQA answer is a 2-hop conjunction by construction ("the director
of X was born in Y" = fact A + fact B). No single 2-sentence window
entails a conjunction. So the answer-bearing claim — the one claim whose
truth decides the answer — is **structurally unverifiable by design**:
it will be "unresolved", or "supported" only spuriously (some window
happens to entail a paraphrase). The measured consequence: H2's
supported recall 0.60, and the 53-row confident-wrong population.

Two further design choices inflate "supported":

- `verify()` status logic: `status = "supported" if be >= (bc - 0.05)
  else "contradicted"`. When evidence is nearly balanced, the claim is
  called supported — a 0.05 margin in favour of support.
- `BeliefGraph.update()` (`src/epistemic/belief_graph.py`): `conf =
  sigmoid(logit(c0) + w_s * Σsup − w_c * Σcon)`. `sup_sum` is a SUM of
  probabilities across passages, not a probability — several weak
  supports add up to high confidence. The frozen config sets w_c = 1.0
  (the module default is 2.0), so contradiction is weighted equally
  with support despite the status logic already favouring support.
- `pre_filter=True` (frozen config) drops passages before scoring using
  a regex subject-entity match (`_extract_subject_entities`). Measured
  in the H16 sweep: it costs supported recall 0.60 → 0.40 on the
  labelled 60 pairs. The verifier's conservatism is partly the
  pre-filter, not the thresholds — which is why H16 was flat.

### 1.3 The belief graph is advisory, never authoritative

`BeliefGraph.gaps()` and `weakest()` drive RETRIEVAL (which claim to
fetch more evidence for), but the graph never AUTHORs the answer. The
only paths by which the graph changes the answer are the final-read
re-reads, and each is narrow:

- `unknown` / `disagree`: fire only when the draft is "unknown" or
  disagrees with the answer claim's text (substring match).
- `contested` (H12): fires only when a supported draft-sourced claim
  contains the draft AND a supported question-sourced claim does not.
- `support_ranked` (H15): fires only when the draft appears in none of
  the top-3 supported claims by eff.

Outside those triggers, the draft stands — including on the 41/53
gold-in-claims wrong rows where no re-read fired. The graph's
`depends_on` edges are declared by the same LLM that wrote the draft,
so weakest-link propagation (`eff = min(conf, parents' eff)`) only
bites when the LLM declares dependencies. The graph measures the
draft's beliefs; it does not constrain them.

### 1.4 The retrieval query confirms the claim instead of testing it

`targeted_retrieve()` with `eig_strategy: direct` (frozen config) uses
the claim text itself as the retrieval query. Querying with a claim
retrieves passages that MATCH the claim — confirmation, not falsification.
The `propose_queries()` path (`eig_strategy: llm`) at least asks for
queries "confirming or refuting the claim", but it is not the frozen
setting. The retrieval loop therefore gathers evidence for the draft's
claims rather than evidence that could overturn them. This is the
retrieval-side version of the same draft-first bias.

### 1.5 Abstention is a confidence proxy, not a grounding check

Step 12 abstains when `ans.eff < theta_abs` (0.5), where `ans =
graph.answer_claim()` — the claim the extractor marked answer-bearing,
i.e. the draft's own claim. So abstention asks "is the draft's claim
weakly supported", not "is the answer entailed by the evidence". The
step-4 diagnosis stands: raising theta_abs abstains 3 correct / 3 wrong
at the margin — a coin flip — because the signal is confidence, not
grounding. H17 (calibrated abstention) is the candidate to fix this,
but it needs a grounding signal, not a better confidence number.

### 1.6 The other components, honestly assessed

- **Self-consistency** (`confidence.py`): measures stability of the
  answer distribution. Useful for cost (sequential stopping) and for
  detecting instability, but it cannot detect a confidently wrong
  answer. It is not a hallucination detector and should stop being
  treated as one.
- **Continuation policy** (`continuation_policy.py`): predicts P(hop-0
  draft correct) from 12 hop-0 features. It is a correctness proxy that
  decides whether to fetch more evidence. It contains NO feature for
  "is the draft entailed by supported claims" — the feature it would
  need for hallucination. Its value is cost control, not truth.
- **Memory** (`systems/memory.py`): symbolic text store, MiniLM
  similarity, surprise-gated writes (c0 < 0.6 or contradiction),
  contradiction override. Measured: fired 1/30 in its live test.
  HotpotQA questions are independent, so cross-question memory has
  almost nothing to carry — the dataset cannot test it. Memory is a
  veto side-channel, never used as evidence for the draft. For the
  paper it is either dropped from the HotpotQA claim or tested only on
  a sequential stream (the planted stream is the only place it can be
  claimed).
- **Retrieval** (`retrieval/index.py`): BM25 top-3 or MiniLM top-3, no
  reranking, no query decomposition, pool capped at 12 titles. The NLI
  cross-encoder is loaded for verification but never used to rerank
  what the reader sees — retrieval ranking and verification are
  disconnected. On the HotpotQA distractor corpus retrieval is easy
  (recall ~0.89), so this is not the current bottleneck; on a pooled
  corpus it would be.
- **Adaptive-RAG router**: decides adaptivity once, up front, from the
  question text. It is a legitimate baseline (H8 tested), not part of
  ERag. Its lesson for the paper: the router sends most questions to
  the weak single-step route — upfront adaptivity from question text
  alone is a weak signal, which is why ERag's per-hop adaptivity was
  the thesis. That thesis (H4) failed on accuracy, so the per-hop
  machinery must earn its keep on grounding, not on cost.

## 2. The superior architecture

Design principle, stated once: **the answer must be entailed by the
evidence, and the system must be unable to output an answer it cannot
derive.** Everything below is a mechanism that enforces some version of
that invariant. None of them is a parameter. All of them are pipeline
changes, because the LLM is a black-box API (Groq): no finetuning, no
logits, no token-level methods (DRAGIN's RIND/QFS are impossible here).
The architecture changes must live in prompts, verification, retrieval,
and the answer space.

### A. Evidence-first answering — invert the pipeline (the big one)

**Change:** retrieve → extract candidate answer-bearing claims FROM THE
PASSAGES (not from a draft) → verify them → compose the answer ONLY
from verified claims. No draft is ever generated before verification
exists. The draft-first order is reversed.

**Why:** it removes the anchor. The measured failure (34/53 wrong rows:
final answer inside a wrong supported claim) exists because the draft
chooses the answer and the machinery then defends it. In the inverted
pipeline there is no draft to defend; the answer is whatever the
verified claims support. H15 is the patch version of this idea (re-read
grounded on the top-3 supported claims); A is the architectural version
(it applies to every row, not just the triggered ones).

**Paper grounding:** the "claim-grounded answering" line; Self-RAG
(Asai et al., 2023) — generate, then critique each segment against
retrieved evidence, and only keep supported segments. The black-box
analogue of Self-RAG's reflection tokens is exactly this: the critic
is a separate model (the NLI verifier), not the generator.

**Cost / risk:** needs an answer-composition step (a prompt that
composes an answer from verified claims, or an extractive pick). Answers
needing synthesis across claims need a composition prompt that is
restricted to verified claims. If no verified claim answers the
question, the system abstains — which is correct behaviour for the
hallucination objective, and costs EM on the rows the current system
guesses right.

### B. Compositional verification — verify the conjunction, not the parts

**Change:** the answer-bearing claim is verified against the JOINT
evidence of its supporting claims, not per-window. Concretely: for the
answer claim, collect the sup passages of its `depends_on` claims,
concatenate them as one evidence block, and run NLI on the block; or
verify the pair (claim A ∧ claim B) directly. The per-window `best()`
call stays for atomic claims; the answer claim gets a joint call.

**Why:** §1.2 — the answer claim is a 2-hop conjunction and is
structurally unverifiable today. The weakest-link propagation is the
right idea executed in the wrong place (it propagates confidences the
LLM declared, instead of verifying the conjunction against evidence).

**Paper grounding:** CRAG (Yan et al., 2024) — evaluate retrieved
documents as correct / incorrect / ambiguous, and act on the evaluation
rather than trusting the retrieval. The joint-verification step is the
"evaluate" half applied to the composition, not just to each document.

### C. Generate–critique–revise loop — a real corrective loop

**Change:** after the draft, a critic grades EACH sentence/claim of the
draft against the evidence (the NLI verifier already does this per
claim). Any unsupported claim triggers one of two actions, chosen by the
critic: (i) targeted retrieval for that claim, phrased to REFUTE it as
well as confirm it (fix §1.4 at the same time); (ii) regeneration of the
draft with the unsupported claim removed. If after the loop no claim
supports an answer, abstain. The loop replaces the narrow re-read
triggers (unknown/disagree/contested/support-ranked) with one general
mechanism: the critic's verdict feeds back into generation.

**Why:** today the critic's verdict only feeds retrieval target
selection and the abstention threshold. The draft is never revised on
the basis of a failed verification — the re-reads are one-shot patches
that fire on 25/100 rows (H12) or 24/53 target rows (H15 trigger).
A loop makes verification load-bearing instead of advisory.

**Paper grounding:** CRAG's retrieve → evaluate → correct loop (the
corrective action is the part ERag never implemented — the master plan
records this: "corrective loop NOT implemented"); DRAGIN (Su et al.,
2024) — trigger retrieval at the moment of information need, detected
from the model's uncertainty, rather than on a fixed schedule. The
black-box version of DRAGIN's trigger is the critic's per-claim
verdict: retrieve when a specific claim is unverified, not when a hop
counter says so.

### D. Evidence reranking with the cross-encoder already in the codebase

**Change:** use the loaded NLI cross-encoder to rerank the pool before
the reader sees it, and to score passages for the answer claim. The
reader currently sees BM25 order; the verifier sees the same pool. A
rerank step aligns what the reader reads with what the verifier trusts.

**Why:** cheap (no new model, no new data), and it attacks reader
grounding directly — the reader's answer is conditioned on the order
and content of the pool. It also gives the targeted-retrieval step a
ranked evidence list instead of a title set.

**Paper grounding:** standard reranking practice in RAG; CRAG's
evaluator used as a reranker rather than only as a filter.

### E. Extractive answering — restrict the answer space to verified claims

**Change:** the final answer must be the text (or a span) of a
supported claim in the graph. The reader is not allowed to invent an
entity; it picks among verified claims. Fallback when no supported
claim answers the question: abstain.

**Why:** the strongest hallucination control available without a new
model. It converts "the model invented an entity" into "the model
picked the wrong verified claim" — a strictly smaller error class, and
one the H15 ranking can then optimise directly (the ranking already
exists; E makes it the answer rule instead of a re-read trigger).
HotpotQA answers are entities (names, dates, places), so extractive
answering is viable on this dataset; it would not be viable on
abstractive QA, which is a stated limitation, not a hidden one.

**Cost / risk:** fails on questions whose answer needs synthesis across
claims (the composition case in B). The honest design is E for the
answer pick + B for the composition check: the answer is a verified
claim, and when the question needs two facts, the pair is jointly
verified.

### F. Grounded abstention — abstain on entailment, not confidence (H17, with a mechanism)

**Change:** replace the abstention signal with P(answer entailed by
supported claims), predicted from GRAPH features: max eff among
answer-bearing supported claims, whether the draft appears in the top-k
supported claims, number of contradicted claims, whether the answer
claim is jointly verified (B). The step-7 logistic predictor is reused
as the carrier, but its features become grounding features. This is H17
written as an architecture change rather than a threshold change.

**Why:** §1.5 — the current abstention signal is confidence, and the
step-4 diagnosis shows it is a coin flip at the margin. The wrong-answer
rate (H11) is the hallucination metric; abstention is the only mechanism
that lowers it without lowering EM, and it needs a grounding signal to
work.

### G. Memory as a retriever, or not at all (Titans, properly)

**Change:** if memory is to matter, it must be a first-class retrieval
source with its own recall measured — memory passages ranked alongside
fresh passages, with a recorded hit rate — not a veto side-channel
appended to the verification pool. And it needs a sequential task to be
testable. On HotpotQA it cannot be claimed, period: the dataset's
questions are independent, the write trigger fired 1/30, and the
override is verified 1/1 only "when it fires".

**Paper grounding:** Titans (Behrouz et al., 2025) — test-time memory
with surprise-gated writes. The borrowing so far is the write pattern
only ("surprise-gated write idea only" — the paper must say this).
A real Titans-style memory would store verified claims with embeddings
and retrieve them as evidence in later hops. That is a different system
from the current BeliefMemory, and it needs a sequential benchmark to
demonstrate anything.

### What NOT to do (measured, not opinion)

- **More hops / more context.** Retrieval is not the bottleneck
  (107/133 wrong rows had full recall). The pool cap and max_hops are
  not the lever.
- **Threshold tuning.** H16 proved the surface flat. Do not revisit
  theta_s/theta_c.
- **More SC samples.** SC measures agreement, not truth; sequential SC
  is a cost win (H7), not an accuracy win.
- **A bigger/different LLM.** Out of scope (black-box API, cost, and
  the paper's claim is about the architecture, not the model). The
  architecture must reduce hallucination for a FIXED model — that is
  the research claim, and it is a stronger one.
- **Memory on HotpotQA.** See G.

## 3. The research program (Phase 2.7 — architecture round)

Order by expected value per cost. Each item is one OpenSpec change, one
Dev-100 BM25 A/B against the improved system (fresh namespaces, both
arms re-run fresh, paired), then ONE Test-400 confirmation of the best
combination vs fresh IRCoT. Every gate includes the hallucination leg,
because EM alone can be bought by answering more: **gate = dEM ≥ +0.02
AND wrong-answer rate not up (ideally down) AND dcalls ≤ +0.5/Q.**
New hypotheses H18+ written BEFORE any run touching them; H1–H16
verdicts stay frozen.

| # | Mechanism | Hypothesis | Why first |
|---|-----------|-----------|-----------|
| 1 | A. Evidence-first answering | H18 | Removes the anchor; targets the 53-row failure directly. Highest value, highest cost. |
| 2 | E. Extractive answering | H19 | Cheap, strongest control; can be tested standalone or as the answer rule inside A. |
| 3 | B. Compositional verification | H20 | Fixes the structural unverifiability of 2-hop answers. Medium cost. |
| 4 | D. Cross-encoder reranking | H21 | Cheap, no new model; attacks reader grounding. |
| 5 | C. Critique–revise loop | H22 | Subsumes the four re-read patches into one general mechanism. Medium cost. |
| 6 | F. Grounded abstention | H17 (write fully first) | The hallucination metric (H11) needs a grounding signal; only if H18–H22 leave it a tie. |

Practical note: A and E overlap — test E standalone first (cheap, fast
signal), then A as the full inversion, then combine the winner with B
and D. The final system for the Phase 2.6 confirmation is whichever
combination passes its gates; the confirmation is still ONE Test-400 run
vs fresh IRCoT, judged on EM up AND wrong-answer rate down with
p < 0.05. If the architecture round fails its gates, the paper reports
that straight and leads with H6 + honest negatives — the same rule as
before, applied to a better architecture.

## 4. What this changes about the paper

- The claim becomes architectural, not parametric: "an evidence-first
  RAG pipeline in which the answer is entailed by verified claims
  reduces confident-wrong answers relative to a draft-first pipeline
  at a stated cost". That is a stronger, more interesting claim than
  "tuned thresholds beat IRCoT", and it is falsifiable in exactly the
  way this project already tests things.
- H6 (gains concentrate where first retrieval was incomplete) remains
  the lead empirical result for the current system; the architecture
  round either strengthens it (the inverted pipeline should gain MORE
  where retrieval was incomplete, because it never drafts from weak
  evidence) or refutes the mechanism.
- The honest negatives stand: H2, H4, H5, H7, H8, H10, H13, H16.
  The architecture round does not erase them; it explains them (they
  were all attempts to fix, by tuning, a pipeline whose shape was the
  problem).
- Titans wording stays "surprise-gated write idea only". CRAG's
  corrective loop, if implemented (C), becomes a real borrowing and
  must be cited as such. DRAGIN's information-need timing becomes a
  real borrowing if C uses per-claim triggers.

## Appendix — file map for the claims in §1

- Pipeline shape: `src/systems/erag.py`, `run_erag()` (569 lines).
- Draft first: `erag.py` Step 2 (`llm.chat(answer_messages(...))`).
- SC measures agreement: `src/epistemic/confidence.py`,
  `sequential_consistency()` / `_consensus()`.
- Claims from the draft: `src/epistemic/claims.py`, `CLAIM_SYSTEM`,
  `extract_claims()`.
- Incremental reuse freezes claims to hop-0 draft: `erag.py`,
  `claim_strategy == "incremental"` branch.
- Per-window verification: `src/epistemic/nli.py`, `best()` (2-sentence
  windows), `verify()` (sup/con thresholding, 0.05 support margin,
  pre-filter subject-entity regex).
- Logit update + weakest link: `src/epistemic/belief_graph.py`,
  `update()` (w_s, w_c; `eff = min(conf, parents)`).
- Draft is the answer: `erag.py` Step 12,
  `answer = "unknown" if abstain else draft`.
- Re-read triggers are narrow: `erag.py`, `ground_final_read` block
  (unknown / disagree / contested / support_ranked).
- Retrieval confirms the claim: `erag.py`, `targeted_retrieve()`,
  `eig_strategy == "direct"` → query = claim text.
- Abstention is confidence: `erag.py` Step 12, `ans.eff < theta_abs`.
- Reader prompt never asks for a citation: `src/llm/prompts.py`,
  `ANSWER_SYSTEM` / `GROUNDED_ANSWER_SYSTEM`.
- Memory write gate + read path: `src/systems/memory.py`, `write()`
  (surprise gate) / `read()` (top-3 by MiniLM similarity).
- Retrieval has no rerank: `src/retrieval/index.py`, `Retriever.search()`
  / `BM25Retriever.search()` (top-k, no reranking stage).
- Frozen config: `configs/erag_trueadaptive_improved.yaml`
  (w_s 1.0, w_c 1.0, theta_abs 0.5, max_hops 2, max_claims 8,
  memory OFF, `eig_strategy: direct`, `post_hop_resample: never`).
