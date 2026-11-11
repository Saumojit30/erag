# evidence-first-answering

## ADDED Requirements

### Requirement: Evidence-first answering inverts the hop

The system SHALL, when `erag.evidence_first` is true, build each
hop's draft from verified passage claims instead of generating a
draft first: extract candidate answer-bearing claims from the
passages, verify them through the belief graph, and compose the
draft only from supported claims, with no context block in the
compose call.

#### Scenario: No draft call is made on the evidence-first path

- **WHEN** the flag is on
- **THEN** no reader draft call (`answer_messages`) runs in the hop;
  the hop's draft comes from the compose step

#### Scenario: Claims come from passages, not from a draft

- **WHEN** the flag is on
- **THEN** the claim extractor receives the question and the pool
  only (no Answer input), marks exactly one claim as the answer
  claim, and re-extracts from the full pool on every hop

#### Scenario: No supported claim means no compose call and an unknown draft

- **WHEN** the flag is on and the verified graph holds no supported
  claim
- **THEN** no compose call is made, the draft is "unknown", and the
  loop continues on gaps as today

#### Scenario: The rest of the pipeline is unchanged

- **WHEN** the flag is on and a composed draft exists
- **THEN** SC, the continuation policy, the Fast Path, the final
  re-reads, and Step 12 abstention all run on the composed draft
  exactly as they run on a reader draft

#### Scenario: Flag-off runs are byte-identical

- **WHEN** `erag.evidence_first` is false or absent
- **THEN** the system behaves exactly as the improved system (no
  extra LLM call, no `evidence_first` row field)
