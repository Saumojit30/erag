# unknown-prompt

## Purpose

On Test-400 BM25, 40 rows end with the reader's draft literally "unknown"
(row flag `unknown`, not abstained) while the graph is confident
(`answer_conf` median 0.875, `c0` median 1.000). Only 3/40 had any hop
produce a real answer, and 16/40 had full recall — the reader refuses from
hop 0 and the hops do not rescue it. Dev has only 7 such rows (step-2 tuned
file), so the dev gate is about the unknown count and recovered-row
accuracy, with EM as a guardrail. Source:
`docs/trueadaptive-test400-error-analysis.md` (§2, §5) and the 2026-11-09
counts in the change proposal.

## ADDED Requirements

### Requirement: Reader prompt is selectable by variant flag

The system SHALL select the reader system prompt via `erag.unknown_prompt`
(`"base"`, `"best_guess"`, or `"cite_first"`), defaulting to `"base"`
(the current `ANSWER_SYSTEM`, unchanged). An unknown variant name SHALL fall
back to `"base"`.

#### Scenario: Default is the current prompt

- **WHEN** no variant is configured
- **THEN** `answer_messages` uses the current `ANSWER_SYSTEM` text

#### Scenario: Unknown variant falls back to base

- **WHEN** `erag.unknown_prompt` names a variant that does not exist
- **THEN** the reader uses the `"base"` prompt instead of failing

### Requirement: best_guess variant separates "not in context" from "uncertain"

The system SHALL, for variant `"best_guess"`, instruct the reader to give
its best short answer from relevant context evidence even when uncertain,
and to reply "unknown" only when the context contains nothing relevant to
the question.

#### Scenario: Relevant evidence present but answer uncertain

- **WHEN** the context contains evidence relevant to the question but no
  cleanly stated answer
- **THEN** the variant instructs a best short answer from that evidence
  rather than "unknown"

#### Scenario: Nothing relevant in the context

- **WHEN** the context contains nothing relevant to the question
- **THEN** the variant instructs exactly "unknown"

### Requirement: cite_first variant locates evidence before answering

The system SHALL, for variant `"cite_first"`, instruct the reader to first
identify the single sentence in the context most relevant to the question,
then reply with only the short answer from that sentence, and to reply
"unknown" when no sentence is relevant.

#### Scenario: Relevant sentence exists

- **WHEN** a sentence in the context is relevant to the question
- **THEN** the variant instructs the reader to identify it first and answer
  from it

#### Scenario: No relevant sentence

- **WHEN** no sentence in the context is relevant to the question
- **THEN** the variant instructs exactly "unknown"

### Requirement: Re-read prompt and abstention rule unchanged

The system SHALL NOT change `GROUNDED_ANSWER_SYSTEM`,
`grounded_answer_messages`, or the abstention rule (`theta_abs`, the
`abstained` flag) in this change. The abstention rule stays the arbiter of
whether an answer is withheld.

#### Scenario: Re-read prompt is untouched

- **WHEN** the unknown-prompt variant changes
- **THEN** the claim-grounded re-read still uses `GROUNDED_ANSWER_SYSTEM`

### Requirement: No gold or few-shot examples in the prompt

The system SHALL NOT include the gold answer, any test/dev label, or any
few-shot example in the reader prompt — it contains only the question and
the pool, as today.

#### Scenario: Prompt contains no answer

- **WHEN** the variant prompt is inspected
- **THEN** it contains no gold answer, label, or worked example
