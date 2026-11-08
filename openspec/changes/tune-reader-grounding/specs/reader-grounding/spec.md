# reader-grounding

## Purpose

The final reader sees only raw pool paragraphs, never the belief graph's
verified claims — so on Test-400 BM25, 70 questions had the gold answer inside
a trace claim and still got the wrong final answer, and 40 ended with the draft
literally "unknown" while the graph was confident. Source:
`docs/trueadaptive-test400-error-analysis.md` (§2, §3, §5).

## ADDED Requirements

### Requirement: Conditional claim-grounded re-read

The system SHALL, after the hop loop and before abstention, perform exactly one
extra reader call grounded on the graph's supported claims when the draft is
"unknown" or disagrees with the graph's answer claim, and only then.

#### Scenario: Draft "unknown" triggers a re-read

- **WHEN** the final draft is "unknown" and the graph has an answer claim
- **THEN** one re-read call is made with the verified-claims prompt, and the
  draft is replaced only if the re-read returns a non-"unknown" answer

#### Scenario: Draft disagreeing with the answer claim triggers a re-read

- **WHEN** the normalized draft is not a substring of the normalized
  answer-claim text
- **THEN** one re-read call is made with the verified-claims prompt

#### Scenario: Draft agreeing with the answer claim triggers nothing

- **WHEN** the normalized draft is a substring of the normalized answer-claim
  text (e.g. draft "5th generation" inside "The BMW 5 Series is currently in
  its 5th generation.")
- **THEN** no extra call is made and the draft stands unchanged

#### Scenario: Re-read returning "unknown" keeps the original draft

- **WHEN** the re-read returns "unknown"
- **THEN** the original draft is kept, the re-read is logged, and no further
  re-read is attempted

#### Scenario: No answer claim means no re-read

- **WHEN** the graph has no claims
- **THEN** no re-read is attempted

### Requirement: Re-read prompt grounds on verified claims

The system SHALL build the re-read prompt with the graph's supported claims
first (answer-bearing first, then by effective confidence descending, capped at
5), followed by the same context block and question the draft call uses.

#### Scenario: Supported claims only

- **WHEN** the re-read prompt is built
- **THEN** it contains only claims with `status == "supported"` — contradicted
  or unresolved claims are excluded

#### Scenario: Same answer format as the draft

- **WHEN** the re-read runs
- **THEN** it uses temperature 0.0 and the same short-answer-only format as the
  draft call

### Requirement: Re-read is measurable per record

The system SHALL log `grounded_reread` (bool), `reread_trigger` ("unknown" |
"disagree" | null), and `reread_answer` (str | null) on every result record, and
the original draft SHALL be kept in the trace's last hop entry when replaced.

#### Scenario: Replaced draft is inspectable

- **WHEN** a re-read replaces the draft
- **THEN** the record carries the re-read answer as `draft` and the original
  draft remains in `trace[-1]["answer"]`

### Requirement: Flag off preserves v1 behavior exactly

The system SHALL make no re-read call and set no new record fields when
`erag.ground_final_read` is false or unset (the default).

#### Scenario: Flag off means zero behavior change

- **WHEN** the flag is off
- **THEN** the run produces byte-identical answers and call counts to v1 for
  the same config, retriever, and cache namespace

### Requirement: Abstention rule is unchanged

The system SHALL still withhold the answer iff `ans.eff < theta_abs` (0.4),
computed from `graph.answer_claim()` exactly as today. The re-read replaces
draft text only.

#### Scenario: Unsupported re-read answer can still be abstained on

- **WHEN** the re-read returns an answer the graph does not support
- **THEN** the abstention rule applies to it unchanged
