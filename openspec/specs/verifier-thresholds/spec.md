# verifier-thresholds Specification

## Purpose
Phase 2.6 H16: the NLI verifier's thresholds (theta_s / theta_c, both
0.5, never tuned) are too conservative — H2's supported recall is 0.60
and macro-F1 0.6825 < 0.70. Sweep the thresholds on a claim-level eval
built from stored Dev-100 traces and adopt the winning pair only if it
clears the H2 bar on held-out claims and does not lower Dev-100 EM.
Source: `docs/phase26-beat-ircot-plan.md`.

## Requirements

### Requirement: Thresholds are selected on a held-out claim eval, not on test

The system SHALL select (theta_s, theta_c) by sweeping a grid over
claim-level verification on Dev-100 traces only, with thresholds chosen
on a 70-row selection split and judged on a held-out 30-row split. No
Test-400 data is involved in selection.

#### Scenario: Selection uses only dev traces

- **WHEN** the sweep runs
- **THEN** every claim comes from a Dev-100 trace file and every label
  from the dev manifest; no Test-400 file is read

#### Scenario: Held-out split judges the selection

- **WHEN** a threshold pair is chosen on the selection split
- **THEN** its reported numbers are computed on the held-out split, and
  a pair that wins selection but fails held-out does not pass the gate

### Requirement: The winning pair clears the H2 bar and does not lower EM

The system SHALL adopt new thresholds only if the winning pair has
binary macro-F1 ≥ 0.70 AND supported recall ≥ 0.70 on held-out claims
and the Dev-100 BM25 A/B with those thresholds has dEM ≥ 0 at
≤ +0.2 calls/Q vs the improved-system baseline.

#### Scenario: No pair clears the bar

- **WHEN** no grid pair reaches binary macro-F1 ≥ 0.70 AND supported
  recall ≥ 0.70 on held-out claims
- **THEN** H16 is NOT SUPPORTED on the eval leg, the thresholds stay at
  0.5/0.5, and no A/B runs

#### Scenario: A/B lowers EM

- **WHEN** the thresholds arm has dEM < 0 vs the improved-system
  baseline on Dev-100 BM25
- **THEN** the thresholds stay at 0.5/0.5 regardless of the eval numbers
