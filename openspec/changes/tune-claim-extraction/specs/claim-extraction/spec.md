# claim-extraction

## Purpose

On Test-400 BM25, 37 wrong answers had recall == 1.0 but the gold answer was
never extracted as a claim — claim extraction is conditioned on the (wrong)
draft, so the claims decompose the wrong answer instead of asking what the
context says. Baselines: gold-in-claims rate among full-recall wrong rows is
0.333 on dev (6/18) and 0.654 on test (70/107). Source:
`docs/trueadaptive-test400-error-analysis.md` (§2, §5) and the 2026-11-09
diagnosis in the change proposal.

## ADDED Requirements

### Requirement: Extraction also returns question-grounded claims

The system SHALL, in the single existing extraction call, return claims from
the context that answer the question in addition to the draft-supporting
claims, including ones that disagree with the draft or give a different
(fuller) name, date, or value, using full names exactly as written in the
context.

#### Scenario: Question claim disagreeing with the draft is returned

- **WHEN** the context contains a claim that answers the question with a
  different answer than the draft
- **THEN** the extraction returns it alongside the draft-supporting claims

#### Scenario: Full names come from the context, not the draft

- **WHEN** the context names an entity in full (e.g. "Thon Marial Maker")
  and the draft uses a short form (e.g. "Thon Maker")
- **THEN** the question-grounded claim uses the full name exactly as written
  in the context

#### Scenario: Draft-supporting claims are still returned

- **WHEN** the extraction runs
- **THEN** the claims that must be true for the draft answer are still
  listed, as today

### Requirement: Each claim carries its source

The system SHALL include a `"source"` field on every returned claim
(`"draft"` or `"question"`), defaulting to `"draft"` when the model omits it,
and the fallback single-atomic claim SHALL carry `"source": "draft"`.

#### Scenario: Source is preserved from the model response

- **WHEN** the model returns a claim with `"source": "question"`
- **THEN** the parsed claim carries `"source": "question"`

#### Scenario: Missing source defaults to draft

- **WHEN** the model returns a claim without a `"source"` field
- **THEN** the parsed claim carries `"source": "draft"`

#### Scenario: Fallback claim is draft-sourced

- **WHEN** structured generation fails and the fallback claim is used
- **THEN** it carries `"source": "draft"`

### Requirement: Exactly one answer-bearing claim, from the draft

The system SHALL mark exactly one claim as answer-bearing, and in the normal
case it SHALL be a draft-supporting claim, as today. The existing fallback
(last claim becomes answer-bearing when none is marked) is unchanged.

#### Scenario: Answer-bearing claim stays draft-sourced

- **WHEN** the extraction returns both kinds of claims
- **THEN** the answer-bearing claim is one of the draft-supporting claims

### Requirement: No new LLM calls

The system SHALL make no additional LLM call for question-grounded claims —
they come from the single existing extraction call.

#### Scenario: Call count unchanged by design

- **WHEN** the revised extraction runs
- **THEN** the number of LLM calls per hop is identical to v1 (1 draft +
  1 claims, plus the usual SC / retrieval calls)

### Requirement: Source is measurement metadata only

The system SHALL NOT branch any belief-graph, gap, retrieval, or abstention
logic on the `"source"` field in this change — all claims are verified by NLI
identically.

#### Scenario: Question claims go through the same NLI verification

- **WHEN** a question-sourced claim enters the graph
- **THEN** it is verified, gapped, and propagated exactly like a
  draft-sourced claim
