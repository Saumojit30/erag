# Proposal: Tune-Memory-Effectiveness — Component test of the verified-belief memory module (tuning step 6)

## Status

Draft — prepared 2026-11-09 from `docs/tuning-master-plan.md` (§3.6), the
H5 assessment in `docs/hypotheses-h1-h6-assessment.md`, `research/openspec_memory.md`,
`research/decisions.md` D-009, and fresh recomputation from the stored E5
stream files (see Why; all numbers recomputed from stored rows, deduplicated
by id keeping the last row). Branch `trueadaptive`. No code written yet.
Sixth and last tuning change; one OpenSpec change per tuning step ("for
each step use openspec along the way", user 2026-11-09). Steps 1 (reader
grounding) and 2 (claim extraction) are built, gated, and archived. Step 3
(unknown prompt) is built, gated, archived — gate failed, mechanism
dropped. Step 4 (`tune-theta-abs`) is undecided at the time of writing and
step 5 (`tune-hop2-sc-cap`) is drafted; both run BEFORE this step's A/B —
see the steps-4/5 dependency below.

**Decisions — resolved:**
1. This is a **component test, not a tuning step.** The memory module is
   a distinct part of the architecture with its own hypothesis (H5), and
   it must be gated **before** the Test-400 freeze (§4.1 of the master
   plan), because enabling it would change the frozen system. Nothing in
   this change tunes the memory module's own thresholds
   (`theta_mem`, `theta_surprise`, `theta_write`, `w_mem`, `decay`,
   `capacity`) — those are frozen as implemented. If the test is null,
   the finding is "the module as configured does not demonstrate
   effectiveness on this stream", not an invitation to re-tune it inside
   this change. Threshold tuning, if ever wanted, is its own change.
2. **The instrument is the E5 stream design, not Dev-100.** Dev
   questions are independent and shuffled; memory would almost never
   fire (`mem_used` ≈ 0) and the A/B would be vacuous. The stream is
   entity-sharing clusters, where later questions reuse facts
   established in earlier ones.
3. **The stream is EXTENDED before running: 30 → 60 questions
   (5 → 10 clusters × 6).** The E5 instrument (N=30) is too weak to
   resolve the question it asks — see Why. The extension preserves the
   E5 instrument (first 30 rows byte-identical, in order) and adds 5
   new clusters built by the identical construction as
   `scripts/make_stream.py`. Decided up front, in this proposal — not
   after seeing results. The raw pool file is absent from this VM, so
   the extension has a scripted fetch prerequisite and a pre-registered
   fallback (tasks.md A.0).
4. **Fresh cache namespaces per arm.** The E5 null is confounded by
   cache replay (see the correction note in design.md): the mem arm
   served 30/30 rows from cache. This change uses one fresh namespace
   per arm and gates on live calls as well as total calls.
5. **Steps-4/5 dependency.** This change's A/B runs on the tuned system
   as it stands AFTER steps 4 and 5, and its baseline is the post-step-5
   tuned stream run — the nomem arm of this A/B *is* the baseline, so no
   separate baseline file is needed, but the tuned values it carries
   (`theta_abs` from step 4, `max_hops` from step 5, plus
   `ground_final_read=true`, `max_claims=8`, `unknown_prompt="base"`
   from steps 1–3) must be verified against the step-4/5 changes before
   running, and are NOT assumed here. If step 4 is skipped, `theta_abs`
   stays 0.4; if step 5's cap fails, `max_hops` stays 2. The A/B
   commands in tasks.md must be verified against the step-4/5 changes
   before running.

## Why

**Prior evidence is a null — and the null is uninformative, twice over.**

E5 (Reference system, 30 questions, 5 entity-sharing clusters), recomputed
from the stored files:

| Arm | EM | F1 | calls/Q | retrievals/Q | cache_hits/Q | fired rows |
|---|---|---|---|---|---|---|
| nomem | 0.4000 | 0.4828 | 14.30 | 2.50 | 0.27 | 0/30 |
| mem | 0.4000 | 0.4828 | 14.30 | 2.50 | **14.30** | 2/30 |
| planted | 0.4000 | 0.4828 | 14.30 | 2.50 | **14.30** | 2/30 |

- **Uninformative reason 1 — the fire rate.** Memory fired on 2/30
  rows (6.7%): row idx 20 (cluster 3, position 2) and row idx 29
  (cluster 4, position 5). Both are later positions in their clusters,
  consistent with the hypothesis that benefit concentrates in later
  questions — but with 2 rows able to differ, the maximum observable EM
  swing from memory is 2/30 = 6.7 pts, and the observed swing is 0.
  The instrument cannot resolve the question it asks.
- **Uninformative reason 2 — the cache.** The mem arm's rows are
  identical to the nomem arm's rows in EVERY field except `mem_used`
  (verified per row: the only differing field, excluding cache/latency
  fields, is `mem_used`). `cache_hits == llm_calls` on 30/30 mem rows
  and 30/30 planted rows. The E5 suite (`scripts/run_memory_suite.py`)
  ran all three arms with no `run.cache_namespace` override, so all
  three shared the default namespace (`test_v1`, from
  `configs/final.yaml`) and the mem/planted arms replayed the nomem
  arm's cached completions. Memory changed no LLM prompt in E5 — it
  could not have, because a changed prompt would have missed the cache.
  The E5 effectiveness null is therefore a null *of a replay*, not a
  null of memory. (The override mechanism is NOT cache-confounded: it
  is observed through local-NLI `mem_events`, and it did fire — row 20,
  the false Wolfgang Becker belief deleted on contradiction.)
- **Noise.** N=30 gives a ±18 pt 95% CI on a proportion
  (SE = √(0.25/30) ≈ 0.091). N=60 halves the variance
  (SE ≈ 0.065, ±12.7 pts) and doubles the expected firing rows to ~4.
  The binding constraint is the fire rate, not N — which is why the
  gate carries a pre-registered fire-rate floor (design.md) instead of
  pretending N=60 alone fixes the power problem.

**Position split on E5** (position = row index within its 6-question
cluster; early 0–1, mid 2–3, late 4–5; n=10 per band, both arms
identical except `mem_used`):

| Band | EM | calls/Q | retrievals/Q | fired (mem arm) |
|---|---|---|---|---|
| early 0–1 | 0.5000 | 14.20 | 2.50 | 0 |
| mid 2–3 | 0.4000 | 13.70 | 2.40 | 1 |
| late 4–5 | 0.3000 | 15.00 | 2.60 | 1 |

EM falls with position (0.50 → 0.40 → 0.30) — later questions are
harder, or the clusters differ. Position and cluster identity are
entangled (each cluster occupies fixed positions), so the position
split is descriptive; the causal contrast is the paired mem-vs-nomem
difference WITHIN each band (same questions, both arms), which the new
analyzer section reports.

**The override test, as designed, overstates the protection** (H5
assessment). Among *retrieved* false beliefs the override rate is 1/1
— the mechanism works when it fires. Among *planted* beliefs it is
1/5, because the other four never passed the similarity threshold
(θ_mem 0.75) for any question and were never considered. The gate
below is therefore stated on retrieved beliefs, with the retrieved
count reported — and the four unretrieved beliefs are a coverage gap
(read threshold too strict, or stream questions that did not match),
reported as such.

**Why the tuned system may behave differently from E5's Reference.**
E5 ran Reference; step 6 runs the tuned TrueAdaptive system. Two
interactions matter and are reported, not assumed:
- Memory is READ once per question, right after the initial retrieval
  (`src/systems/erag.py`, Step 1) and BEFORE the hop loop and the Fast
  Path — so the Fast Path does not bypass the read. But the WRITE is
  surprise-gated (`memory.write`: only when c0 < 0.6 or a contradiction
  was seen), and Fast-Path rows carry c0 = min_eff (typically high), so
  they do not write. On the tuned system the store fills only from
  low-confidence rows — by design, but slowly. Store growth is a
  reported measure (tasks.md B.1 adds the field); if the store stays
  near-empty, the test is testing an empty memory, and that is the
  finding.
- The memory's similarity space is MiniLM embeddings
  (`configs/base.yaml`: `retrieval.embedder:
  sentence-transformers/all-MiniLM-L6-v2`), built by the runner
  regardless of retriever — so BM25 stream runs with memory enabled
  work, and the similarity threshold θ_mem = 0.75 is a MiniLM cosine,
  independent of the BM25 retriever.

## What Changes — step 6

**A stream A/B on the tuned system (extended stream, N=60), memory off
vs on, plus a planted override run — with the gate pre-registered in
design.md.** The A/B is three runs on the extended stream manifest
(`data/manifests/stream.jsonl`, extended to 60 rows by tasks.md B.0):
nomem (memory off), mem (memory on), planted (memory on + the same 5
planted beliefs from `data/manifests/planted.json`, unchanged). Fresh
cache namespace per arm. The analyzer (`scripts/eval_memory.py`) gains
a `--position` section reporting per-arm EM/F1/calls/live-calls/
retrievals, fire rate, position splits, fired-row paired differences,
override rate among retrieved beliefs, and store growth — verified
against the E5 numbers above before any live run (tasks.md A.2). Two
measurement-only row fields are added (`mem_store_size`,
`mem_texts`) to close the E5 provenance gap (used-belief texts were
not recoverable from stored rows). If the gate passes, the frozen
tuned config (written at end of Phase 1) records `memory.enabled:
true`; if it fails, memory stays OFF for Test-400 and the paper
reports it as a null — the override mechanism verified, the
effectiveness not demonstrated. A null here does not block Phase 2; it
scopes the paper's claims.

## Considered alternatives

- **Run N=30 as-is, no extension.** Rejected: the E5 instrument is
  known-uninformative (2 firing rows, max 6.7 pt swing). Running it
  again on the tuned system would spend ~450 live calls to re-measure
  a test that cannot resolve the question. The extension is the
  cheaper option — one scripted data-prep task — and its fallback
  (N=30 if the raw file cannot be obtained) is pre-registered, not
  decided after seeing results.
- **Extend further, to N=90 or N=120.** Rejected: the binding
  constraint is the fire rate (6.7%), not N. N=90 expects ~6 firing
  rows against N=60's ~4 — a marginal gain for 50% more live calls
  and 5 more clusters to construct, while the stream stops resembling
  the E5 instrument the hypothesis was validated against. The
  fire-rate floor in the gate governs interpretability at any N; if
  the extended stream still fires <5 rows, the verdict is "instrument
  too weak", not a bigger-N rerun.
- **Tune the memory thresholds (e.g. lower θ_mem to raise the fire
  rate) inside this change.** Rejected: this is a component TEST of
  the module as implemented, not a tuning step. Lowering θ_mem would
  test a different module than the one H5 describes and would
  confound the verdict (a gain could be the threshold, not the
  memory). Threshold tuning, if ever wanted, is its own OpenSpec
  change with its own gate.
- **Test memory on Dev-100 instead of the stream.** Rejected (plan
  §3.6): dev questions are independent and shuffled; memory would
  almost never fire and the A/B would be vacuous.
- **Test memory on Test-400 directly.** Rejected: Test-400 is the
  frozen confirmation set, run once at the end on the frozen system
  (§4 of the master plan). Enabling an untested module on it would
  contaminate the confirmation run. The stream gates the freeze; the
  freeze gates Test-400.
- **Keep the E5 three-arm layout but reuse one namespace (as E5
  did).** Rejected: that is exactly the confound that made the E5
  effectiveness null uninterpretable. Fresh namespace per arm, live
  calls reported per arm.

## Non-goals (step-6 scope guard)

- Not a retriever, threshold, graph, NLI, prompt, or re-read change.
  `theta_abs`, `max_hops`, the Fast-Path gate, and the sequential-SC
  settings are untouched. Steps 4 and 5 own those.
- Not a change to the memory module's behavior. Surprise-gated
  writes, NLI-verified reads, contradiction override, decay, and
  capacity are exactly as implemented (`src/systems/memory.py`).
  The only code in this change is measurement-only row fields
  (tasks.md B.1).
- Not a Test-400 run. The confirmation run comes once, after all
  tuning steps, on the frozen system.
- Not a rewrite of the stream's first 30 rows. They stay
  byte-identical and in order, so the E5 baseline remains comparable.

## Impact

- **Code:** measurement-only — two row fields in `run_erag`'s output
  dict (`mem_store_size`, `mem_texts`), behind no flag, covered by
  mocked tests (tasks.md A.1/B.1). No change to `BeliefMemory`,
  `run_erag`'s logic, the runner, or any config default.
  `memory.enabled` stays `false` in `configs/base.yaml`; the mem and
  planted arms enable it via `--set` only.
- **Data:** the stream manifest grows 30 → 60 rows (tasks.md B.0),
  plus a committed sidecar `data/manifests/stream_clusters.json`
  (id → {cluster, position}, the 5 new title lists, raw-file SHA).
  The first 30 rows are byte-identical. `planted.json` is unchanged.
  The raw pool file (`data/raw/hotpot_dev_distractor_v1.json`) is
  fetched, not committed.
- **Tests:** mocked tests for the two new row fields; the analyzer's
  `--position` section verified against the E5 numbers above before
  any live run (tasks.md A.2).
- **Evaluation:** three stream runs on the tuned system (nomem / mem /
  planted), N=60 each, fresh namespaces. Gate (per design.md,
  pre-registered): fire-rate floor (≥5/60 firing rows) AND (EM gain
  OR call reduction with EM not falling) AND override test passes.
  Expected live-call cost ≈ 900–1,400 calls total (60 Qs × ~5–8
  calls/Q tuned × 3 arms).
- **Cache:** fresh namespace per arm
  (`stream_tuned_nomem_v1`, `stream_tuned_mem_v1`,
  `stream_tuned_planted_v1`); live calls/Q (`llm_calls −
  cache_hits`) reported per arm so a replay cannot masquerade as a
  result (E5 lesson).
- **Branches:** work on branch `trueadaptive`. Nothing is pushed.

## Follow-up changes (one per tuning step)

- None after this step in Phase 1. After step 6 closes: freeze
  `configs/erag_trueadaptive_tuned.yaml` (incl. the memory on/off
  decision from this step), then Phase 2 Test-400 confirmation.
- Possible follow-up if the fire-rate floor fails: a separate change
  to the memory module's read threshold or write gate — as its own
  change, with its own gate, not inside this one.

## References

- Master plan: `docs/tuning-master-plan.md` (§3.6 — the full step-6
  spec; §9 open decision 3b, the memory on/off decision)
- H5 assessment: `docs/hypotheses-h1-h6-assessment.md` (H5 section)
  and `docs/hypotheses-current-status.md`
- Memory proposal + decision: `research/openspec_memory.md`,
  `research/decisions.md` D-009 (2026-11-06, APPROVED & VERIFIED)
- Module: `src/systems/memory.py` (`BeliefMemory`); wiring:
  `src/systems/erag.py` (read at Step 1, line ~166; write at line
  ~350; row fields at lines ~367–368); runner:
  `scripts/run_experiment.py` (memory construction lines ~183–191,
  embedder line ~165); E5 suite: `scripts/run_memory_suite.py`
  (the no-namespace-override layout this change corrects);
  analyzer: `scripts/eval_memory.py`; stream construction:
  `scripts/make_stream.py`; manifests: `data/manifests/stream.jsonl`
  (30 Qs), `data/manifests/planted.json` (JSON array, 5 beliefs)
- Baselines: E5 nomem/mem/planted EM 0.4000, F1 0.4828, 14.30
  calls/Q, 2.50 retrievals/Q; fired rows idx 20 and 29; override
  1/1 retrieved (Becker), 1/5 planted. Cache: mem/planted
  14.30/14.30 cache hits (100% replay); nomem 0.27.
