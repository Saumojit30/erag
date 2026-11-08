# Cache namespaces and key versioning

How the shared LLM cache (`results/cache.sqlite`) stays safe to reuse — and
when it must not be reused. Written for the audit remediation (audit M3, L4),
2026-11-09.

## The namespace-rotation rule

**A new system or a new split gets a new cache namespace. Never reuse a
namespace across systems or splits.** The cache key is prompt-based, not
system-based, so two systems asking the same prompt share the cached
completion — that is exactly how Standard ended up replaying E-RAG's hop-0
drafts 400/400 on test (audit H2). Namespaces are the only isolation between
systems; there is no per-system field in the key.

## Key version (audit M3)

`src/llm/client.py` carries `CACHE_KEY_VERSION` (currently **2**), included
in every cache-key payload. Bump it whenever the *meaning* of a cached
completion changes — a code change that alters how identical completions are
used downstream (e.g. a different `w_c`, a changed abstention rule, a
changed claim-extraction step). Prompt text is already in the key, so prompt
edits create new keys on their own; the version covers everything else.

**Consequence:** old rows never hit under a new key version. The next run in
an old namespace re-fetches every completion live instead of replaying the
cache. That is the intended safety behavior, not a bug — it is cheaper than
a silently poisoned comparison. Version 1 is the pre-2026-11-09 key (no `v`
field in the payload); version 2 is the first versioned key.

## Namespaces in use

| Namespace | Used by |
|---|---|
| `dev_v1` | Reference dev (original `erag_active_dev.jsonl` and cost-opt `erag_reference_dev.jsonl`), Standard/IRCoT dev, pooled ablation run |
| `dev_cost_opt_v1` | Balanced and Cost dev |
| `test_v1` | All Phase 3/4/5 test systems (Standard, IRCoT, E-RAG Reference/Balanced/Cost, BM25, E5, BGE) — shared |
| `dev_trueadaptive_v1` | TrueAdaptive MiniLM Dev-100 |
| `dev_trueadaptive_v1_bm25` | TrueAdaptive BM25 Dev-100 |
| `test_trueadaptive_v1_bm25` | TrueAdaptive BM25 Test-400 (commit `d69490f`) |
| `test_ircot_v1_bm25` | IRCoT BM25 Test-400, fresh rerun (commit `d69490f`) |

## MLflow provenance (audit L4)

MLflow tracking (`mlruns/` + `mlflow.db`, gitignored, local only) covers
**only the TrueAdaptive runs**. No MLflow runs exist for any Phase 2/3/4/5
experiment — those scripts never logged MLflow. For pre-TrueAdaptive
experiments the record is the results files plus git commits.

Two L4 fixes applied 2026-11-09 (see `scripts/run_experiment.py` and the
local `mlflow.db`):

- `run_experiment.py` now sets the `mlflow.source.git.repoURL` tag
  explicitly from `git remote get-url origin` (actual origin:
  `https://github.com/Saumojit30/erag.git`). MLflow's auto-detection had
  recorded the fetch-only upstream `https://github.com/ManojAdapakala/ERag.git`
  on all four TrueAdaptive runs.
- The zombie RUNNING run `eafdc209` (the killed first Dev-100 run) was closed
  (set to FINISHED).
