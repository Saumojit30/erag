# eager-sc Specification

## Purpose
Phase 2.5 H14: replicate the Test-400 FP-control direction on Dev-100.
Source: `docs/phase25-improvement-diagnosis.md` (pre-registered H14)
and the Test-400 D2 FP leg (FP-control EM 0.4675 vs tuned 0.4500,
dEM +0.0175, p=0.2810, +0.70 calls/Q). Config-only change; the flag
already exists.

## Requirements

### Requirement: Eager self-consistency is a config-only switch

The system SHALL, when `erag.gate_sc_behind_fast_path` is false, run
self-consistency up front at hop 0 before the belief graph is built
(the existing behavior of the flag), with no other change to the
pipeline.

#### Scenario: Flag false runs SC up front

- **WHEN** `erag.gate_sc_behind_fast_path` is false
- **THEN** hop-0 `c0` comes from self-consistency on every row and the
  fast-path check sees the SC-derived graph

#### Scenario: Flag true keeps the deferred behavior

- **WHEN** `erag.gate_sc_behind_fast_path` is true
- **THEN** hop-0 SC is deferred until after the fast-path check, as in
  the frozen tuned system
