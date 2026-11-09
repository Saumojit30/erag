# hop2-sc-cap Specification

## Purpose
On Test-400 BM25, 54 rows with ≥7 calls consume 422 of 1,910 calls
(22.1%) at EM 0.3333, and 38 of the 54 are hop-2 rows; hop-2 rows cost
7.95 calls/Q at EM 0.4048 (42 rows, 334 calls). The hop-2 iteration
costs 1 draft call + 1 claim-extraction call (iff the hop-2 draft
differs from the hop-0 draft). There is no self-consistency work at
hop 2 to cap — SC runs at most once per question, at hop 0, and
post-hop resampling is already `never` in the frozen v1 config — so
the cap targets the hop-2 iteration itself, via the existing
`erag.max_hops` config value. Source:
`docs/trueadaptive-test400-error-analysis.md` (§5) and the diagnosis
in the change proposal (counterfactual on stored rows, draft-level EM).

## Requirements

### Requirement: Hop loop stops after hop 1 when max_hops is 1

The system SHALL stop the adaptive hop loop after hop 1 when
`erag.max_hops` is `1`, using the existing loop stop condition — no new
flag, no new stop condition.

#### Scenario: Capped run never reaches hop 2

- **WHEN** `erag.max_hops` is `1` and the hop-1 graph still has gaps
  with retrievable evidence
- **THEN** the run ends after hop 1 (`hops == 1`) and no hop-2 draft or
  claim-extraction call is made

#### Scenario: Uncapped run is unchanged

- **WHEN** `erag.max_hops` is `2`
- **THEN** the loop behaves exactly as in v1 (hop 2 runs when gaps
  remain and retrieval returns new passages)

#### Scenario: Rows stopping earlier are unaffected

- **WHEN** a row stops at hop 0 or hop 1 under `max_hops=2`
  (Fast Path, no gaps, saturation, or no new passages)
- **THEN** it produces identical behavior under `max_hops=1`

### Requirement: Cap changes nothing else in the pipeline

The system SHALL NOT change self-consistency, the Fast-Path gate, the
claim-grounded re-read, the abstention rule, or hop 0 / hop 1 behavior
when the hop cap is applied. The post-loop machinery reads the hop-1
graph and draft on capped rows, as it reads the final hop's graph and
draft on uncapped rows.

#### Scenario: SC and Fast Path are untouched

- **WHEN** the cap is applied
- **THEN** SC still runs at most once, at hop 0, behind the Fast-Path
  gate, with the same sequential cap (M=3)

#### Scenario: Re-read and abstention still run on capped rows

- **WHEN** a capped row ends at hop 1 with an unknown or
  graph-disagreeing draft
- **THEN** the claim-grounded re-read still triggers as in step 1, and
  abstention still withholds the answer when the answer claim's
  effective confidence is below `theta_abs`

### Requirement: Analyzer reports the hop-cap measures for a dev file

The analyzer SHALL, with `--hopcap`, report for the `--ta-dev` file:
N (deduplicated by id, keeping the last row), failed count, EM, F1,
mean `llm_calls`/Q, mean `cache_hits`/Q, mean live calls/Q
(`llm_calls − cache_hits`), the hops distribution (n, mean calls, EM
per hops value), hop-2 row count and hop-2 calls, and tail rows (≥7
calls) with their call share. With `--hopcap-baseline <file>` it SHALL
also print the same measures for the baseline file and the deltas
(calls/Q, live calls/Q, EM).

#### Scenario: Section reproduces known stored-file numbers

- **WHEN** `--hopcap` is run on the step-2 tuned dev file
  (`results/trueadaptive/erag_trueadaptive_bm25_dev_claims.jsonl`)
- **THEN** it reports EM 0.5400, 4.65 calls/Q, 10 hop-2 rows,
  78 hop-2 calls

#### Scenario: Section reproduces the Test-400 tail numbers

- **WHEN** `--hopcap` is run on the Test-400 v1 file
  (`results/trueadaptive/erag_trueadaptive_test_bm25.jsonl`)
- **THEN** it reports 42 hop-2 rows, 334 hop-2 calls, tail 54 rows /
  422 calls

### Requirement: No change to the frozen v1 config

The system SHALL NOT modify `configs/erag_trueadaptive.yaml` in this
change. The cap is expressed in the A/B run's `--set` flags
(`erag.max_hops=1`); if the gate passes, the tuned value
(`max_hops: 1`) is recorded for the frozen tuned config written at the
end of Phase 1.

#### Scenario: Frozen config untouched

- **WHEN** the change is complete
- **THEN** `git status` shows no modification to
  `configs/erag_trueadaptive.yaml`
