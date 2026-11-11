# extraction-recall Specification

## Purpose
Phase 2.5 H13: a second extraction pass at hop 0 recovers gold answers
the first extraction skips. Source:
`docs/phase25-improvement-diagnosis.md` (33 never-claimed Test-400
rows, gold retrieved at hop 0 but never extracted) plus a stored-data
check that the max_claims cap binds on only 2/33 rows and parsing never
fails — the failure is coverage, not capacity.

## Requirements

### Requirement: Second extraction pass at hop 0 adds uncovered claims

The system SHALL, at hop 0 and only when `erag.second_extraction` is
true, run a second claim-extraction call with a coverage-driven prompt
(given the already-extracted claims, list additional claims from the
Context that bear on the question and are NOT already covered) and merge
the new claims into the claim set (deduped by normalized text) before
the belief graph is built. At most +1 LLM call per question.

#### Scenario: Second pass adds a genuinely new claim

- **WHEN** the first extraction returns 1 claim and the second pass
  returns 1 new claim plus 1 duplicate of it
- **THEN** the graph is built from 2 claims, `second_pass_added` is 1,
  and the question costs exactly 1 more LLM call than with the flag off

#### Scenario: Flag off is byte-identical to the H12-improved system

- **WHEN** `erag.second_extraction` is false or absent
- **THEN** no second pass runs and the output record is identical to
  the same inputs with the flag off

#### Scenario: Merge dedupes by normalized text

- **WHEN** an additional claim's normalized text matches an existing
  claim (up to articles and punctuation)
- **THEN** it is dropped and the existing claim is kept in place

### Requirement: The second pass only ever adds context claims

The system SHALL default second-pass claims to `source: "question"`
(the pass only adds claims from the Context), keeping an explicit
`"draft"` value from the model as-is.

#### Scenario: Missing source defaults to question

- **WHEN** a second-pass claim carries no `source` field
- **THEN** it is recorded with `source: "question"`
