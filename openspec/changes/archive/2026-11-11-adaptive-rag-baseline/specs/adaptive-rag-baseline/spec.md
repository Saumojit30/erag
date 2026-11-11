# Adaptive-RAG routing baseline Specification

## Purpose

Add a third system to the Phase 2 Test-400 comparison: an
Adaptive-RAG baseline (Jeong et al., NAACL 2024) that routes each
question up front to no-retrieval, single-step, or multi-step
retrieval via a trained complexity classifier. It tests whether
evidence-driven, during-reasoning adaptivity (TrueAdaptive) beats
question-text routing (Adaptive-RAG), alongside the fixed IRCoT
control. Source: `docs/publication-ready-plan.md` (§3.3, D3) and the
user's 2026-11-10 decision to add the baseline alongside IRCoT.

## ADDED Requirements

### Requirement: Router dispatches by classifier prediction

The system SHALL, when `run.system` is `adaptive_rag`, classify
each question with the trained classifier and run exactly one of
the three existing strategies: closed-book (A), single-step
Standard RAG (B), or multi-step IRCoT (C). No new retrieval or
generation code is introduced; the router only picks between
existing systems.

#### Scenario: Route A (no retrieval)

- **WHEN** the classifier predicts class A for a question
- **THEN** the run answers it closed-book, with no retrieval

#### Scenario: Route B (single-step)

- **WHEN** the classifier predicts class B for a question
- **THEN** the run answers it with single-step Standard RAG

#### Scenario: Route C (multi-step)

- **WHEN** the classifier predicts class C for a question
- **THEN** the run answers it with multi-step IRCoT

### Requirement: Route is recorded per row

Every run row written by the Adaptive-RAG system SHALL carry a
`route` field ("A" / "B" / "C") and a `route_p` field (the
classifier's max class probability), so the analyzer can report
the route distribution and per-route accuracy.

#### Scenario: Route is visible in the output

- **WHEN** a run with system `adaptive_rag` finishes
- **THEN** every row has a `route` and a `route_p` field, and the
  analyzer's `--adaptive-rag` section reports the counts and EM
  per route

### Requirement: Classifier is a trained 3-class model

The system SHALL use a small trained classifier for the routing
decision: DistilBERT fine-tuned for 3-class classification as the
primary, or a sklearn logistic regression on cached MiniLM
embeddings as the fallback if the DistilBERT download fails.
Whichever ran is named in the artifact, the commit, and the paper.

#### Scenario: Missing classifier fails loudly

- **WHEN** the classifier file named in config does not exist
- **THEN** the run fails at startup with an error, and never
  silently falls through to a single strategy

### Requirement: Training data is dev and public external data only

The system SHALL train the classifier only on questions whose
complexity labels come from dataset properties — HotpotQA dev
questions (class C), a SQuAD v1 train sample (class B), and
no-retrieval questions by the construction recorded in tasks A.1
(class A). The training script SHALL refuse any input file that
is a Test-400 file. Test-400 data is never used for training,
feature selection, threshold choice, or model selection.

#### Scenario: Test file is refused

- **WHEN** the training script is given a Test-400 file as input
- **THEN** it exits with an error and trains nothing

### Requirement: Frozen system and pre-registered verdict are untouched

The system SHALL NOT modify the frozen tuned TrueAdaptive system
or its config, and SHALL NOT change the pre-registered ERag-vs-IRCoT
Phase 2 verdict. The Adaptive-RAG comparison is an additional,
separately-judged comparison under new hypothesis H8.

#### Scenario: Baseline added, primary verdict unchanged

- **WHEN** the Adaptive-RAG Test-400 run is added to Phase 2
- **THEN** the ERag-vs-IRCoT verdict rule (Win / Loss /
  Inconclusive, master plan §4.2) is unchanged, and H8 is judged
  on its own paired test

### Requirement: Gates are pre-registered

The baseline SHALL proceed to a live run only if it meets Gate
AR-1 (offline router validation: held-out routing accuracy
strictly above the majority-class rate, AND no single route above
90% of Dev-100 questions). The Test-400 run (Gate AR-2) SHALL
have N=400 deduped and 0 failed rows, and H8 SHALL be judged by
paired McNemar exact two-sided, α=0.05, primary EM.

#### Scenario: Gate AR-1 fails

- **WHEN** the held-out routing accuracy does not beat the
  majority-class rate, or one route dominates Dev-100
- **THEN** the baseline is not wired in, no live run happens, and
  the change closes as a negative result
