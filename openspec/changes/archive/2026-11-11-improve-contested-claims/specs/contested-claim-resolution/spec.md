# contested-claim-resolution

## Purpose

Phase 2.5 H12: when the final belief graph is contested — a supported
draft-sourced claim agrees with the draft while a supported
question-sourced claim does not — run one extra reader call grounded on
the competing claims, with the disagreement stated explicitly. Source:
`docs/phase25-improvement-diagnosis.md` (stored Test-400 diagnosis:
53 gold-in-claims wrong rows, 34/53 with the final answer inside a WRONG
supported claim, re-read never fired on 41/53).

## ADDED Requirements

### Requirement: Contested graphs trigger one extra grounded re-read

The system SHALL, at the final read and only when
`erag.contested_resolution` is true, detect a contested graph — a
supported draft-sourced claim contains the normalized draft answer AND
a supported question-sourced claim does not — and run one extra reader
call grounded on the competing claims. The draft is replaced only when
the re-read returns a non-"unknown" answer. At most one extra LLM call
per question.

#### Scenario: Contested graph triggers the re-read

- **WHEN** the final graph has a supported draft-sourced claim
  containing the draft and a supported question-sourced claim that does
  not, and the flag is on
- **THEN** exactly one extra LLM call is made, `reread_trigger` is
  `"contested"`, and `contested` is true on the row

#### Scenario: Uncontested graph triggers nothing

- **WHEN** no supported question-sourced claim disagrees with the draft
- **THEN** no extra call is made and the row carries no new fields
  beyond the step-1 set

#### Scenario: Flag off is byte-identical to the tuned system

- **WHEN** `erag.contested_resolution` is false or absent
- **THEN** no contested re-read runs and the output record is identical
  to the tuned system's record for the same inputs

#### Scenario: Re-read returning unknown keeps the draft

- **WHEN** the contested re-read returns "unknown" (or empty)
- **THEN** the draft is kept and `reread_answer` records the reply

### Requirement: The contested re-read states the disagreement

The system SHALL present the competing claims under separate headings
(claims supporting the current answer vs claims supporting a different
answer), so the reader decides by the evidence rather than repeating
the draft.

#### Scenario: Both sides listed separately

- **WHEN** `contested_answer_messages` is built for a contested graph
- **THEN** the user message contains a heading for the agreeing side
  and a heading for the disagreeing side, plus the question and the
  context block
