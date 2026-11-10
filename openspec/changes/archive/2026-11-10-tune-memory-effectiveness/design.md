# Design: Tune-Memory-Effectiveness — Component test of the verified-belief memory module (tuning step 6)

## Mechanism (pre-registered)

Three runs on the extended stream manifest (`data/manifests/stream.jsonl`,
60 rows after tasks.md B.0), on the tuned system (TrueAdaptive + all
gated tuning steps), BM25, k=3, distractor:

| Arm | `memory.enabled` | `memory.plant` | Namespace | Output file |
|---|---|---|---|---|
| nomem | false (default) | — | `stream_tuned_nomem_v1` | `results/stream_tuned_nomem_v1.jsonl` |
| mem | true | — | `stream_tuned_mem_v1` | `results/stream_tuned_mem_v1.jsonl` |
| planted | true | `data/manifests/planted.json` | `stream_tuned_planted_v1` | `results/stream_tuned_planted_v1.jsonl` |

- The tuned system is the post-steps-4/5 system: `ground_final_read=true`,
  `max_claims=8`, `unknown_prompt="base"` (steps 1–3), plus `theta_abs`
  from step 4 and `max_hops` from step 5. The exact `--set` for each arm
  MUST be verified against the step-4/5 changes before running
  (tasks.md C.1); no tuned value is assumed here. If step 4 was skipped,
  `theta_abs` stays 0.4; if step 5's cap failed, `max_hops` stays 2.
- Memory thresholds are FROZEN as implemented (`configs/base.yaml`):
  `theta_mem: 0.75`, `theta_surprise: 0.6`, `theta_write: 0.7`,
  `w_mem: 0.5`, `decay: 0.98`, `capacity: 200`. No threshold is touched
  by any arm. The similarity space is MiniLM embeddings (the runner
  always builds the embedder, `scripts/run_experiment.py:165`),
  independent of the BM25 retriever.
- The planted arm uses the SAME 5 planted beliefs as E5
  (`data/manifests/planted.json`, unchanged, JSON array). No new planted
  beliefs are added for the new clusters: the override test is a
  mechanism test, and its denominator is retrieved beliefs (see Gate).
- Runs are sequential, detached, in order nomem → mem → planted (the
  planted arm's store is independent — each run constructs a fresh
  `BeliefMemory`, so arm order cannot contaminate arm state; the order
  is for log readability only). Each run uses `--set` in ONE flag
  (repeated `--set` overwrites; only the last survives — the step-1
  lesson). Crash recovery (the runner skips ids already in the output
  file) applies as usual; rows are deduplicated by id keeping the LAST
  row before analysis.

**The extended stream (tasks.md B.0, decided up front).** 5 new
entity-sharing clusters × 6 questions = 30 new rows, appended after
the original 30 in order; the original 30 rows stay byte-identical and
in order. Construction is identical to `scripts/make_stream.py`: each
new cluster is a title list of named entities (people, battles,
universities, films, or the same kinds of entity families), 6 distinct
questions per cluster selected in raw-file order, no id overlap with
`debug`/`dev`/`test`/`stream`, no duplicate questions. The extension
script records the 5 new title lists, the id → {cluster, position}
mapping for all 60 rows, and the raw-file SHA in the sidecar
`data/manifests/stream_clusters.json` (committed). Position is read
from the sidecar by the analyzer, never inferred from row order alone.

**Measures (reported by the `--position` analyzer section, tasks.md
A.2).** Per arm: EM, F1, mean `llm_calls`/Q, mean LIVE calls/Q
(`llm_calls − cache_hits`), mean retrievals/Q, mean `cache_hits`/Q,
fire rate (rows with `mem_used > 0`), mean `mem_store_size` by
position, `mem_events` (overrides). Splits: early (position 0–1),
mid (2–3), late (4–5) — n=20 per band at N=60 — with the paired
mem-vs-nomem difference WITHIN each band. Fired-row paired
difference: on rows where the mem arm fired, mem-arm EM/calls minus
nomem-arm EM/calls on the SAME questions. Override rate: unique
planted beliefs overridden / planted beliefs retrieved in the planted
arm, plus a check that no planted-arm final answer equals a planted
false claim.

## Gate (pre-registered, before any run)

Memory enters the frozen Test-400 system ONLY if ALL of the following
hold on the extended stream (N=60 deduped, 0 failed rows per arm):

1. **Validity — fire-rate floor.** The mem arm fires (`mem_used > 0`)
   on ≥5 of 60 questions. Below 5, the test cannot resolve
   effectiveness however the EM numbers fall, and the verdict is
   **"instrument too weak"** — memory stays OFF, and the paper reports
   the test as under-powered, NOT as a null. (E5 fired on 2/30; at the
   same 6.7% rate, N=60 expects ~4 firing rows — the floor may fail,
   and that outcome is pre-registered here, not decided afterwards.)
2. **Effectiveness — EM gain OR call reduction with EM not falling.**
   Either ΔEM (mem − nomem) > 0, or Δcalls/Q < 0 with ΔEM ≥ −0.02
   (the H5 criterion's tolerance). Δ is on the full 60-row stream;
   the fired-row paired difference is reported alongside and must not
   contradict the full-stream direction (if the full stream gains but
   the fired rows lose, the gain is not attributable to memory and the
   gate does not pass).
3. **Override test passes.** Every planted belief retrieved in the
   planted arm (similarity ≥ θ_mem for some question) is overridden
   (deleted, `mem_events` entry `"overridden"`) before or when it
   would be used, AND no final answer in the planted arm equals a
   planted false claim. The retrieved count is reported; if ZERO
   planted beliefs are retrieved, the override half is
   **unresolved** (not passed, not failed) and the gate does not pass
   on this half alone — the mechanism cannot be re-verified on the
   tuned system without a retrieved false belief.

If the gate passes, the frozen tuned config records
`memory.enabled: true` (thresholds unchanged). If it fails on (2) with
(1) and (3) met, the verdict is a **clean null**: memory stays OFF,
H5 stays NOT SUPPORTED, and the paper reports it as mechanism-verified
/ effectiveness-not-demonstrated. If (1) fails, the verdict is
"instrument too weak" (see above). A null or too-weak verdict does
NOT block Phase 2; it scopes the paper's claims. No re-run with
different thresholds, no second stream, no gate revision inside this
change — any of those is a new change with its own gate.

## Correction note (applies the step-2/3 lesson — the E5 cache finding)

The E5 effectiveness null is confounded by cache replay, and this
change is designed around that fact. Evidence, recomputed from the
stored files (`results/stream_mem.jsonl`,
`results/stream_nomem.jsonl`, `results/stream_planted.jsonl`):

- `scripts/run_memory_suite.py` ran all three arms with NO
  `run.cache_namespace` override, so all three shared the default
  namespace (`test_v1`, from `configs/final.yaml`).
- The mem arm served `cache_hits == llm_calls` on 30/30 rows
  (mean 14.30/14.30); the planted arm likewise 30/30. The nomem arm
  served 0.27 cache hits/Q.
- The mem arm's rows are identical to the nomem arm's rows in EVERY
  field except `mem_used` (verified per row, excluding cache/latency
  fields). The cache key is a hash of `{namespace, model, messages,
  temperature, max_tokens, reasoning_effort, sample_idx}` (audit M3),
  and prompt text is in the key — so a memory passage that changed any
  LLM prompt would have missed the cache. Zero misses means memory
  changed no LLM prompt in E5. The E5 EM/calls identity (0.4000,
  14.30 in all three arms) is therefore a property of the replay, and
  the E5 null cannot be read as "memory does nothing".
- The override mechanism is NOT cache-confounded: it is observed
  through local-NLI `mem_events`, which do not go through the LLM
  cache. The row-20 Becker override stands as verified.

Consequences for this change, all pre-registered above: one fresh
namespace per arm; live calls/Q reported per arm; the gate's call
measure is computed on live calls as well as total calls; the
`--position` section reproduces the E5 cache numbers as part of its
verification (tasks.md A.2), so a replay in the new runs would be
visible immediately. Any arm whose live calls/Q is ~0 has not run —
it has replayed — and its results are discarded, not analyzed.

## Guardrails

- The frozen v1 config (`configs/erag_trueadaptive.yaml`) is NOT
  edited (step-3 lesson). `memory.enabled` stays `false` in
  `configs/base.yaml`; arms enable it via `--set` only. The tuned
  value is recorded for the frozen tuned config at end of Phase 1.
- No `src/` change except the two measurement-only row fields
  (tasks.md B.1). `BeliefMemory`, `run_erag`'s logic, the runner,
  and the NLI verifier are untouched.
- No threshold tuning, no retriever change, no prompt change, no
  re-read change, no Test-400 run.
- The first 30 stream rows are byte-identical; `planted.json` is
  unchanged; the raw pool file is fetched, never committed.
- Results files are committed on `trueadaptive` (as in steps 1–3);
  `results/cache.sqlite` and `results/nli_memo.pkl` are NOT committed.
- A Groq key is needed for the live runs, transiently, never saved.
  No GitHub token is needed for this change (no push in its tasks).

## Threats to validity

- **Small N, even extended.** N=60 gives a ±12.7 pt 95% CI on a
  proportion; the paired mem-vs-nomem difference is tighter (same
  60 questions, both arms) but the effect can only appear on firing
  rows, so the effective N is the firing count, not 60. The
  fire-rate floor exists for exactly this reason — but a floor of 5
  is itself a small sample for the fired-row paired difference, and
  a 5-row difference is fragile. The paper must report the firing
  count alongside any effect, not just the headline delta.
- **Position and cluster identity are entangled.** Each cluster
  occupies fixed positions, so the position split also compares
  different entity families (E5: EM 0.50 early vs 0.30 late may be
  cluster difficulty, not position). The causal contrast is the
  WITHIN-band paired difference, not the across-band levels. The
  analyzer reports both, and the gate uses only the paired
  full-stream delta.
- **Fire rate is a property of frozen thresholds, not of N.** If
  θ_mem = 0.75 is too strict, or the surprise gate starves the
  store, no stream size fixes the fire rate — extension buys rows,
  not firings. A too-weak verdict therefore points at the
  configuration, not at the idea, and the paper must say so. The
  store-growth measure exists to distinguish "nothing was written"
  from "beliefs were written but never matched".
- **Fast-Path / surprise-gate interaction.** On the tuned system the
  store fills only from low-confidence rows (c0 < 0.6 or
  contradiction). If the tuned system is confident on most stream
  questions, the store stays small and the test measures an empty
  memory. Store growth by position is reported so this is visible;
  it is not adjusted for inside this change.
- **The stream is synthetic.** Entity-sharing clusters built from
  HotpotQA dev questions are a constructed proxy for a real
  question stream, not a deployed workload. A positive result
  generalizes to "sequential streams with entity overlap", not to
  memory in general. The paper must scope the claim accordingly.
- **Planted beliefs target only the original 5 clusters.** The
  override test exercises the mechanism on 5 known-false beliefs
  about 5 entities. It verifies deletion on contradiction; it does
  not verify that a subtly-wrong belief (right entity, wrong
  detail) would be caught, nor that a true belief is never wrongly
  overridden (no false-override measure exists in this change —
  the mem arm's `mem_events` are reported, and any override of a
  TRUE stream belief would appear there and must be reported).
- **Single retriever, single LLM, single stream.** BM25, Groq
  `openai/gpt-oss-20b`, one 60-question stream — the same scope
  limits as the rest of Phase 1. The result is a component verdict
  on this configuration, not a general claim about episodic memory
  in RAG.
- **Cache discipline is load-bearing.** The entire effectiveness
  half of the gate rests on the fresh-namespaces rule. A namespace
  mistake (e.g. reusing `dev_trueadaptive_v1_bm25`, which holds
  dev answers) would replay dev prompts — but stream questions
  differ from dev questions, so the prompts would miss and the runs
  would go live; the dangerous mistake is reusing a namespace
  ACROSS the three stream arms, which is exactly the E5 error. The
  analyzer's live-calls check is the tripwire, and it is verified
  on E5 numbers before any live run.
- **Live-call nondeterminism.** The tuned system at temperature 0.0
  is not perfectly deterministic across runs (step 1: 8 untouched
  dev rows flipped between runs). The nomem/mem/planted arms share
  the tuned system, so run-to-run flips add noise to the paired
  difference; a 1–2 row EM difference is inside that noise and must
  not be over-read. The gate's ΔEM > 0 uses the observed delta with
  this caveat stated in the commit message.

## Outcome (to be filled when the change closes)

- Gate verdict: PASS (memory enters the frozen system) / clean null
  (memory stays OFF, H5 stays NOT SUPPORTED) / instrument too weak
  (fire-rate floor failed).
- Per-arm numbers, firing count, override rate among retrieved
  beliefs, and `cache_hits`/Q per arm.
