# Results — provenance record

This file is the provenance record for every file under `results/`, written for the
paper (audit M2, `docs/audit-cache-dataset-integrity.md`). For each file it gives the
system/config that produced it, the LLM-cache namespace it ran under, and the commit
that first tracked it. **"unknown" means the provenance could not be established from
evidence in the repo — it is not a guess.** Row-level `system`/`setting`/`split` fields
exist only in files produced by `scripts/run_experiment.py` (TrueAdaptive runs,
`ircot_test_bm25.jsonl`, and the `erag_active_*` / `erag_observe_*` / `standard_*` /
`ircot_*` / `closed_book_*` baselines); older Phase 2/3/4/5 rows are filename-only
(audit L5). EM figures below are means of the stored `em` field, recomputed from the
files on 2026-11-09.

## Shared context (applies to all files)

- **Generator for every run:** `openai/gpt-oss-20b` via Groq (`configs/base.yaml`, `model.name`).
  Any report naming another generator (e.g. `meta-llama/llama-3.3-70b-versatile`) is wrong (audit H1).
- **Default retriever:** MiniLM (`sentence-transformers/all-MiniLM-L6-v2`, k=3, distractor
  setting) unless the file or table says BM25 / E5 / BGE.
- **Cache namespaces** (audit §"Cache key and namespaces"; namespaces are hashed into cache
  keys, so the DB cannot be enumerated by namespace):

  | Namespace | Used by |
  |---|---|
  | `dev_v1` | Reference dev (`erag_active_dev.jsonl`), cost-opt Reference dev, Standard/IRCoT dev, pooled ablation |
  | `dev_cost_opt_v1` | Balanced and Cost dev (`results/cost_opt/`) |
  | `test_v1` | All Phase 3/4/5 test systems (Standard, IRCoT, E-RAG Reference/Balanced/Cost, BM25, E5, BGE) |
  | `dev_trueadaptive_v1` | TrueAdaptive MiniLM Dev-100 |
  | `dev_trueadaptive_v1_bm25` | TrueAdaptive BM25 Dev-100 |
  | `test_trueadaptive_v1_bm25` | TrueAdaptive BM25 Test-400 |
  | `test_ircot_v1_bm25` | IRCoT BM25 Test-400 (fresh run) |

- **Cache sharing — read before citing (audit H2).** Systems share one cache
  (`results/cache.sqlite`): `llm_calls` counts cache hits as calls, so reported
  "mean calls/Q" is mostly cache replay for the older systems (e.g. Balanced Test-400:
  8.56 calls/Q but only ~0.3 live; cost-opt Reference dev: 14.46 calls/Q, 100% replay,
  0 live). Live calls = `llm_calls` − `cache_hits` per row. Standard's answers are
  E-RAG's hop-0 drafts replayed (400/400 test, 100/100 dev), so the systems are **not
  independent measurements**. TrueAdaptive runs are clean: 0 cache hits, all calls live.
- **MLflow:** only TrueAdaptive runs have MLflow records (`mlflow.db`, gitignored, not in
  the repo): 7 runs as of 2026-11-09, all from `scripts/run_experiment.py` — see
  `results/trueadaptive/` below. No MLflow runs exist for any Phase 2/3/4/5 experiment;
  for those, the results files + git commits are the record. The MLflow `repoURL` tag
  wrongly points at `https://github.com/ManojAdakapala/ERag.git` (fetch-only upstream);
  the actual origin is `Saumojit30/erag` (audit L4). Two runs are stuck RUNNING
  (`eafdc209…`, killed first Dev-100 run; `c0fac8fb…`, Test-400 run interrupted by a
  runtime restart).
- **First-tracked commit:** most pre-TrueAdaptive files were first tracked in bulk in
  `3a4b9ba` ("feat(results): track benchmark evaluation outputs and response cache",
  2026-11-08). That is the commit the file entered git, **not** necessarily the commit
  that produced the run — the runs themselves predate tracking, and their producing
  commit is unknown unless stated otherwise.

## ⚠️ `erag_active_dev_pooled.jsonl` — MUST NEVER ENTER HEADLINE AGGREGATIONS (audit M4)

`results/erag_active_dev_pooled.jsonl` (N=100, EM 0.37, 15.95 calls/Q) is a
**pooled-corpus run**: `scripts/run_ablations.py` ran it with
`retrieval.setting=pooled`, which builds **one index from dev+test items together** —
test gold paragraphs were retrievable during a dev run (and vice versa). Its EM is
lower than the distractor run (0.37 vs 0.39), so nothing was inflated, but the file
sits alongside headline files and **must never be averaged into any benchmark table,
headline EM, or paper claim**. The data rows are left untouched; this warning is the
record. The same applies to the pooled row in `research/methodology_audit/` outputs
derived from it.

**Table-generator warning:** `scripts/export_ablation_results.py` still lists this file
as an ablation row ("Pooled Setting (1,000 paras)") **by default** — do not reuse its
output for headline tables without removing that row first. (The script itself was
not edited here; that is a separate fix.) `scripts/make_tables.py` uses explicit
per-system filenames and does **not** include `*_pooled` (checked 2026-11-09: no
`pooled` reference, no results-glob that could pick it up). `scripts/compute_all_sensitivities.py`
hardcodes the pooled numbers as sensitivity-matrix entry `F4_setting_pooled`
(EM 0.37, 15.95 calls/Q) — it reads no pooled file, but its output is a sensitivity
analysis, not a headline table.

## Field semantics — `draft` is the LAST hop's draft, not hop-0's (audit L6)

In E-RAG result rows, `draft` equals the **final hop's** draft. Verified from the raw
files on 2026-11-09: `draft == trace[0].answer` (the hop-0 draft) for only **281/400**
test rows (`results/erag_active_test.jsonl`) and **62/100** dev rows
(`results/erag_active_dev.jsonl`); `draft == trace[-1].answer` for **400/400** test and
**100/100** dev rows. The correct hop-0 draft is `trace[0].answer` (trace entries carry
`hop` / `answer` / `pool` / `graph` — there is no `draft` key inside a trace entry).
Anyone analyzing "the draft" — e.g. comparing with Standard — must use `trace[0]`,
not the row `draft` field. (The trace, not `draft`, is what matches Standard 400/400.)

## `results/` (top level)

| File | N | System / config | Cache namespace | First tracked | Notes |
|---|---|---|---|---|---|
| `closed_book_debug.jsonl` | 50 | Closed-Book, unknown producer script | unknown | `3a4b9ba` | EM 0.24; no retrieval |
| `closed_book_dev.jsonl` | 100 | Closed-Book, unknown producer script | unknown | `3a4b9ba` | EM 0.19 |
| `closed_book_test.jsonl` | 400 | Closed-Book, `scripts/run_test_suite.py`, `base.yaml` + `final.yaml` | `test_v1` | `3a4b9ba` | EM 0.20 |
| `standard_debug.jsonl` | 50 | Standard RAG, unknown producer script | unknown | `3a4b9ba` | EM 0.38 |
| `standard_dev.jsonl` | 100 | Standard RAG, unknown producer script | `dev_v1` | `3a4b9ba` | EM 0.44; repeat in `standard_dev_rep.jsonl` (EM 0.44, producer unknown) |
| `standard_dev_rep.jsonl` | 100 | Standard RAG repeat, producer unknown | unknown | `3a4b9ba` | EM 0.44; temp-0 flip rate vs `standard_dev.jsonl` is 3/100 (audit H2) |
| `standard_test.jsonl` | 400 | Standard RAG, `scripts/run_test_suite.py`, `base.yaml` + `final.yaml` | `test_v1` | `3a4b9ba` | EM 0.4050; answers == E-RAG hop-0 drafts 400/400 (cache sharing, H2) |
| `ircot_debug.jsonl` | 50 | IRCoT, unknown producer script | unknown | `3a4b9ba` | EM 0.38 |
| `ircot_dev.jsonl` | 100 | IRCoT, unknown producer script | `dev_v1` | `3a4b9ba` | EM 0.44 |
| `ircot_test.jsonl` | 400 | IRCoT, `scripts/run_test_suite.py`, `base.yaml` + `final.yaml` | `test_v1` | `3a4b9ba` | EM 0.4250, 2.51 calls/Q |
| `ircot_test_bm25.jsonl` | 400 | IRCoT, `scripts/run_experiment.py`, retriever `bm25`, frozen | `test_ircot_v1_bm25` | `d69490f` | EM 0.4200, 2.54 calls/Q, 0 cache hits; fresh Test-400 run, MLflow run `9e3791a2…` (commit `4040bfc`) |
| `erag_observe_debug.jsonl` | 50 | E-RAG Observe, unknown producer script | unknown | `3a4b9ba` | EM 0.38 |
| `erag_observe_dev.jsonl` | 100 | E-RAG Observe, unknown producer script | unknown | `3a4b9ba` | EM 0.44 |
| `erag_observe_test.jsonl` | 400 | E-RAG Observe, `scripts/run_test_suite.py`, `base.yaml` + `final.yaml` | `test_v1` | `3a4b9ba` | EM 0.4050 |
| `erag_active_debug.jsonl` | 50 | E-RAG Reference (Active), unknown producer script | unknown | `3a4b9ba` | EM 0.40 |
| `erag_active_debug_phase2_collapse.jsonl` | 50 | E-RAG Reference debug analysis output, producer unknown | unknown | `3a4b9ba` | EM 0.24; analysis output, not a benchmark cell (audit App. A) |
| `erag_active_dev.jsonl` | 100 | E-RAG Reference (Active), `configs/base.yaml` (`w_c: 2.0`), producer script unknown | `dev_v1` | `3a4b9ba` | EM 0.39, 14.72 calls/Q — differs from `cost_opt/erag_reference_dev.jsonl` (EM 0.50) **only** by `w_c` (see `results/cost_opt/`) |
| `erag_active_dev_pooled.jsonl` | 100 | E-RAG Reference (Active), `scripts/run_ablations.py`, `base.yaml`, `retrieval.setting=pooled` | `dev_v1` | `3a4b9ba` | ⚠️ **POOLED — never in headline aggregations** (see warning above). EM 0.37, 15.95 calls/Q |
| `erag_active_test.jsonl` | 400 | E-RAG Reference (Active), `scripts/run_test_suite.py`, `base.yaml` + `final.yaml` | `test_v1` | `3a4b9ba` | EM 0.4525, 14.22 calls/Q (9.47 live) |
| `erag_ablate_no_adaptive_dev.jsonl` | 100 | E-RAG ablation (no adaptive retrieval), `scripts/run_ablations.py`, `base.yaml` | `dev_v1` | `3a4b9ba` | EM 0.37 |
| `erag_ablate_no_fast_dev.jsonl` | 100 | E-RAG ablation (no Fast Path), `scripts/run_ablations.py`, `base.yaml` | `dev_v1` | `3a4b9ba` | EM 0.38 |
| `erag_ablate_no_eig_dev.jsonl` | 100 | E-RAG ablation (no EIG query selection), `scripts/run_ablations.py`, `base.yaml` | `dev_v1` | `3a4b9ba` | EM 0.37 |
| `erag_ablate_no_conf_dev.jsonl` | 100 | E-RAG ablation (no epistemic confidence), producer script unknown | unknown | `3a4b9ba` | EM 0.54 |
| `erag_ablate_no_nli_dev.jsonl` | 100 | E-RAG ablation (no NLI verification), producer script unknown | unknown | `3a4b9ba` | EM 0.47 |
| `erag_ablate_no_prop_dev.jsonl` | 100 | E-RAG ablation (no belief propagation), producer script unknown | unknown | `3a4b9ba` | EM 0.45 |
| `stream_mem.jsonl` | 30 | E-RAG Active + episodic memory, `scripts/run_memory_suite.py`, `base.yaml` + `final.yaml`, `data.split=stream` | `test_v1` (final.yaml default; no override in the suite) | `3a4b9ba` | EM 0.40; memory/stream proof-of-concept, not a benchmark cell |
| `stream_nomem.jsonl` | 30 | E-RAG Active, no memory, `scripts/run_memory_suite.py`, `base.yaml` + `final.yaml`, `data.split=stream` | `test_v1` (as above) | `3a4b9ba` | EM 0.40 |
| `stream_planted.jsonl` | 30 | E-RAG Active + memory + 5 planted false beliefs, `scripts/run_memory_suite.py`, `base.yaml` + `final.yaml`, `data.split=stream`, `memory.plant=data/manifests/planted.json` | `test_v1` (as above) | `3a4b9ba` | EM 0.40; planted beliefs are deliberate (audit I1) |
| `cache.sqlite` | — | LLM response cache (SQLite, table `c`, key = SHA-256 of `{namespace, model, messages, temperature, max_tokens, reasoning_effort, sample_idx}`) | all namespaces above | tracked (`3a4b9ba`; working copy modified since) | **26,488 rows as of 2026-11-09** (grows as runs happen; was 23,622 at the audit, 23,567 after the 2026-11-09 purge of 55 empty completions — audit M1, backup outside the repo). `PRAGMA integrity_check` = ok |
| `nli_memo.pkl` | — | NLI memoization store (pickled dict) | n/a | tracked (`3a4b9ba`; working copy modified since) | 26,701 pairs memoized as of 2026-11-09 |

## `results/trueadaptive/`

TrueAdaptive v1 (OpenSpec change `erag-trueadaptive`), branch `trueadaptive`, config
`configs/erag_trueadaptive.yaml` (frozen; sequential SC M=1→3, ΔH<0.05, SC gated behind
the Fast Path, `w_c: 1.0`), all via `scripts/run_experiment.py`, 0 cache hits (fresh
namespaces, all calls live).

| File | N | System / config | Cache namespace | Commit | Notes |
|---|---|---|---|---|---|
| `erag_trueadaptive_dev.jsonl` | 100 | TrueAdaptive v1, MiniLM, k=3, Dev-100 | `dev_trueadaptive_v1` | `ece1c0e` | EM 0.50, F1 0.6018, 4.91 calls/Q; gate met (≤6 calls, EM ≥0.50). MLflow run `9c479459…` (commit `719c285`) |
| `erag_trueadaptive_bm25_dev.jsonl` | 100 | TrueAdaptive v1, BM25, k=3, Dev-100 | `dev_trueadaptive_v1_bm25` | `ef937fc` | EM 0.56, F1 0.6495, 4.58 calls/Q. MLflow runs `0d5e1153…` / `610050d4…` (commit `e8f3c27`) |
| `erag_trueadaptive_test_bm25.jsonl` | 401 lines / **400 unique ids** | TrueAdaptive v1, BM25, k=3, Test-400 | `test_trueadaptive_v1_bm25` | `d69490f` | EM **0.4750**, F1 0.6192, 4.78 calls/Q on the deduped N=400. File has 401 lines: the run was resumed after a runtime restart and 1 failed question was retried, leaving a stale failed row — **dedupe by id keeping the last row** before analysis (the log's printed EM 0.4738 over n=401 includes the stale row). MLflow run `9a12bb41…` (commit `4040bfc`). McNemar vs fresh IRCoT below: p=0.0043, significant |
| `run.log` | — | Log of the MiniLM Dev-100 run | `dev_trueadaptive_v1` | `ece1c0e` | — |
| `run_bm25.log` | — | Log of the BM25 Dev-100 run | `dev_trueadaptive_v1_bm25` | `ef937fc` | — |
| `test400_bm25_run.log` | — | Log of the Test-400 BM25 runs (TrueAdaptive + IRCoT) | `test_trueadaptive_v1_bm25` / `test_ircot_v1_bm25` | `d69490f` | Includes the restart/resume; see the 401-line note above |
| `test400_bm25_trueadaptive.log` | — | Log of the TrueAdaptive Test-400 run | `test_trueadaptive_v1_bm25` | `d69490f` | Progress-bar output; the summary at the end reads the whole output file, so it says n=401, failed=1 (it includes the stale failed row — see the 401-line note above) |

## `results/cost_opt/`

Phase 2 cost-optimization runs, all via `scripts/run_phase2_experiments.py` (MiniLM,
distractor). Dev sweep files are cache-determined replays of each other (audit App. A).

| File | N | System / config | Cache namespace | First tracked | Notes |
|---|---|---|---|---|---|
| `erag_reference_dev.jsonl` | 100 | **Reference (`final.yaml`, `w_c: 1.0`, cache replay)** | `dev_v1` | `3a4b9ba` | EM 0.50, 14.46 calls/Q, **100% cache hits (0 live)** — it replays the original run's cached completions. Differs from `results/erag_active_dev.jsonl` (EM 0.39, `base.yaml` `w_c: 2.0`) **only** by the `w_c` config value; the two "Reference Dev-100" EMs (0.39 vs 0.50) are both correct for their configs (audit M2). Cite with the config |
| `erag_balanced_dev.jsonl` | 100 | E-RAG Balanced, `configs/erag_balanced.yaml` | `dev_cost_opt_v1` | `3a4b9ba` | EM 0.51, 8.92 calls/Q |
| `erag_balanced_test.jsonl` | 400 | E-RAG Balanced, `configs/erag_balanced.yaml` | `test_v1` | `3a4b9ba` | EM 0.4475, 8.56 calls/Q (~0.3 live) |
| `erag_cost_dev.jsonl` | 100 | E-RAG Cost, `configs/erag_cost.yaml` | `dev_cost_opt_v1` | `3a4b9ba` | EM 0.36, 3.44 calls/Q, 0 cache hits |
| `erag_cost_test.jsonl` | 400 | E-RAG Cost, `configs/erag_cost.yaml` | `test_v1` | `3a4b9ba` | EM 0.3950, 3.41 calls/Q |
| `erag_sc_k1_dev.jsonl` | 100 | SC sweep k=1, `base.yaml` + `final.yaml` | `dev_v1` | `3a4b9ba` | EM 0.53 |
| `erag_sc_k2_dev.jsonl` | 100 | SC sweep k=2, `base.yaml` + `final.yaml` | `dev_v1` | `3a4b9ba` | EM 0.49 |
| `erag_sc_k3_dev.jsonl` | 100 | SC sweep k=3, `base.yaml` + `final.yaml` | `dev_v1` | `3a4b9ba` | EM 0.52 |
| `erag_sc_k5_dev.jsonl` | 100 | SC sweep k=5, `base.yaml` + `final.yaml` | `dev_v1` | `3a4b9ba` | EM 0.50 |
| `erag_resample_always_dev.jsonl` | 100 | Post-hop resample=always | `dev_v1` | `3a4b9ba` | EM 0.50 |
| `erag_resample_conditional_dev.jsonl` | 100 | Post-hop resample=conditional | `dev_v1` | `3a4b9ba` | EM 0.49 |
| `erag_resample_never_dev.jsonl` | 100 | Post-hop resample=never | `dev_v1` | `3a4b9ba` | EM 0.47 |
| `query_direct_sat_False_dev.jsonl` | 100 | Query strategy sweep (direct, saturation off) | `dev_v1` | `3a4b9ba` | EM 0.49 |
| `query_llm_sat_False_dev.jsonl` | 100 | Query strategy sweep (LLM, saturation off) | `dev_v1` | `3a4b9ba` | EM 0.50 |
| `query_llm_sat_True_dev.jsonl` | 100 | Query strategy sweep (LLM, saturation on) | `dev_v1` | `3a4b9ba` | EM 0.50 |
| `nli_prefiltered_dev50.jsonl` | 50 | NLI pre-filter (first 50 dev items) | `dev_v1` | `3a4b9ba` | EM 0.52 |
| `nli_unfiltered_dev50.jsonl` | 50 | NLI post-hoc (first 50 dev items) | `dev_v1` | `3a4b9ba` | EM 0.52 |

## `results/bm25/`

Phase 4 BM25 Test-400, all via `scripts/run_phase4_ircot_bm25.py`, namespace `test_v1`,
distractor setting, first tracked `3a4b9ba`.

| File | N | System / config | Notes |
|---|---|---|---|
| `erag_balanced_bm25_test.jsonl` | 400 | E-RAG Balanced, `erag_balanced.yaml`, BM25 | EM 0.4450, 8.95 calls/Q |
| `ircot_bm25_test.jsonl` | 400 | IRCoT, `base.yaml` + `final.yaml`, BM25 | EM 0.4100, 2.59 calls/Q (superseded as the fresh comparator by `results/ircot_test_bm25.jsonl`, EM 0.4200) |
| `standard_bm25_test.jsonl` | 400 | Standard RAG, `base.yaml` + `final.yaml`, BM25 | EM 0.4025, 1.00 calls/Q |

## `results/phase5/`

Phase 5 E5/BGE Test-400, all via `scripts/run_phase5_four_retrievers.py`, namespace
`test_v1`, distractor setting. The BM25 cells of the 12-cell benchmark are the
`results/bm25/` files above (reused, not re-run); the MiniLM cells are the
`results/*_test.jsonl` / `results/cost_opt/erag_balanced_test.jsonl` files above.

| File | N | System / retriever | First tracked | Notes |
|---|---|---|---|---|
| `erag_balanced_e5_test.jsonl` | 400 | E-RAG Balanced / E5-base-v2 | `3a4b9ba` | EM 0.4900, 8.12 calls/Q |
| `erag_balanced_bge_test.jsonl` | 400 | E-RAG Balanced / BGE-base-en-v1.5 | `ed41253` | EM 0.4800, 8.19 calls/Q |
| `ircot_e5_test.jsonl` | 400 | IRCoT / E5-base-v2 | `3a4b9ba` | EM 0.4575, 2.57 calls/Q |
| `ircot_bge_test.jsonl` | 400 | IRCoT / BGE-base-en-v1.5 | `ed41253` | EM 0.4650, 2.52 calls/Q |
| `standard_e5_test.jsonl` | 400 | Standard RAG / E5-base-v2 | `3a4b9ba` | EM 0.4400, 1.00 calls/Q |
| `standard_bge_test.jsonl` | 400 | Standard RAG / BGE-base-en-v1.5 | `ed41253` | EM 0.4525, 1.00 calls/Q |

## `results/enriched/`

Offline enrichment of the 12 Test-400 benchmark conditions — **derived files, zero LLM
calls** — produced by `scripts/enrich_results_with_retrieval_metrics.py` from the source
files listed, adding 12 retrieval-metric fields (hop-by-hop recall, precision, MRR,
bridge-entity resolution, …). Ids/answers/EM are faithful copies of the sources
(audit App. A). First tracked `ed41253`.

| File | N | Source file | Notes |
|---|---|---|---|
| `erag_balanced_minilm_test.jsonl` | 400 | `results/cost_opt/erag_balanced_test.jsonl` | EM 0.4475 |
| `erag_balanced_bm25_test.jsonl` | 400 | `results/bm25/erag_balanced_bm25_test.jsonl` | EM 0.4450 |
| `erag_balanced_e5_test.jsonl` | 400 | `results/phase5/erag_balanced_e5_test.jsonl` | EM 0.4900 |
| `erag_balanced_bge_test.jsonl` | 400 | `results/phase5/erag_balanced_bge_test.jsonl` | EM 0.4800 |
| `ircot_minilm_test.jsonl` | 400 | `results/ircot_test.jsonl` | EM 0.4250 |
| `ircot_bm25_test.jsonl` | 400 | `results/bm25/ircot_bm25_test.jsonl` | EM 0.4100 |
| `ircot_e5_test.jsonl` | 400 | `results/phase5/ircot_e5_test.jsonl` | EM 0.4575 |
| `ircot_bge_test.jsonl` | 400 | `results/phase5/ircot_bge_test.jsonl` | EM 0.4650 |
| `standard_minilm_test.jsonl` | 400 | `results/standard_test.jsonl` | EM 0.4050 |
| `standard_bm25_test.jsonl` | 400 | `results/bm25/standard_bm25_test.jsonl` | EM 0.4025 |
| `standard_e5_test.jsonl` | 400 | `results/phase5/standard_e5_test.jsonl` | EM 0.4400 |
| `standard_bge_test.jsonl` | 400 | `results/phase5/standard_bge_test.jsonl` | EM 0.4525 |

## `results/erag_vs_ircot_study/`

Head-to-head analysis outputs from `scripts/eval_erag_vs_ircot.py`, first tracked `3a4b9ba`.
**Do not cite the "Matched" / "Uninhibited" rows as separate systems or as significance
evidence (audit H3):** they are post-hoc re-thresholdings of the single
`erag_active_test.jsonl` run (theta sweep 0.00–0.50 over test predictions), not separate
runs. The frozen systems are not significantly different (Active vs IRCoT ΔEM +0.0275,
McNemar p=0.2145; Balanced vs IRCoT ΔEM +0.0225, p=0.2892).

| File | Notes |
|---|---|
| `erag_no_abs_test.jsonl` | N=400. E-RAG Active Test-400 predictions with abstention disabled (theta_abs=0.00 re-thresholding of `erag_active_test.jsonl`); EM 0.5225. Derived file, not a separate run |
| `coverage_sweep.csv` | Theta sweep table (theta_abs 0.00–0.50) over the same Active test predictions: coverage / EM / F1 / selective EM / wins-losses vs IRCoT |
| `head_to_head_comparisons.csv` | Frozen + post-hoc comparisons vs IRCoT with McNemar p-values and bootstrap CIs; the CSV itself labels the Matched/Uninhibited rows as post-hoc |

## What this file does not establish

- Producing commits for the pre-tracking runs (bulk-tracked in `3a4b9ba`) — see "unknown"
  entries above; the runs predate git tracking of `results/`.
- Live-vs-cached call splits beyond the headline figures in the audit — recompute per file
  as `llm_calls` − `cache_hits`.
- Anything about `mlruns/` (empty) — the live MLflow record is `mlflow.db`.
