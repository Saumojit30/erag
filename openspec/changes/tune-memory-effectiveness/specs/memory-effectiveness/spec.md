# memory-effectiveness

## Purpose

The verified-belief memory module (`src/systems/memory.py`) is
implemented and wired but disabled by default (`memory.enabled:
false`), so all results so far are memory-off. Its only validation
(E5, Reference system, 30-question stream) was a null that is
uninterpretable as an effectiveness result: memory fired on 2/30
rows, and the mem arm replayed the nomem arm's cached completions
(30/30 rows with `cache_hits == llm_calls`). This change runs the
component test properly — on the tuned system, on an extended
60-question stream, with fresh cache namespaces per arm — and gates
whether memory enters the frozen Test-400 system. Sources:
`docs/tuning-master-plan.md` (§3.6),
`docs/hypotheses-h1-h6-assessment.md` (H5),
`research/openspec_memory.md`, `research/decisions.md` D-009.

## ADDED Requirements

### Requirement: Stream A/B runs memory off vs on vs planted on the tuned system

The system SHALL be run on the extended stream manifest
(`data/manifests/stream.jsonl`, 60 rows) in three arms — memory off,
memory on, memory on with the 5 planted beliefs from
`data/manifests/planted.json` — on the tuned system (TrueAdaptive +
all gated tuning steps), BM25, k=3, distractor, each arm in its own
fresh cache namespace, with results written to new files that do not
overwrite the E5 files.

#### Scenario: Three arms, three namespaces

- **WHEN** the stream A/B runs
- **THEN** the nomem, mem, and planted arms use namespaces
  `stream_tuned_nomem_v1`, `stream_tuned_mem_v1`, and
  `stream_tuned_planted_v1` respectively, and no arm reuses another
  arm's namespace

#### Scenario: Tuned values carried forward

- **WHEN** the A/B commands are assembled
- **THEN** they carry all tuned values from steps 1–5
  (`ground_final_read`, `max_claims`, `unknown_prompt`,
  `theta_abs` from step 4, `max_hops` from step 5), verified against
  the step-4/5 changes — none assumed

### Requirement: Extended stream preserves the E5 instrument

The extended stream manifest SHALL contain the original 30 rows
byte-identical and in order, followed by 30 new rows in 5 new
entity-sharing clusters of 6 questions each, built by the same
construction as `scripts/make_stream.py`, with no id overlap with
the debug/dev/test/stream manifests and no duplicate questions. A
committed sidecar (`data/manifests/stream_clusters.json`) SHALL map
every question id to its {cluster, position} and record the 5 new
title lists and the raw-file SHA.

#### Scenario: First 30 rows unchanged

- **WHEN** the extended manifest is written
- **THEN** its first 30 rows are byte-identical to the pre-extension
  file, in the same order

#### Scenario: New clusters follow the same construction

- **WHEN** a new cluster is built
- **THEN** it is a title list of named entities with 6 distinct
  questions selected in raw-file order, excluding all frozen ids

### Requirement: Row records memory use, events, store size, and used-belief texts

Each stored row SHALL carry `mem_used` (count of memory passages
returned for that question), `mem_events` (override events, with
belief text), `mem_store_size` (post-row memory store size), and
`mem_texts` (texts of the passages memory returned; empty when memory
is off or nothing fired), alongside the existing `llm_calls`,
`cache_hits`, `retrievals`, `em`, `f1`, `answer`, and `gold` fields.

#### Scenario: Memory off writes zeros

- **WHEN** memory is disabled for a run
- **THEN** every row carries `mem_used` 0, `mem_events` [],
  `mem_store_size` 0, and `mem_texts` []

#### Scenario: Fired rows record what was used

- **WHEN** memory returns passages for a question
- **THEN** the row's `mem_texts` lists exactly those passages'
  texts and `mem_used` equals their count

### Requirement: Analyzer reports per-arm and position-split memory measures

The analyzer (`scripts/eval_memory.py`, `--position` section) SHALL
report, per arm, EM, F1, mean `llm_calls`/Q, mean live calls/Q,
mean retrievals/Q, mean `cache_hits`/Q, fire rate, mean
`mem_store_size` by position band, and `mem_events`. It SHALL also
report the position split (early 0–1, mid 2–3, late 4–5) with the
paired mem-vs-nomem difference within each band, the fired-row
paired difference, and the planted override rate among retrieved
beliefs with the false-claim-in-answer check.

#### Scenario: Live calls are reported per arm

- **WHEN** the section runs on any three-arm set
- **THEN** mean live calls/Q is shown for each arm, so a replayed
  arm (live calls/Q ≈ 0) is visible immediately

### Requirement: Analyzer reproduces the E5 numbers

Run on the E5 files, the `--position` section SHALL reproduce the
E5 numbers listed in the scenario below.

#### Scenario: Section reproduces known stored-file numbers

- **WHEN** the `--position` section runs on the E5 files
- **THEN** it reports: nomem EM 0.4000, F1 0.4828, 14.30 calls/Q,
  2.50 retrievals/Q, 0.27 cache_hits/Q; mem identical except 14.30
  cache_hits/Q and fired rows idx 20 and 29; position splits early
  EM 0.5000 / 14.20 calls, mid EM 0.4000 / 13.70 calls, late EM
  0.3000 / 15.00 calls; planted override 1 unique belief / 5
  planted, 1/1 retrieved

### Requirement: Contradicted beliefs are deleted and logged (override contract)

A stored belief contradicted by fresh evidence SHALL be deleted from
memory and logged as a `mem_events` entry with event `"overridden"`,
the belief text, and the contradicting passage titles — the contract
verified in E5 (D-009) and re-verified on the tuned system by the
planted arm of this change.

#### Scenario: Retrieved false belief is purged

- **WHEN** a planted false belief is retrieved and fresh evidence
  contradicts it
- **THEN** the belief is deleted and an `"overridden"` event is
  recorded with its text

#### Scenario: Unretrieved beliefs stay dormant

- **WHEN** a planted belief never passes the similarity threshold
  for any question
- **THEN** it is neither overridden nor used, and the override rate
  is computed over retrieved beliefs only, with the retrieved count
  reported

### Requirement: Memory thresholds and the frozen config are unchanged

This change SHALL NOT modify any memory threshold (`theta_mem`,
`theta_surprise`, `theta_write`, `w_mem`, `decay`, `capacity`), the
`BeliefMemory` logic, `run_erag`'s logic, or the frozen v1 config
(`configs/erag_trueadaptive.yaml`). `memory.enabled` stays `false`
in `configs/base.yaml`; arms enable it via `--set` only.

#### Scenario: Frozen config untouched

- **WHEN** the change is complete
- **THEN** `configs/erag_trueadaptive.yaml` is byte-identical to
  its pre-change state
