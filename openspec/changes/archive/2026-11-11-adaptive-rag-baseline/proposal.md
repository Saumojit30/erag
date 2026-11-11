# Proposal: Adaptive-RAG routing baseline (Phase 2 addition)

Drafted 2026-11-10 from `docs/publication-ready-plan.md` (§3.3, D3) and
the user's 2026-11-10 decision: add Adaptive-RAG as a running baseline
alongside IRCoT. Branch `trueadaptive`. Nothing is pushed. Do not start
the build until the proposal is approved — the user approved the
baseline itself on 2026-11-10 ("yes do adaptive rag with ircot also")
and delegated the planning and execution to the assistant; this change
is the planning the user delegated.

## Why

The publication-ready plan's gap G3: the paper's only running
baseline is IRCoT (2023, a fixed interleaved method). The paper as
planned beats a fixed baseline and a non-adaptive ablation — a
mechanism claim, not a SOTA claim, and a reviewer will ask whether
the adaptivity itself is better than the other adaptive system in
the literature. Adaptive-RAG (Jeong et al., NAACL 2024) is that
system: it routes each question up front to no-retrieval,
single-step, or multi-step retrieval via a trained complexity
classifier. Adding it as a third system on the same Test-400 answers
the question the paper otherwise leaves open: is evidence-driven,
during-reasoning adaptivity (ERag) better than question-text routing
(Adaptive-RAG)?

## What (scope, tight)

A new system, `adaptive_rag`, in the runner: a small trained
classifier reads the question and routes it to one of three existing
strategies — closed-book (A), single-step Standard RAG (B), or
multi-step IRCoT (C). The three strategies already exist in the repo
(`run_closed_book`, `run_standard`, `run_ircot`); the new code is the
classifier, its training, and the router that picks between them. The
baseline is evaluated on the same Test-400 BM25 as the Phase 2
head-to-head, same LLM, same retriever, same corpus, fresh cache
namespace — and compared against the frozen tuned TrueAdaptive and
against IRCoT, paired, by McNemar.

Out of scope: any change to the frozen tuned TrueAdaptive system
(it stays frozen; the baseline is built alongside it, not inside
it); any change to the pre-registered ERag-vs-IRCoT Phase 2 verdict
(the Adaptive-RAG comparison is an additional, separately-judged
comparison — new hypothesis H8, written here before the run, never
after seeing it); a faithful T5-small classifier if the environment
cannot train it in reasonable time (the design names a DistilBERT
primary and a no-download fallback, and the paper will disclose
whichever ran); running the baseline on any dataset other than
HotpotQA Test-400 in this change (Phase 3 datasets get their own
changes, and the baseline may or may not travel there — that is a
Phase 3 decision, not this one).

## What it does NOT replace

IRCoT stays. The comparison becomes three systems, not two: ERag
(the system under test), IRCoT (the fixed control — "do nothing
adaptive"), Adaptive-RAG (the other-adaptive control — "adapt once,
up front, from the question text"). Each control answers a different
question, and dropping IRCoT would remove the fixed-baseline
comparison the H1/H6 story rests on.

## How it is judged

Two gates, both pre-registered in `design.md` before any code:
(AR-1) an offline router validation — held-out routing accuracy
above the majority-class baseline, and a non-degenerate route
distribution on Dev-100; (AR-2) a live Test-400 run, N=400 deduped,
0 failed, judging new hypothesis H8 (tuned TrueAdaptive beats
Adaptive-RAG on EM at equal-or-fewer calls/Q, paired McNemar
α=0.05). The honest expectation, recorded before the run: HotpotQA
is all multi-hop, so a good router will send most questions to
multi-step — the baseline will likely land close to IRCoT, and the
gap to ERag will be smaller than the gap to IRCoT. A small gap is
still informative (it says the routing buys little on this dataset);
a large one would say the opposite. Either way it is reported.

## Training data (dev + public external data only, never test)

The classifier trains only on questions whose complexity labels come
from dataset properties — HotpotQA dev questions (multi-hop, class
C), single-hop QA (SQuAD v1, class B), and no-retrieval questions
(class A, construction defined in tasks A.1 and recorded before
training). Test-400 rows are never used for training, feature
selection, threshold choice, or model selection — Phase 2 is the
judge, and anything learned from test would contaminate it. The
training set, its sources, and its class counts are committed as a
file before training starts.
