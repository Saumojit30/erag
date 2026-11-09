# Learned continuation policy Specification

## Purpose

Replace the fixed hop-0 continuation decision (theta_fast fast
path + first gap/EIG continuation check) with a learned model that
predicts whether the hop-0 draft is correct and continues only
when it probably is not. The system stays adaptive in structure;
the decision boundary becomes learned from dev instead of
hand-set. Source: the user's 2026-11-09 question (properly adaptive
vs static values), the H3 finding (c0 AUROC 0.5915 — the confidence
signal discriminates weakly), and the step-4 finding (threshold
moves are a coin flip at the margin).

## ADDED Requirements

### Requirement: Policy decides hop-0 continuation when configured

The system SHALL, when `erag.continuation_policy` names a policy
artifact file, consult the policy at the hop-0 boundary (after
hop-0 draft, claim extraction, and NLI verification) and follow
its binary STOP / CONTINUE output instead of the fixed theta_fast
fast-path rule and the first gap/EIG continuation check. When the
flag is absent, behavior is exactly the current static system.

#### Scenario: Policy says STOP

- **WHEN** the policy artifact is configured and the model
  predicts the hop-0 draft is probably correct (P ≥ τ)
- **THEN** the run answers the hop-0 draft now with no retrieval,
  even when gaps exist

#### Scenario: Policy says CONTINUE

- **WHEN** the policy artifact is configured and the model
  predicts the hop-0 draft is probably wrong (P < τ)
- **THEN** the run enters the retrieval loop as today, with EIG
  gap selection unchanged

#### Scenario: Flag absent

- **WHEN** `erag.continuation_policy` is not configured
- **THEN** the run behaves exactly as the static system (fast
  path + gap/EIG rules), with no code-path change

### Requirement: Policy inputs are the hop-0 features

The system SHALL compute the policy's input features from the
hop-0 trace exactly as the offline extraction computes them
(design.md feature list: c0, c0_source, claim-status counts,
answer-bearing claim status, mean claim conf, hop-0 recall
recomputed from the manifest, question type, draft-unknown flag,
sc_skipped_fast_path), sharing one function where possible, so
the live run and the offline simulation see the same features.

#### Scenario: Live and offline features agree

- **WHEN** the same dev row is featurized live and from its
  stored trace
- **THEN** the feature vectors are identical

### Requirement: Model is logistic regression with a learned threshold

The system SHALL use a logistic regression on standardized
features, deciding CONTINUE iff P(draft correct) < τ, with τ
chosen by 5-fold cross-validation on dev. A depth-2 decision
tree is the only permitted alternative, taken only if its
cross-validated counterfactual beats the logistic regression's.

#### Scenario: Threshold is learned, not hand-set

- **WHEN** the training script runs on the dev training set
- **THEN** τ comes from cross-validation, and the artifact records
  it alongside the coefficients

### Requirement: Training data is dev only

The system SHALL train the policy only on the post-step-4 tuned
dev file (`results/trueadaptive/erag_trueadaptive_bm25_dev_theta_a.jsonl`,
N=100). The training script SHALL refuse any input file that is
not a dev file. Test-400 data is never used for training, feature
selection, τ choice, or model selection.

#### Scenario: Test file is refused

- **WHEN** the training script is given a Test-400 file as input
- **THEN** it exits with an error and trains nothing

### Requirement: Policy artifact is a committed JSON

The system SHALL store the trained policy as a committed JSON
with model type, feature list in order, coefficients, intercept,
τ, and training provenance (file, N, date, cross-validated
scores).

#### Scenario: Artifact is self-describing

- **WHEN** the artifact is read by the runner or by a reviewer
- **THEN** the model, its features, its threshold, and what it was
  trained on are all recoverable from the file alone

### Requirement: Policy scope is hop 0 only

The system SHALL apply the policy at hop 0 only. Hop-1+
continuation, EIG gap selection, SC, abstention (theta_abs=0.5),
and max_hops=2 are unchanged.

#### Scenario: Hop-1 decision stays static

- **WHEN** a run reaches hop 1
- **THEN** the hop-2 continuation decision uses the existing
  static rules, not the policy

### Requirement: Policy decisions are recorded per row

Every run row written while the policy is active SHALL carry a
`policy_decision` field ("stop" / "continue"; absent when the
flag is off), so the analyzer can report the decision
distribution and the simulation agreement check.

#### Scenario: Decision is visible in the output

- **WHEN** a Dev-100 run finishes with the policy configured
- **THEN** every row has a `policy_decision` field, and the
  analyzer's `--policy` section reports the STOP vs CONTINUE
  counts and their EMs

### Requirement: Gates are pre-registered

The policy SHALL enter the frozen Test-400 system only if it
meets both pre-registered gates. Gate A (offline counterfactual,
out-of-fold only): simulated EM ≥ 0.5000 AND simulated calls/Q
strictly below 4.65. Gate B (live Dev-100): live EM ≥ 0.5000 AND
live calls/Q strictly below 4.65 AND live numbers within ±0.02
EM / ±0.2 calls/Q of the simulation. N=100 deduped, 0 failed rows
in both gates.

#### Scenario: Gate A fails

- **WHEN** the cross-validated simulation does not meet Gate A
- **THEN** the policy is not wired in, no live run happens, and
  the change closes as a negative result
