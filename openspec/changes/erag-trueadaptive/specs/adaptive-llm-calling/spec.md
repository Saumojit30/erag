# adaptive-llm-calling

## Purpose

E-RAG's LLM calls adapt to each question instead of running a fixed,
unconditional pipeline: sequential self-consistency and self-consistency
gated behind the Fast Path (v1). Entropy-gated retrieval is deferred to
v2. Source: `docs/audit-adaptive-llm-calling.md` §11.

## ADDED Requirements

### Requirement: Sequential self-consistency stops early on consensus

The system SHALL sample self-consistency completions one at a time
(M=1 → 3, cap 3) and stop when the leading answer has an unassailable
majority or when the change in answer-distribution entropy ΔH < 0.05
after at least 2 samples, instead of firing all samples at once.

#### Scenario: Unanimous samples stop at 2

- **WHEN** the first 2 sampled answers agree
- **THEN** no third sample is taken and `tracker.llm_calls` reflects 2
  self-consistency calls

#### Scenario: Split samples go to 3

- **WHEN** the first 2 sampled answers disagree
- **THEN** a third sample is taken and the result uses the majority of 3

#### Scenario: Same return shape as fixed sampling

- **WHEN** sequential sampling is used
- **THEN** it returns `conf_majority`, `conf_draft_agreement`, and
  `samples`, identical in shape to `self_consistency`

### Requirement: Self-consistency gated behind the Fast Path

The system SHALL run hop 0 in the order draft → claim extraction →
belief graph / NLI → Fast-Path check, and run self-consistency only if
gaps exist or `min_eff < theta_fast`.

#### Scenario: Fast-Path question costs 2 calls

- **WHEN** a hop-0 question has no gaps and `min_eff >= theta_fast`
- **THEN** self-consistency is skipped and the question costs 1 draft +
  1 claim extraction = 2 LLM calls

#### Scenario: Confidence fallback is explicit when SC is skipped

- **WHEN** self-consistency is skipped by the Fast-Path gate
- **THEN** `c0` is set to `min_eff` and recorded as such in the result

### Requirement: Entropy-gated retrieval probe

> DEFERRED to v2 by user decision 2026-11-08. NOT implemented in v1;
> no `parametric_gate` flag exists in v1 code. This requirement is
> recorded here so the v2 change starts from a written spec.

The system SHALL, before any retrieval, generate a closed-book draft
plus one self-consistency sample, and skip retrieval when they agree
and the draft is not "unknown", answering from parameters in 2 calls total.

#### Scenario: Confident closed-book answer skips retrieval

- **WHEN** the closed-book draft and the probe sample agree and the draft
  is not "unknown"
- **THEN** no retrieval runs and the question costs 2 LLM calls

#### Scenario: Disagreement or "unknown" proceeds to retrieval

- **WHEN** the probe sample disagrees with the draft, or the draft is
  "unknown"
- **THEN** the normal retrieval loop runs and the gate decision is logged
  per question

### Requirement: TrueAdaptive configuration is frozen and isolated

The system SHALL provide `configs/erag_trueadaptive.yaml` with sequential
self-consistency (M cap 3), gated SC behind the Fast Path, direct EIG,
incremental claims, never resample, saturation precheck, and unchanged
thresholds (`theta_fast 0.8`, `theta_gap 0.6`, `theta_abs 0.4`), using a
new `cache_namespace` that is never `dev_v1` or `test_v1`.

#### Scenario: Cache namespace is new

- **WHEN** the TrueAdaptive config is loaded
- **THEN** its `cache_namespace` differs from every earlier config's
  namespace, so no cached Reference/Balanced completions are reused

#### Scenario: Thresholds unchanged in v1

- **WHEN** the TrueAdaptive config is loaded
- **THEN** `theta_fast`, `theta_gap`, and `theta_abs` are 0.8, 0.6, and
  0.4 respectively
