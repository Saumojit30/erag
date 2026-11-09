# Design: Adaptive-RAG routing baseline (Phase 2 addition)

## The router (exact)

New module `src/systems/adaptive_rag.py`, one function with the same
signature as the other systems:

```python
run_adaptive_rag(item, retriever, llm, cfg, tracker) -> {
    "answer": ..., "pool_titles": [...], "hops": ...,
    "route": "A" | "B" | "C", "route_p": float,
}
```

It classifies `item["question"]` with a small trained classifier
(§Classifier) and dispatches to an existing strategy — no new
retrieval or generation code:

- **A — no retrieval:** `run_closed_book(item, llm, cfg, tracker)`
  (`src/systems/standard.py:29`).
- **B — single-step:** `run_standard(item, retriever, llm, cfg, tracker)`
  (`src/systems/standard.py:7`).
- **C — multi-step:** `run_ircot(item, retriever, llm, cfg, tracker)`
  (`src/systems/ircot.py:36`).

The router returns the chosen strategy's result dict plus `route`
and `route_p` (the classifier's max class probability). The runner
writes extra keys from the system dict into the output row (the same
mechanism that carries `policy_decision` / `policy_p` for step 7), so
every Adaptive-RAG row carries its route. One branch is added to
`dispatch()` in `scripts/run_experiment.py` for
`system == "adaptive_rag"` (selected by `run.system` in config, as
for the other systems). No changes to `run_standard`,
`run_closed_book`, or `run_ircot`. No changes to the frozen tuned
TrueAdaptive system or its config. The classifier is loaded once per
process (path from `adaptive_rag.classifier_path` in config, default
`configs/adaptive_rag_classifier/`); a missing classifier file is a
loud error at startup, never a silent fall-through to one strategy.

## Classifier

**Primary:** DistilBERT (`distilbert-base-uncased`, ~66M parameters)
fine-tuned for 3-class classification on CPU in the repo venv
(sklearn 1.9.1, transformers 5.22.2, torch 2.15.0+cpu — all present;
verified 2026-11-10). The model must be downloaded from the HF hub
(`HF_HUB_DISABLE_XET=1` applies, as for MiniLM); the download is a
build step with its own check in tasks A.2.

**Fallback (only if the download fails):** a sklearn logistic
regression on cached MiniLM embeddings (`all-MiniLM-L6-v2` is already
in `~/.cache/huggingface/hub`, no download needed). The fallback is
a disclosed deviation, not a silent substitution: whichever classifier
ran is named in the artifact, the commit, and the paper. No third
classifier, no architecture search after seeing results.

**Why not T5-small (the paper's classifier):** the paper trains a
T5-small; DistilBERT is the practical CPU equivalent here (same
order of parameters, a standard 3-class head, faster to train on
this VM). The baseline's job is to represent "question-text
routing" faithfully, not to reproduce the paper's exact weights —
and the paper will say which model ran. If the reviewer asks, the
honest answer is that the routing *idea* is implemented, with a
smaller classifier than the paper's.

## Training data (dev + public external data only, never test)

Committed file `data/adaptive_rag_training.jsonl` — one row per
question with `question`, `label` (A/B/C), and `source`. Labels come
from dataset properties only:

- **C — multi-step:** HotpotQA dev questions (`data/manifests/dev.jsonl`,
  N=100, all multi-hop by construction).
- **B — single-step:** a SQuAD v1 train sample (single-hop extractive
  QA, class B by construction).
- **A — no retrieval:** construction decided and recorded in tasks
  A.1 *before* training (candidates: a TriviaQA sample, or SQuAD
  questions the closed-book system already answers correctly on a
  small labeled sample). Whichever is chosen, its definition and
  counts are committed with the training file.

Target ~3,000 questions, roughly balanced across A/B/C; a 20%
held-out split is reserved for validation and never trained on.
Test-400 rows are never used for training, feature selection,
threshold choice, or model selection — the training script asserts
its input is not a test file (same guard as the step-7 extractor)
and refuses test files. The training set's sources and class counts
are recorded in the commit that adds it.

## Hypothesis H8 (new, pre-registered — written here, before any run)

**H8 (exploratory, not confirmatory — H1/H4 are the confirmatory
ones):** the frozen tuned TrueAdaptive beats the Adaptive-RAG
baseline on HotpotQA Test-400 BM25 on EM, at equal-or-fewer LLM
calls/Q. Judged by paired McNemar exact two-sided, α=0.05, on the
same 400 questions. Secondaries: F1, calls/Q, coverage, route
distribution, per-route EM. H8 is exploratory for the same reason
the ERag-vs-IRCoT comparison is exploratory (the report's
classification): it compares two systems, and the confirmatory
claims are H1 (vs Standard) and H4 (vs the no-adaptive ablation).

## Gates (pre-registered)

**Gate AR-1 (offline router validation, before any live run):**
held-out routing accuracy strictly above the majority-class rate on
the 20% split, AND the Dev-100 route distribution non-degenerate —
no single route above 90% of questions (otherwise the baseline
collapses to one strategy and the comparison is vacuous). If AR-1
fails, the baseline does not proceed to a live run — the change
closes as a negative result with the router's accuracy recorded.

**Gate AR-2 (live Test-400, needs a Groq key, transient):** one run,
system `adaptive_rag`, BM25 k=3, distractor, fresh cache namespace
`test_adaptive_rag_v1_bm25`, output
`results/adaptive_rag/adaptive_rag_test_bm25.jsonl`. N=400 deduped,
0 failed. Then the H8 paired comparison against the frozen tuned
TrueAdaptive Test-400 file (from Phase 2) and against the fresh
IRCoT Test-400 file, via the analyzer section (tasks C.2).

**Honest expectation, recorded before the run:** HotpotQA is all
multi-hop, so a good router will send most questions to C
(multi-step) — the baseline will likely land close to IRCoT, and
the gap to TrueAdaptive will be smaller than the gap to IRCoT. A
small gap is still informative (routing buys little on this
dataset); a large one would say the opposite. Either way it is
reported, and the route distribution is published alongside the
headline numbers so the reader can see *why*.

## Verification numbers (must be recorded before training)

A.1 records, before any training: the training set's sources and
class counts (A/B/C), the majority-class rate on the held-out split
(the AR-1 floor), and the Dev-100 question count (N=100, all class C
by construction — the router's dev distribution is therefore a
sanity check, not a training signal). There are no prior numbers to
reproduce: the classifier and the training set do not exist yet.

## Threats to validity

- **The classifier is the weak point — by the paper's own result.**
  Adaptive-RAG's oracle classifier would jump HotpotQA F1 53.82 →
  64.00; a weak router makes the baseline weak, and beating a weak
  baseline proves little. Gate AR-1 exists for exactly this reason,
  and the router's held-out accuracy is published with the result.
- **HotpotQA is all multi-hop.** The routing idea earns its keep on
  mixed-complexity data; on HotpotQA the baseline is mostly IRCoT
  with a few questions routed elsewhere. The comparison is still
  worth running (it tests whether evidence-driven adaptivity beats
  question-text routing), but the expected gap is small — recorded
  above, not discovered after the fact.
- **Router errors are silent.** A misrouted question just runs the
  wrong strategy, with no recovery — unlike ERag, which re-evaluates
  at every hop. The per-route EM in the analysis shows whether the
  router's mistakes cost accuracy.
- **CPU training + HF download.** DistilBERT fine-tuning on CPU for
  ~3,000 questions is feasible (tens of minutes per epoch at small
  batch sizes) but slow; the HF download may fail (the CMU mirror
  failed three times for the HotpotQA raw file — the fallback
  classifier exists for this case and is named, not hidden).
- **Contamination.** Test-400 must not appear in training, in the
  held-out split, or in any threshold/model choice. The training
  script refuses test files; any run that touches Test-400 before
  the Phase 2 freeze invalidates the verdict.
- **The Dev-100 sanity run is in-sample for the router's training
  data** (the dev questions are class-C training rows), so its route
  distribution is a sanity check only — the Test-400 run is the
  judge.
