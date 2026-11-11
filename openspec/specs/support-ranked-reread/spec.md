# support-ranked-reread Specification

## Purpose
Phase 2.6 H15: when the final draft is not backed by the top-3
supported claims (ranked by `eff`), run one extra reader call grounded
only on those top-3 claims and let the reader choose the answer from
them. Source: `docs/phase26-beat-ircot-plan.md` (headroom measured on
stored tuned Test-400 rows: gold in top-3 supported claims on 48/53
gold-in-claims wrong rows; trigger fires on 24/53 target rows vs
39/180 correct rows).

## Requirements

### Requirement: Drafts unbacked by the top supported claims trigger one extra grounded re-read

The system SHALL, at the final read and only when
`erag.support_ranked_reread` is true, rank supported claims by `eff`
descending and, when the normalized draft appears in none of the top-k
(`erag.support_ranked_top_k`, default 3) and at least one supported
claim exists, run one extra reader call grounded only on those top-k
claims. The draft is replaced only when the re-read returns a
non-"unknown" answer. At most one extra LLM call per question.

#### Scenario: Unbacked draft triggers the re-read

- **WHEN** the final graph has supported claims, the draft appears in
  none of the top-3 by `eff`, and the flag is on
- **THEN** exactly one extra LLM call is made, `reread_trigger` is
  `"support_ranked"`, and `support_ranked` is true on the row

#### Scenario: Backed draft triggers nothing

- **WHEN** the draft appears in one of the top-3 supported claims
- **THEN** no extra call is made and the row carries no new fields
  beyond the step-1 set

#### Scenario: No supported claims trigger nothing

- **WHEN** the final graph has no supported claim
- **THEN** no extra call is made

#### Scenario: Flag off is byte-identical to the improved system

- **WHEN** `erag.support_ranked_reread` is false or absent
- **THEN** no support-ranked re-read runs and the output record is
  identical to the improved system's record for the same inputs

#### Scenario: Re-read returning unknown keeps the draft

- **WHEN** the support-ranked re-read returns "unknown" (or empty)
- **THEN** the draft is kept and `reread_answer` records the reply

### Requirement: The re-read is grounded only on the top supported claims

The system SHALL present only the top-k supported claims (by `eff`) in
the re-read, so the reader chooses by the strongest verified evidence
rather than repeating the draft or re-reading the whole pool.

#### Scenario: Only the top claims are listed

- **WHEN** `support_ranked_answer_messages` is built for a triggered
  graph
- **THEN** the user message contains exactly the top-k claim texts, the
  question, and the context block — and no claim outside the top-k
