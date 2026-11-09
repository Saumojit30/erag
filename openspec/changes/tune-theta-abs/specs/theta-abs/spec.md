# theta-abs

## Purpose

On Test-400 BM25, 37 rows are system-abstained (`answer_conf` median
0.214, 17 with correct drafts) while 133 wrong answers are given —
the system answers wrong more often than it abstains. The abstention
threshold `theta_abs` (currently 0.4) is the system's only
hallucination control: it withholds answers whose final answer claim
is below the threshold. The paper's goal, decided by the user
2026-11-09, is to REDUCE HALLUCINATION of RAG first, with reduced LLM
cost second — so this step tests HIGHER thresholds (selective
answering: abstain rather than guess), judged by selective EM and
wrong-answer rate, with EM as a guardrail. Source:
`docs/trueadaptive-test400-error-analysis.md` (§2, §4) and the
2026-11-09 diagnosis in the change proposal (dev counterfactual from
the step-2 tuned dev file).

## ADDED Requirements

### Requirement: Abstention threshold is selectable by config value

The system SHALL apply the abstention threshold from `erag.theta_abs`
(a config value, default `0.4`), read at the abstention rule in
`src/systems/erag.py` (`ans.eff < e.get("theta_abs", 0.4)`), so that
an A/B can set it to a candidate value in the `--set` flags with no
code change.

#### Scenario: Default threshold is 0.4

- **WHEN** no `theta_abs` override is configured
- **THEN** the system abstains exactly the rows with `answer_conf`
  below 0.4

#### Scenario: Candidate threshold is applied

- **WHEN** the run sets `erag.theta_abs=0.50` (candidate A) or `0.65`
  (candidate B)
- **THEN** the system abstains exactly the rows with `answer_conf`
  below that value, and no other part of the pipeline changes

### Requirement: Higher threshold withholds low-confidence answers

The system SHALL, at a higher `theta_abs`, withhold the draft and
return "unknown" for rows whose final answer claim confidence is
below the threshold, instead of answering them.

#### Scenario: Low-confidence draft is withheld

- **WHEN** a row's `answer_conf` is below the candidate threshold
- **THEN** its final answer is "unknown" and the row is counted as
  abstained, not as a wrong answer

#### Scenario: High-confidence draft is answered

- **WHEN** a row's `answer_conf` is at or above the candidate threshold
- **THEN** its draft is answered as before, with the same calls and
  the same retrieval

### Requirement: Model-unknown rows are unaffected by the threshold

The system SHALL NOT change the outcome of rows whose draft is
literally "unknown": they stay "unknown" with EM 0 at any threshold,
because withholding an already-"unknown" answer changes nothing.

#### Scenario: Model-unknown row at a higher threshold

- **WHEN** a row's draft is "unknown" (reader refusal, high
  `answer_conf`)
- **THEN** its final answer is still "unknown" and its EM is still 0,
  whether or not its `abstained` flag flips

### Requirement: Analyzer reports selective-answer measures for a file

The analyzer SHALL, under a `--theta` flag, report for a dev file:
N (deduped), failed count, EM, selective EM (correct / answered),
wrong-answer rate among answered, wrong answers among all rows,
coverage, mean `llm_calls`/Q, mean `cache_hits`/Q, mean live calls/Q,
abstained count, and model-unknown count.

#### Scenario: Baseline file reproduces known numbers

- **WHEN** the `--theta` section runs on the step-2 tuned dev file
- **THEN** it reports EM 0.5400, selective EM 0.6353, wrong-answer
  rate 0.3647, coverage 0.850, 4.65 calls/Q, 2.53 cache_hits/Q

### Requirement: Analyzer reports the threshold counterfactual table

The analyzer SHALL, under the same `--theta` flag, report the
counterfactual table at t = 0.40–0.80 (EM, selective EM, wrong-answer
rate, coverage), computed the same way as §4. The two unknown
populations SHALL be classified by draft text
(`draft == "unknown"`), not by the `abstained` flag, because a
model-unknown row can flip `abstained=True` at a higher threshold
while its answer stays "unknown".

#### Scenario: Counterfactual table reproduces known numbers

- **WHEN** the `--theta` section computes the counterfactual table
- **THEN** t=0.50 reads EM 0.5100, selective EM 0.6456, wrong-answer
  rate 0.3544, coverage 0.790; t=0.65 reads identical to 0.50; t=0.75
  reads EM 0.4700, selective EM 0.6351, wrong-answer rate 0.3649,
  coverage 0.740

### Requirement: No other value changes in this change

The system SHALL NOT change any other config value in this change:
`ground_final_read` stays `true`, `max_claims` stays `8`,
`unknown_prompt` stays `"base"`, `max_hops` stays `2`, and the
Fast-Path gate, the re-read, the retrieval, and the NLI thresholds
stay untouched. The frozen v1 config (`configs/erag_trueadaptive.yaml`)
is NOT edited.

#### Scenario: Tuned values are preserved

- **WHEN** an A/B runs with a candidate `theta_abs`
- **THEN** its `--set` flags carry `erag.ground_final_read=true`,
  `erag.max_claims=8`, `erag.unknown_prompt=base` alongside the
  candidate threshold

### Requirement: No gold or few-shot examples in any prompt

The system SHALL NOT include the gold answer, any test/dev label, or
any few-shot example in any prompt — this change moves no prompt at
all, and the requirement is recorded so the change cannot be used to
smuggle one in.

#### Scenario: No prompt is touched

- **WHEN** the change is inspected
- **THEN** no prompt file or prompt constant differs from the tuned
  system
