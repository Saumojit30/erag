# extractive-final-read Specification

## Purpose
TBD - created by archiving change extractive-final-read. Update Purpose after archive.

## Requirements

### Requirement: Extractive final read restricts the answer to verified claims

The system SHALL, when `erag.extractive_final_read` is true and
`erag.ground_final_read` is true and at least one supported claim
exists, run a single claims-only final re-read that replaces the
other re-read triggers (unknown / disagree / contested /
support-ranked) for that row.

#### Scenario: Extractive re-read fires and replaces the draft

- **WHEN** the final graph holds supported claims and the flag is on
- **THEN** the reader receives only the supported claims (sorted by
  `eff` desc, capped at `erag.max_claims`) with NO context block, and
  the draft is replaced by the re-read answer when it is not
  "unknown"

#### Scenario: Extractive re-read is always on, unlike the H15 trigger

- **WHEN** the draft is backed by the supported claims and the flag
  is on
- **THEN** the extractive re-read still fires (it is not conditional
  on the draft being unbacked)

#### Scenario: No supported claims means no re-read

- **WHEN** the final graph holds no supported claim and the flag is on
- **THEN** no re-read runs and the draft stands

#### Scenario: Flag-off runs are byte-identical

- **WHEN** `erag.extractive_final_read` is false or absent
- **THEN** the system behaves exactly as the improved system (no
  extra LLM call, no `extractive` row field)
