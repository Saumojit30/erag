# Proposal: Phase 2.5 H12 — Contested-claim resolution at the final read

## Status

Draft — prepared 2026-11-11 from `docs/phase25-improvement-diagnosis.md`
(stored Test-400 diagnosis, no live calls yet). Phase 2.5, H12 of three
mechanisms (H13 extraction recall, H14 eager SC follow). User decision
2026-11-11: improve first, then Phase 3.

## Why

The tuned system's largest diagnosed failure population is 53 Test-400 rows
where the gold answer sits in the trace claims and the system still answers
wrong. On 34 of the 53, the final answer sits inside a WRONG supported
claim; the claim-grounded re-read (step 1) never fires on 41 of the 53
because it triggers only on draft-"unknown" or draft-disagrees-with-answer-
claim, and these rows agree — with the wrong claim. The system is
confidently wrong (mean c0 0.94, mean answer_conf 0.90). The failure is
claim *selection* at the final read, not extraction and not retrieval.

## What changes

One new trigger at the final read, behind `erag.contested_resolution`
(default false): when the final graph is *contested* — a supported
draft-sourced claim agrees with the draft while a supported
question-sourced claim does not — run one extra reader call grounded on
the competing claims, with a prompt that states the disagreement and
asks the reader to decide by the evidence. The draft is replaced only
when the re-read returns a non-"unknown" answer. Row fields reuse the
step-1 `grounded_reread` / `reread_trigger` / `reread_answer` shape, with
`reread_trigger="contested"` and a new `contested` boolean.

## Dated clarification to H12 (before the affected run, Rule 2)

H12 as pre-registered said the trigger was "≥2 supported answer-bearing
claims with different answers". A stored-data check (`/tmp/h12_trigger.py`,
2026-11-11) shows that trigger covers **2/53** target rows — the
extractor marks exactly one answer-bearing claim on most graphs, so the
definition is unusable. The trigger is redefined to T2 (measured on the
same stored file): a supported draft-sourced claim contains the draft
answer AND a supported question-sourced claim does not. T2 covers 16/53
target rows at a 36% false-trigger rate on correct rows (64/180). The
false triggers cost +1 call each; the step-1 re-read's record (fixed 14,
broke 1 on its triggered population) is the reason to believe a false
trigger mostly returns the same answer rather than breaking a right one.
The H12 criterion itself is unchanged: Dev-100 BM25 EM gain ≥ +0.02 at
≤ +0.5 calls/Q vs the tuned baseline.

## Threats to validity

- **Dev-100 is small (N=100).** The target population on dev is ~6
  gold-in-claims full-recall wrong rows (step-2 dev baseline). A +0.02 EM
  gate is 2 rows — inside the ±3-row temp-0.0 noise band. The gate is a
  smoke test, not a verdict; the mechanism must also fix more than it
  breaks *on the rows it triggers on* (recorded per row), and the final
  word is the one Test-400 confirmation of the improved system.
- **The re-read may just repeat the draft.** The grounded reader sees the
  same claims the draft was based on. The contested prompt makes the
  disagreement explicit, but there is no guarantee the reader switches to
  the gold claim. If the A/B shows triggers with no fixes, the mechanism
  is dropped, not tuned further on dev.
- **Cache.** Both A/B arms run with fresh namespaces; verify `cache_hits`
  before believing the paired comparison (step-1 lesson: a v2 cache key
  made a run effectively all-live and flipped 8 untouched rows).
- **Model drift.** The dev baseline is re-run fresh alongside the
  contested arm (not compared against the Nov-9 policy file), so a
  silent Groq model update affects both arms equally.

## Out of scope

- H13 (second extraction pass) and H14 (eager SC) — separate changes.
- Any theta_abs change (would raise the wrong-answer rate; against the
  paper's first objective).
- Any Test-400 selection: Test-400 rows above are diagnosis only.
