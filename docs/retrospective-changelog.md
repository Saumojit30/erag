# E-RAG Retrospective Changelog

**Status:** DRAFT — not committed. Prepared 2026-11-09 from repository evidence on branch `trueadaptive` (HEAD `0ac6d99`). Every commit hash, file path, test path, OpenSpec document, and result artifact cited here was checked against the repository at the time of writing (`git log`, `git show`, `ls`, and recomputation from stored rows). Nothing in this document modifies historical result files, caches, tags, or benchmark artifacts.

## Purpose

Reconstruct the project's technical history and current state from repository evidence, without claiming unmeasured research results.

## Rules

- Use only verifiable repository evidence.
- Cite commit hashes, file paths, tests, OpenSpec documents, and result artifacts where available.
- Mark missing evidence as `not recoverable from repository`.
- Do not claim accuracy, cost, robustness, or generalization improvements unless a completed, saved experiment demonstrates them.
- Separate implementation evidence from benchmark evidence.
- Do not modify historical result files, caches, tags, or benchmark artifacts while creating this document.
- **Keep this changelog current:** every experiment that completes gets a §2 entry the same day it is verified, with the same evidence standard (commit hash, files changed, numbers from stored artifacts, verdict). In-flight work is not entered until it is verified and committed. §4 (current state), §5 (evidence map), and §7 (evidence boundary) are updated in the same commit as the new §2 entry, so the document never again falls behind the work it records.

**Verification method used for this draft.** Commit existence was checked with `git log --oneline <hash>` (all branches). File existence was checked on disk. Headline result numbers were recomputed from the stored JSONL rows (deduplicated by question id, keeping the last row; EM taken from the runner's stored `em` field, which is the repository's `exact_match`). The full offline test suite and `scripts/verify_results.py` were re-run for this draft; their measured outputs are recorded in §4.5. Numbers taken from the project record without re-running are labelled as such. Where this draft corrects the supplied template, the correction is stated and the check that supports it is named.

**Scope note.** This repository is a fork. Its history begins with the upstream author's staged build (2026-11-05 to 2026-11-08, commits `ed717cd` through `6aced98`) and continues with the fork's own work on branch `trueadaptive` (from `f779122` onward). The remote `upstream` (`ManojAdapakala/ERag`) is fetch-only; `origin` is `Saumojit30/erag`. Nothing in this document was pushed to the upstream.

## 1. Project timeline

### 1.1 Baseline RAG system

- Date: 2026-11-05 (commits `ed717cd`, `40bfe3a`, `8a888df`, `79e74cb`, `10ee899`)
- Commit(s): `ed717cd` (Stage 1: foundation, config, LLM client, cache, tracker, tests), `40bfe3a` (Stage 2: manifests, stratified split, FAISS retriever, tests), `8a888df` (Stage 3: evaluation framework), `79e74cb` (Stage 4: Standard RAG, closed-book comparator, runner, tests), `10ee899` (baseline reproduction note, `research/baseline.md`)
- Scope: one-shot Standard RAG (System A) plus a closed-book comparator, driven by `scripts/run_experiment.py`
- Implementation: `src/config.py`, `src/llm/client.py`, `src/llm/prompts.py`, `src/retrieval/index.py`, `src/systems/standard.py`, `src/eval/metrics.py`, `src/eval/stats.py`, `scripts/run_experiment.py`
- Configuration: `configs/base.yaml` — model `openai/gpt-oss-20b` via Groq, retriever `sentence-transformers/all-MiniLM-L6-v2` + FAISS, `k: 3`, setting `distractor`, NLI model `cross-encoder/nli-deberta-v3-base`, `max_tokens: 1024`, seed 13
- Data: HotpotQA dev-distractor split, recorded as `hotpot_dev_distractor_v1.json` (SHA-256 `e3da074df24e8369009918aa5cdbdd254dadcde4c63f7569d36afd6f2268caa8` in `data/manifests/manifest.json`). Manifests on disk: `data/manifests/debug.jsonl` (50), `data/manifests/dev.jsonl` (100: 80 bridge / 20 comparison, all hard), `data/manifests/test.jsonl` (400: 320 bridge / 80 comparison, all hard). The raw file itself is not in the repository; `scripts/verify_results.py` reports "raw file not in repo; raw_sha256 not checked". The "Test-400" split is a held-out slice of the HotpotQA *dev* distractor set, not the official HotpotQA test set (official test answers are not public).
- Metrics (recomputed from stored rows for this draft): Standard debug-50 EM 0.38 (`results/standard_debug.jsonl`, N=50); closed-book debug-50 EM 0.24 (`results/closed_book_debug.jsonl`, N=50); Standard dev-100 EM 0.4400, F1 0.5471, 1.00 calls/Q (`results/standard_dev.jsonl`, N=100); Standard test-400 (MiniLM) EM 0.4050, F1 0.5384, 1.00 calls/Q (`results/standard_test.jsonl`, N=400); Standard test-400 (BM25) EM 0.4025, F1 0.5461, 1.00 calls/Q (`results/bm25/standard_bm25_test.jsonl`, N=400)
- Result artifacts: `results/standard_debug.jsonl`, `results/standard_dev.jsonl`, `results/standard_test.jsonl`, `results/bm25/standard_bm25_test.jsonl`, `results/closed_book_debug.jsonl`, `results/closed_book_dev.jsonl`, `results/closed_book_test.jsonl`
- Latency and token figures: reported in `research/cost/` (notably `research/cost/llm_call_audit.md`, `research/cost/cost_breakdown.csv`, `research/cost/latency_breakdown.csv`, commit `5ef8533`); not independently recomputed for this draft
- Evidence status: implemented, tested offline (see §4.5), evaluated on saved benchmark data

### 1.2 Epistemic layer

- Date: 2026-11-05
- Commit(s): `76ec90d` (Stage 5: Epistemic Layer — self-consistency, claim extraction, NLI verifier, belief graph)
- Scope: claim extraction, NLI verification, belief graph, confidence signal, confidence propagation
- Implementation: `src/epistemic/claims.py` (claim extraction), `src/epistemic/nli.py` (NLI verifier, 2-sentence windows, `theta_s: 0.5`, `theta_c: 0.5`), `src/epistemic/belief_graph.py` (belief graph), `src/epistemic/confidence.py` (self-consistency / confidence)
- Tests: `tests/test_claims.py`, `tests/test_graph.py` (both added in `76ec90d`); `tests/test_nli.py` (added in `18b051f`, 2026-11-06)
- Result artifacts: none directly attributable to this commit; the layer is exercised by the E-RAG system runs in §1.3 (notably `results/erag_active_test.jsonl` and the Phase 5 enriched runs)
- Evidence status: implemented, tested offline (see §4.5). The NLI verifier itself was evaluated on a 60-pair labelled set in the H2 analysis (§2, 2026-11-09 entry): macro-F1 0.6825, contradicted recall 0.75 — see §5

### 1.3 Decision-theoretic retrieval loop

- Date: 2026-11-05 (proposals) to 2026-11-08 (cost optimization, four-retriever runner, TrueAdaptive v1)
- Commit(s): `80187f6` (OpenSpec proposals: System B IRCoT, System C E-RAG, Verified-Belief Memory), `18b051f` (2026-11-06 — `src/systems/erag.py`, `src/systems/ircot.py`, `src/systems/memory.py` first land in the tree, with entity-grounded collapse fix and debug tables/figures), `ec50c8b` (2026-11-07 — E-RAG Active vs IRCoT head-to-head evaluation suite, `scripts/eval_erag_vs_ircot.py`), `cfd1b3c` (2026-11-08 — Phase 2 cost optimizations: conditional resampling, pre-NLI filtering, claim gating), `af81180` (2026-11-08 — Balanced and cost-optimized configurations, `configs/erag_balanced.yaml`, `configs/erag_cost.yaml`, Dev-100 sweep runner), `d1dbb5c` (2026-11-08 — Phase 5 four-retriever benchmark runner), `ed41253` (2026-11-08 — Phase 5 BGE evaluations and enriched multi-hop retrieval dynamics), `6c671d0` (2026-11-08 — TrueAdaptive split into v1/v2), `738dd1e` (2026-11-08 — sequential self-consistency), `7d5cba4` (2026-11-08 — self-consistency gated behind the Fast Path)
- Scope: multi-hop retrieval, gap selection, query generation, fast path, abstention, IRCoT, adaptive call control (TrueAdaptive v1: sequential self-consistency M=1→3 with ΔH < 0.05 stop, SC gated behind the Fast Path, direct EIG, incremental claims, never resample)
- Implementation: `src/systems/erag.py`, `src/systems/ircot.py`, `src/epistemic/confidence.py` (`sequential_consistency()`), `configs/erag_trueadaptive.yaml` (frozen v1 config, `8a64503`: `sc_mode: sequential`, `gate_sc_behind_fast_path: true`, `max_hops: 2`, `theta_abs: 0.4`, `max_claims: 5`)
- Tests: `tests/test_erag.py`, `tests/test_ircot.py` (both added in `18b051f`); TrueAdaptive call-count tests with a mocked LLM added in `d5c820f` (2026-11-08)
- Result artifacts: `results/erag_active_test.jsonl`, `results/erag_vs_ircot_study/` (head-to-head comparisons and coverage sweep), `results/enriched/*_test.jsonl` (Phase 5: 3 systems × 4 retrievers — Balanced E-RAG, IRCoT, Standard × MiniLM/BM25/E5/BGE; 12 cells recomputed by `scripts/verify_results.py`, all PASS), `results/trueadaptive/erag_trueadaptive_dev.jsonl` (Dev-100 MiniLM: EM 0.50, F1 0.6018, 4.91 calls/Q, `ece1c0e`), `results/trueadaptive/erag_trueadaptive_bm25_dev.jsonl` (Dev-100 BM25: EM 0.56, F1 0.6495, 4.58 calls/Q, `ef937fc`), `results/trueadaptive/erag_trueadaptive_test_bm25.jsonl` (Test-400 BM25: EM 0.4750, F1 0.6192, 4.78 calls/Q, `d69490f`; IRCoT comparison `results/ircot_test_bm25.jsonl`: EM 0.4200, F1 0.5674, 2.545 calls/Q — McNemar b=38, c=16, p=0.0043)
- Evidence status: implemented, tested offline, evaluated on saved benchmark data (Test-400 BM25 head-to-head is the completed, saved demonstration for TrueAdaptive v1 vs IRCoT)

### 1.4 Memory extension

- Date: 2026-11-06 (implementation lands) to 2026-11-09 (effectiveness test designed, not yet run)
- Commit(s): `18b051f` (first lands `src/systems/memory.py`, `data/manifests/stream.jsonl` (30 questions), `data/manifests/planted.json` (5 planted beliefs)), `017db9a` (2026-11-07 — Phase 0 audit including memory stream evaluation and `scripts/plot_memory_evaluation.py`), `2facd2d` (2026-11-09 — master plan adds the memory effectiveness test as Phase 1 Step 6), `db7b598` (2026-11-09 — OpenSpec change `tune-memory-effectiveness` drafted, design-only)
- Scope: persistent beliefs, write/read/forget policies, robustness (surprise-gated writes, NLI verification gating, contradiction override, decay 0.98, capacity 200 — `src/systems/memory.py`; `memory.enabled: false` by default in `configs/base.yaml`, so all benchmark results to date are memory-off)
- Implementation: `src/systems/memory.py`; stream construction `scripts/make_stream.py` (verified to exist on disk)
- Tests: `tests/test_memory.py` (added in `18b051f`)
- Result artifacts: `results/stream_mem.jsonl`, `results/stream_nomem.jsonl`, `results/stream_planted.jsonl` (each N=30). Recomputed for this draft: all three EM 0.4000, F1 0.4828, 14.30 calls/Q. The memory arm served `cache_hits == llm_calls` on 30/30 rows (shared default namespace `test_v1`, no per-arm override), so its answers are identical to the no-memory arm — the E5 memory null is a null of a cache replay, i.e. uninformative, not a real null. Planted-belief override: 1/5 among planted, 1/1 among retrieved. The override mechanism itself (local-NLI `mem_events`) is not cache-confounded. A re-test with one fresh namespace per arm is designed in `openspec/changes/tune-memory-effectiveness/` (Step 6, not yet run).
- Evidence status: implemented, tested offline (see §4.5); evaluated on saved data, but the evaluation is uninformative (cache confound) — memory benefit is NOT evaluated

### 1.5 Recent audit and repair sequence

Baseline:

- `checkpoint-pre-audit3` target: `6aced98810227ce3404152799a426a97ca6d62a1`

Verification of the baseline: the commit `6aced98` exists (`2026-11-08 chore(openspec): archive completed Phase 4 and Phase 5 changes and sync retrieval specs`). **The tag `checkpoint-pre-audit3` does not exist in this repository** — `git rev-parse checkpoint-pre-audit3` fails with "unknown revision". The baseline is therefore cited by commit hash only; the tag is `not recoverable from repository`.

The repair sequence that follows the baseline *in this repository* is the audit remediation of 2026-11-08/09 (see §2 entries for `7c32650`, `3064740`, `4040bfc`, `011e5d2`, `1aface5`, `f7830cb`, `fdad630`, `9da25fe`, `296088f`, `9408542`, and the reporting-correction commits `4ab6a76`, `a920b3f`, `394cc88`, `c0285a8`, `7ebaca9`, `f83f5b9`, `9055208`). Its substance: never cache or serve empty LLM completions; purge of 55 empty cache rows; row-level retriever provenance on every output row; cache key versioned to `v: 2` with namespace rotation documented (`docs/cache-namespaces.md`); a provenance record (`results/README.md`, 235 lines); generator/cost corrections in the Phase 5 report; post-hoc re-thresholdings labelled as such; and `scripts/verify_results.py` (10 checks, all PASS at HEAD — re-run for this draft, see §4.5).

The four-entry repair sequence supplied with the template for this section (Batch 2A `4e5f446b2587eb838bcbf69fea2d183b220cf7e6`, Provenance `34a487da5ebc70fb09222505d01ba7fdc7a11863`, Conflict-policy characterization `8bdd695781a7fc7652750e6834ddb49ce57ec18b`, Contradiction veto "[to be recorded after commit]") **is not in this repository**. The checks performed and their results are recorded in §3; the entries are retained there as `not recoverable from repository` rather than reproduced as fact.

## 2. Change entries

Entries are chronological. "Evidence" records only what was verified for this draft: commit existence via `git log`, file existence on disk, and — where stated — re-runs performed for this draft. Historical test counts claimed in earlier records are not repeated here unless re-verified; they are marked `not recoverable from repository` where the check cannot be performed. The full offline suite measured for the latest update (HEAD `fc1a428` plus the uncommitted `--write-artifact` flag, command `HF_HUB_DISABLE_XET=1 NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 .venv/bin/python -m pytest tests/ -q -p no:cacheprovider --tb=no`, exit code 1, 126 passed, 1 failed, 0 xfailed in 26.44s) applies to the current tree, not to individual historical commits. (Original draft measurement: HEAD `0ac6d99`, 87 passed, 1 failed in 24.33s.)

### 2026-11-05 — Stage 1: project foundation

**Commit:** `ed717cd`
**Scope:** Foundation
**Type:** feature
**Prediction-changing:** no (no system existed yet)

#### What changed
- Project skeleton, configuration loader, Groq LLM client with retry and tracker, SQLite response cache, experiment tracker, first tests.

#### Why it changed
- Foundational stage of the staged build.

#### Files changed
- `configs/base.yaml`, `src/config.py`, `src/llm/client.py`, `src/llm/prompts.py`, `tests/test_cache.py`, `tests/test_config.py`, `tests/test_retry_and_tracker.py`, `.env.example`, `.gitignore`, `requirements.txt`, `research/audit.md`, `research/decisions.md`, `research/ai-assistance-log.md`

#### Tests added or updated
- `tests/test_cache.py`, `tests/test_config.py`, `tests/test_retry_and_tracker.py`

#### Evidence
- Commit verified via `git log`. Files exist on disk. Test counts at this commit: `not recoverable from repository` (suite not re-run at this commit). Current suite at HEAD: 87 passed, 1 failed (see §4.5); the 1 failure is in `tests/test_retry_and_tracker.py` and is a test/code mismatch, not a regression introduced by this commit (see §4.5).

#### Prediction impact
- None; no answering system existed yet.

#### Limitations
- LLM client as built retries 6 times (1 try + 5 retries); the retry test added here expects 4 attempts and therefore fails against the current code (see §4.5).

#### Evidence status
- Implemented and tested (at HEAD; historical counts not recovered)

### 2026-11-05 — Stage 2: dataset manifests and FAISS retriever

**Commit:** `40bfe3a`
**Scope:** Retrieval / data
**Type:** feature
**Prediction-changing:** no (retrieval only; no answering system yet)

#### What changed
- Stratified manifests (debug 50, dev 100, test 400) generated by `scripts/make_manifests.py`; FAISS retriever over `sentence-transformers/all-MiniLM-L6-v2` in `src/retrieval/index.py`.

#### Why it changed
- Dataset and retrieval groundwork for all later systems.

#### Files changed
- `data/manifests/debug.jsonl`, `data/manifests/dev.jsonl`, `data/manifests/test.jsonl`, `data/manifests/manifest.json`, `scripts/make_manifests.py`, `src/retrieval/index.py`, `tests/test_retrieval.py`

#### Tests added or updated
- `tests/test_retrieval.py`

#### Evidence
- Commit verified via `git log`. Manifests exist on disk with the recorded row counts (50/100/400). Manifest SHAs verified by `scripts/verify_results.py` (PASS, re-run for this draft).

#### Prediction impact
- None at the time; the retriever is the evidence source for every later system.

#### Limitations
- The raw source file `hotpot_dev_distractor_v1.json` is not in the repository, so the recorded raw SHA-256 cannot be checked (verify script reports this explicitly).

#### Evidence status
- Implemented, tested, evaluated (manifests are the data for all later benchmarks)

### 2026-11-05 — Stage 3: evaluation framework

**Commit:** `8a888df`
**Scope:** Evaluation
**Type:** feature
**Prediction-changing:** no

#### What changed
- `src/eval/metrics.py` (EM, F1, recall, ECE, Brier, AUROC), `src/eval/stats.py` (paired bootstrap, McNemar, Holm).

#### Why it changed
- A shared, exact evaluation definition for all systems (the repository's `exact_match` is the EM of record throughout).

#### Files changed
- `src/eval/metrics.py`, `src/eval/stats.py`, `tests/test_metrics.py`

#### Tests added or updated
- `tests/test_metrics.py`

#### Evidence
- Commit verified via `git log`. Files exist on disk. Historical test counts: `not recoverable from repository`.

#### Prediction impact
- None; measurement only. Every EM/F1 number in this changelog is computed with this code (or the stored `em` field it produced).

#### Limitations
- None recorded for this change.

#### Evidence status
- Implemented and tested

### 2026-11-05 — Stage 4: Standard RAG and runner

**Commit:** `79e74cb`
**Scope:** Baseline RAG
**Type:** feature
**Prediction-changing:** yes (first answering system)

#### What changed
- `src/systems/standard.py` (one-shot retrieve-then-answer), closed-book comparator, `scripts/run_experiment.py` runner with crash recovery (skips question ids already in the output file).

#### Why it changed
- The baseline every later system is compared against.

#### Files changed
- `scripts/run_experiment.py`, `src/systems/standard.py`, `tests/test_standard.py`

#### Tests added or updated
- `tests/test_standard.py`

#### Evidence
- Commit verified via `git log`. Files exist on disk. Benchmark evidence: Standard debug-50 EM 0.38, dev-100 EM 0.4400, test-400 (MiniLM) EM 0.4050, test-400 (BM25) EM 0.4025 — all recomputed from stored rows for this draft (see §1.1).

#### Prediction impact
- Establishes the one-shot baseline: 1.00 calls/Q on every split.

#### Limitations
- One-shot retrieval only; no uncertainty, verification, or abstention.

#### Evidence status
- Implemented, tested, evaluated on saved benchmark data

### 2026-11-05 — Stage 5: epistemic layer

**Commit:** `76ec90d`
**Scope:** Epistemic layer
**Type:** feature
**Prediction-changing:** yes

#### What changed
- `src/epistemic/claims.py` (claim extraction), `src/epistemic/nli.py` (NLI verifier, 2-sentence windows), `src/epistemic/belief_graph.py` (belief graph), `src/epistemic/confidence.py` (self-consistency / confidence).

#### Why it changed
- The evidence-aware uncertainty and claim-level verification machinery that distinguishes E-RAG from one-shot RAG.

#### Files changed
- `src/epistemic/belief_graph.py`, `src/epistemic/claims.py`, `src/epistemic/confidence.py`, `src/epistemic/nli.py`, `tests/test_claims.py`, `tests/test_graph.py`

#### Tests added or updated
- `tests/test_claims.py`, `tests/test_graph.py`

#### Evidence
- Commit verified via `git log`. Files exist on disk. Historical test counts: `not recoverable from repository`. The NLI verifier was later evaluated on a 60-pair labelled set (H2, 2026-11-09): macro-F1 0.6825 — see §5.

#### Prediction impact
- Claims, NLI verdicts, and the belief graph determine what the E-RAG system believes, what it retrieves next, and when it abstains.

#### Limitations
- The verifier scores independent 2-sentence windows and takes the maximum, so it cannot combine evidence across paragraphs (established by the H2 failure-mode analysis, `docs/hypotheses-h1-h6-assessment.md`).

#### Evidence status
- Implemented and tested; the verifier component evaluated on a 60-pair set (§5)

### 2026-11-05 — OpenSpec proposals: IRCoT, E-RAG, Memory

**Commit:** `80187f6`
**Scope:** Design / documentation
**Type:** documentation
**Prediction-changing:** no

#### What changed
- OpenSpec proposals `research/openspec_ircot.md`, `research/openspec_erag.md`, `research/openspec_memory.md` (Systems B, C, and Verified-Belief Memory).

#### Why it changed
- Design record preceding implementation.

#### Files changed
- `research/openspec_erag.md`, `research/openspec_ircot.md`, `research/openspec_memory.md`, `research/ai-assistance-log.md`

#### Tests added or updated
- None.

#### Evidence
- Commit verified via `git log`. Files exist on disk.

#### Prediction impact
- None; design only.

#### Limitations
- Proposals are not implementations; the systems land in `18b051f`.

#### Evidence status
- Implemented (as design documents)

### 2026-11-05 — Baseline reproduction note

**Commit:** `10ee899`
**Scope:** Baseline RAG
**Type:** documentation
**Prediction-changing:** no

#### What changed
- `research/baseline.md` (65 lines) recording the Standard RAG and closed-book baseline reproduction on debug-50.

#### Why it changed
- Baseline record for the report.

#### Files changed
- `research/baseline.md`

#### Tests added or updated
- None.

#### Evidence
- Commit verified via `git log`. Saved artifacts: `results/standard_debug.jsonl` (EM 0.38 recomputed for this draft), `results/closed_book_debug.jsonl` (EM 0.24 recomputed).

#### Prediction impact
- None.

#### Limitations
- Note only; the runs themselves are recorded in the result files.

#### Evidence status
- Implemented (as a record)

### 2026-11-06 — Gate G2: E-RAG, IRCoT, and Memory systems land

**Commit:** `18b051f`
**Scope:** Retrieval loop / Memory
**Type:** feature
**Prediction-changing:** yes

#### What changed
- First implementation of `src/systems/erag.py` (215 lines added), `src/systems/ircot.py` (79 lines), `src/systems/memory.py` (128 lines); entity-grounded fix for the Phase 2 collapse; debug tables and figures (`research/tables/table1_main_debug.*`, `table3_significance_debug.*`, `research/figures/fig1-3_*_debug.png`); stream manifest `data/manifests/stream.jsonl` (30 questions) and `data/manifests/planted.json` (5 planted beliefs).

#### Why it changed
- The multi-hop retrieval loop, the IRCoT baseline, and the memory module become runnable; the Phase 2 collapse (EM ~0.56 → ~0.28 when the epistemic layer entered the pipeline, per the project record) is resolved with entity grounding.

#### Files changed
- `src/systems/erag.py`, `src/systems/ircot.py`, `src/systems/memory.py`, `src/epistemic/nli.py`, `data/manifests/stream.jsonl`, `data/manifests/planted.json`, `research/method.md`, `research/decisions.md`, `research/tables/*_debug.*`, `research/figures/*_debug.png`

#### Tests added or updated
- `tests/test_nli.py`, `tests/test_ircot.py`, `tests/test_memory.py`

#### Evidence
- Commit verified via `git log` and `git show --stat`. Files exist on disk. Historical test counts: `not recoverable from repository`.

#### Prediction impact
- E-RAG becomes a multi-hop retrieve–reason loop with a belief graph, gap/EIG-driven stopping, and abstention; IRCoT becomes the comparison baseline; memory becomes available (disabled by default).

#### Limitations
- The collapse-resolution claim (EM recovery) is recorded in the project record and the debug tables; the debug-50 numbers were not independently recomputed for this draft beyond the stored `results/standard_debug.jsonl` / `results/closed_book_debug.jsonl` files.

#### Evidence status
- Implemented and tested; evaluated via the runs in the following entries

### 2026-11-06 — Test-400 benchmark evaluation

**Commit:** `4cf4299`
**Scope:** Benchmark
**Type:** documentation
**Prediction-changing:** no

#### What changed
- Test-400 tables and figures (`research/tables/table1_main_test.*`, `table3_significance_test.*`, `research/figures/fig1-3_*_test.png`) and a decisions note.

#### Why it changed
- Record of the Test-400 benchmark evaluation of the pre-adaptive systems.

#### Files changed
- `research/tables/table1_main_test.csv`, `research/tables/table1_main_test.md`, `research/tables/table3_significance_test.csv`, `research/tables/table3_significance_test.md`, `research/figures/fig1_calibration_test.png`, `research/figures/fig2_risk_coverage_test.png`, `research/figures/fig3_pareto_test.png`, `research/decisions.md`

#### Tests added or updated
- None.

#### Evidence
- Commit verified via `git log`. The underlying Test-400 result files were tracked in `3a4b9ba` (see next entry). The Phase 5 matrix cells were later recomputed by `scripts/verify_results.py` (PASS, re-run for this draft).

#### Prediction impact
- None; reporting only.

#### Limitations
- Tables are derived artifacts; the raw rows are the JSONLs in `results/`.

#### Evidence status
- Implemented (as a record); benchmark evidence lives in the result files

### 2026-11-07 — E-RAG Active vs IRCoT head-to-head suite

**Commit:** `ec50c8b`
**Scope:** Evaluation
**Type:** feature
**Prediction-changing:** no

#### What changed
- `scripts/eval_erag_vs_ircot.py` (344 lines) and plotting scripts; head-to-head comparison outputs in `results/erag_vs_ircot_study/` (`head_to_head_comparisons.csv`, `coverage_sweep.csv`, `erag_no_abs_test.jsonl`) and comparative report/figures.

#### Why it changed
- A dedicated harness for the E-RAG vs IRCoT comparison that the paper's exploratory comparison rests on.

#### Files changed
- `scripts/eval_erag_vs_ircot.py`, `scripts/plot_crystal_clear_comparison.py`, `results/erag_vs_ircot_study/*`, `.gitignore`

#### Tests added or updated
- None.

#### Evidence
- Commit verified via `git log` and `git show --stat`. Harness and outputs exist on disk. The head-to-head CSV was later corrected and labelled (post-hoc re-thresholdings) in `fdad630` (see audit remediation entry).

#### Prediction impact
- None; evaluation harness only. Its outputs include the Matched/Uninhibited re-thresholdings that were later labelled POST-HOC (audit finding H3).

#### Limitations
- The suite's earlier comparisons were superseded by the frozen-system Test-400 head-to-head in `d69490f`, which is the comparison of record.

#### Evidence status
- Implemented; evaluated (superseded comparison)

### 2026-11-07/08 — Phase 0–3 audits, cost analysis, and reports (documentation)

**Commit(s):** `017db9a` (Phase 0 repository audit, baseline inventory, memory stream evaluation), `5ef8533` (Phase 1 LLM call audit, token usage, cost profiling), `7a3f6fb` (methodology audit, sensitivity analyses, 400-item test tables), `974f61d` (Phase 2 sweep results, Pareto analysis, configuration freeze), `b153def` (Phase 3 cost-effectiveness matrix), `b944672` (Phase 3 validation report), `2358c4c` (IRCoT methodology audit, 18-dimension deviation register)
**Scope:** Audit / documentation
**Type:** documentation
**Prediction-changing:** no

#### What changed
- Audit and analysis documents under `research/` (`research/audit/`, `research/methodology_audit/`, `research/cost/`, `research/ircot/`), including the cost breakdown, latency breakdown, token usage, and the memory stream evaluation figure.

#### Why it changed
- Record of what was built, what it cost, and where it deviates from the cited papers.

#### Files changed
- `research/audit/*`, `research/methodology_audit/*`, `research/cost/*`, `research/ircot/*`, `research/final_validation_audit.md`

#### Tests added or updated
- None.

#### Evidence
- Commits verified via `git log`. Documents exist on disk. Cost/latency figures in these documents were not independently recomputed for this draft.

#### Prediction impact
- None; analysis only. One recorded consequence: the audit's Phase 5 report named the wrong generator model and cost rates, corrected later in `f7830cb`.

#### Limitations
- The methodology audit's memory sensitivity sweep (`research/methodology_audit/memory_sensitivity.md`) reports parameter sweeps and an override-disabled EM drop to 0.3667; only the 3 E5 stream files exist as stored runs, so the sweep itself is unverified against files (per the project record).

#### Evidence status
- Implemented (as records)

### 2026-11-08 — Phase 2 cost optimizations

**Commit:** `cfd1b3c`
**Scope:** Retrieval loop / cost
**Type:** feature
**Prediction-changing:** yes

#### What changed
- Conditional resampling, pre-NLI filtering, and claim gating in `src/systems/erag.py` (55 lines changed) and `src/epistemic/nli.py` (20 lines), with the design record `research/openspec_phase2_cost_optimization.md` (228 lines).

#### Why it changed
- Reduce LLM calls per question without losing accuracy (the cost track that TrueAdaptive later continues).

#### Files changed
- `src/systems/erag.py`, `src/epistemic/nli.py`, `research/openspec_phase2_cost_optimization.md`

#### Tests added or updated
- None in this commit.

#### Evidence
- Commit verified via `git log` and `git show --stat`. Files exist on disk. Cost effect recorded in the project record (Phase 2 sweep, `974f61d`); not independently recomputed for this draft.

#### Prediction impact
- Resampling, NLI filtering, and claim gating change which claims are verified and when retrieval stops, so answers and call counts can change.

#### Limitations
- No new tests in this commit; coverage comes from the existing `tests/test_erag.py` suite at HEAD.

#### Evidence status
- Implemented and tested (at HEAD)

### 2026-11-08 — Balanced and cost-optimized configurations

**Commit:** `af81180`
**Scope:** Configuration
**Type:** feature
**Prediction-changing:** yes (new system configurations)

#### What changed
- `configs/erag_balanced.yaml` and `configs/erag_cost.yaml`; Dev-100 sweep runner `scripts/run_phase2_experiments.py` (381 lines).

#### Why it changed
- Frozen configurations for the cost-effectiveness comparison (Balanced vs Reference vs cost-optimized).

#### Files changed
- `configs/erag_balanced.yaml`, `configs/erag_cost.yaml`, `scripts/run_phase2_experiments.py`

#### Tests added or updated
- None.

#### Evidence
- Commit verified via `git log`. Configs exist on disk. Benchmark evidence: Balanced BM25 Test-400 EM 0.4450 at 8.95 calls/Q, recomputed from `results/bm25/erag_balanced_bm25_test.jsonl` for this draft (N=400). The verify script confirms the Reference→Balanced call reduction of −39.8% (Reference 14.22 → Balanced 8.56 calls/Q, Test-400 MiniLM).

#### Prediction impact
- The Balanced configuration is the cost/accuracy reference point TrueAdaptive is measured against (TrueAdaptive v1: EM 0.4750 at 4.78 calls/Q vs Balanced 0.4450 at 8.95).

#### Limitations
- The "45.4% call reduction" figure that circulated for Reference→Balanced is wrong; the verified figure is −39.8% (audit correction).

#### Evidence status
- Implemented; evaluated on saved benchmark data

### 2026-11-08 — BM25 retriever

**Commit:** `6d0c0f8`
**Scope:** Retrieval
**Type:** feature
**Prediction-changing:** yes (new retriever option)

#### What changed
- `BM25Retriever` with BM25Plus in `src/retrieval/index.py` (61 lines); Groq client timeout in `src/llm/client.py`; `tests/test_retrieval.py` extended (+30 lines).

#### Why it changed
- A lexical retriever alongside the dense MiniLM retriever; BM25 later becomes the first retriever for the adaptive track (it leads MiniLM on Dev-100, 0.56 vs 0.50).

#### Files changed
- `src/retrieval/index.py`, `src/llm/client.py`, `tests/test_retrieval.py`

#### Tests added or updated
- `tests/test_retrieval.py`

#### Evidence
- Commit verified via `git log` and `git show --stat`. Files exist on disk. Benchmark evidence: BM25 Test-400 rows in `results/bm25/*` and `results/enriched/*_bm25_test.jsonl`, recomputed for this draft (Standard-BM25 EM 0.4025; IRCoT-BM25 EM 0.4100 at 2.59 calls/Q in the older file, 0.4200 at 2.545 calls/Q in the fresh `d69490f` run).

#### Prediction impact
- Retrieval changes change which passages enter the belief graph, so answers can change.

#### Limitations
- None recorded for this change.

#### Evidence status
- Implemented, tested, evaluated on saved benchmark data

### 2026-11-08 — E5 and BGE embedding wrappers

**Commit:** `24dec3d`
**Scope:** Retrieval
**Type:** feature
**Prediction-changing:** yes (new retriever options)

#### What changed
- E5 and BGE embedding wrappers with asymmetric prefix formatting in `src/retrieval/index.py` (+70 lines); `tests/test_retrieval.py` extended (+31 lines).

#### Why it changed
- The remaining two retrievers of the Phase 5 four-retriever comparison.

#### Files changed
- `src/retrieval/index.py`, `tests/test_retrieval.py`

#### Tests added or updated
- `tests/test_retrieval.py`

#### Evidence
- Commit verified via `git log` and `git show --stat`. Files exist on disk. Benchmark evidence: Phase 5 enriched runs (`results/enriched/*_e5_test.jsonl`, `results/enriched/*_bge_test.jsonl`); the 12 Phase 5 cells were recomputed by `scripts/verify_results.py` (PASS, re-run for this draft).

#### Prediction impact
- New retrievers change retrieved passages and therefore answers; E5/BGE are not used in the adaptive track (no BGE now, per the project direction).

#### Limitations
- None recorded for this change.

#### Evidence status
- Implemented, tested, evaluated on saved benchmark data (Phase 5 matrix)

### 2026-11-08 — Phase 5 four-retriever benchmark runner and BGE evaluations

**Commit(s):** `d1dbb5c` (runner + initial comparative matrix), `ed41253` (BGE evaluations, enriched multi-hop retrieval dynamics)
**Scope:** Benchmark
**Type:** feature
**Prediction-changing:** no (evaluation harness + recorded runs)

#### What changed
- `scripts/run_phase5_four_retrievers.py` (344 lines); `research/retrievers/four_retriever_benchmark.csv`; `research/retrievers/four_retriever_analysis_report.md` (263 lines); enriched runs for 3 systems × 4 retrievers in `results/enriched/`; `results/cache.sqlite` grew (5,967,872 → 6,889,472 bytes in `ed41253`).

#### Why it changed
- The four-retriever comparison the original plan called Phase 5.

#### Files changed
- `scripts/run_phase5_four_retrievers.py`, `research/retrievers/four_retriever_benchmark.csv`, `research/retrievers/four_retriever_analysis_report.md`, `research/retrievers/enriched_multi_hop_dynamics.csv`, `results/enriched/*_test.jsonl`, `results/cache.sqlite`

#### Tests added or updated
- None.

#### Evidence
- Commits verified via `git log` and `git show --stat`. Runner, matrix, report, and enriched files exist on disk. `scripts/verify_results.py` recomputes all 12 Phase 5 cells from `results/enriched/*_test.jsonl` and matches the report matrix (PASS, re-run for this draft).

#### Prediction impact
- None; the runner executes the systems, and the recorded runs are the evidence. (The systems themselves changed predictions in their own commits.)

#### Limitations
- The Phase 5 report named the wrong generator model and cost rates; corrected in `f7830cb`. The four-retriever matrix is a repo development, not part of the Nov 4 project report's plan (which fixes one retriever in all three versions).

#### Evidence status
- Implemented; evaluated on saved benchmark data

### 2026-11-08 — Archive Phase 4/5 changes; checkpoint commit

**Commit:** `6aced98`
**Scope:** OpenSpec / housekeeping
**Type:** documentation
**Prediction-changing:** no

#### What changed
- Phase 4 (IRCoT BM25) and Phase 5 (four retrievers) OpenSpec changes archived to `openspec/changes/archive/2026-11-08-phase-4-ircot-bm25/` and `.../2026-11-08-phase-5-four-retrievers/`; retrieval spec synced to `openspec/specs/retrieval/spec.md` (48 lines).

#### Why it changed
- Close out the completed phases in the OpenSpec record.

#### Files changed
- `openspec/changes/archive/2026-11-08-phase-4-ircot-bm25/*`, `openspec/changes/archive/2026-11-08-phase-5-four-retrievers/*`, `openspec/specs/retrieval/spec.md`

#### Tests added or updated
- None.

#### Evidence
- Commit verified via `git log` and `git show --stat`. Archived changes and spec exist on disk. **The tag `checkpoint-pre-audit3` said to point at this commit does not exist in this repository** (`git rev-parse checkpoint-pre-audit3` fails); the commit itself is the verifiable baseline.

#### Prediction impact
- None.

#### Limitations
- None recorded for this change.

#### Evidence status
- Implemented (as a record)

### 2026-11-08 — Fork setup: dependency fix and upstream merge

**Commit(s):** `f779122` (build: add missing `rank-bm25` dependency, pin CPU torch 2.15.0), `9564676` (merge upstream Manoj Phase 5 completion `6aced98` into local master)
**Scope:** Build / repository
**Type:** infrastructure
**Prediction-changing:** no (build fix and merge; no system code changed in `f779122`)

#### What changed
- `requirements.txt` gains `rank-bm25`; `constraints-cpu.txt` pins torch 2.15.0+cpu for transformers 5.22.2; upstream Phase 5 completion merged into local `master`. The initial commit `1edc0ce` was rewritten at the fork owner's request to `f779122` with author Saumojit30 <santrasaumojit05@gmail.com> and force-pushed to `Saumojit30/erag` only. Upstream `ManojAdapakala/ERag` is fetch-only (push URL `no_push`); nothing is pushed there.

#### Why it changed
- The fork needed the missing BM25 dependency and a CPU torch build that installs in this VM; the merge brings the upstream Phase 5 completion into the fork's master.

#### Files changed
- `requirements.txt`, `constraints-cpu.txt` (`f779122`); merge brings the Phase 4/5 archive and spec changes (`9564676`)

#### Tests added or updated
- None in these commits. The build was verified in this VM (torch 2.15.0+cpu, transformers 5.22.2, sentence-transformers 6.2.0, faiss-cpu 1.15.1; retrieval tests pass with `HF_HUB_DISABLE_XET=1`).

#### Evidence
- Commits verified via `git log` and `git show --stat`. Files exist on disk. Authorship mapping for the upstream author's commits is `.mailmap` (`88f2512` on master, `719c285` on `trueadaptive`; see the mailmap entry below).

#### Prediction impact
- None from the merge itself. The BM25 dependency enables the BM25 retriever to run.

#### Limitations
- None recorded for this change.

#### Evidence status
- Implemented

### 2026-11-08/09 — Audit remediation: code, cache, and provenance fixes

**Commit(s):** `7c32650` (never cache or serve empty LLM completions), `3064740` (purge 55 empty completions from the cache), `4040bfc` (record the retriever on every experiment output row), `011e5d2` (version the cache key `v: 2`, document namespace rotation in `docs/cache-namespaces.md`), `1aface5` (results provenance record, `results/README.md`, 235 lines)
**Scope:** Audit remediation
**Type:** fix
**Prediction-changing:** partial (see below)

#### What changed
- `src/llm/client.py`: the read path falls through to a live call for legacy empty rows and empty completions are never cached again (23 lines changed, +3 unit tests in `tests/test_cache.py`); 55 empty cache rows purged (cache backup kept outside the repo at `~/workspace/erag-backups/cache.sqlite.2026-11-09.bak` per the project record — backup file not verified in this draft); `scripts/run_experiment.py` writes a `retriever` field on every output row and MLflow tag; the cache key is versioned (`v: 2`), so old cache rows never hit under the new key; `results/README.md` records the provenance of the result files.

#### Why it changed
- The complete audit (`docs/audit-adaptive-llm-calling.md`) found empty completions cached and served, a shared cache across systems (Standard's answers equalled E-RAG hop-0 drafts 400/400), and no per-row retriever record.

#### Files changed
- `src/llm/client.py`, `tests/test_cache.py`, `scripts/run_experiment.py`, `docs/cache-namespaces.md`, `results/README.md`, `results/cache.sqlite` (binary, purged then regrown)

#### Tests added or updated
- `tests/test_cache.py` (+120 lines in `7c32650`, +15 in `011e5d2`)

#### Evidence
- Commits verified via `git log` and `git show --stat`. Files exist on disk. `scripts/verify_results.py` reports cache integrity PASS with 27,617 rows and 0 empty-text rows (re-run for this draft; the count was 26,488 at the last committed verification report, `9408542` — the growth is the step-4 runs). The cache purge backup path is recorded in the project record, not verified on disk in this draft.

#### Prediction impact
- Partial. No scoring math changed. But: empty completions are no longer served (previously served as answers); the versioned cache key means old cached rows never hit, so runs after `011e5d2` make fresh calls and can produce different answers through temp-0.0 nondeterminism; the retriever field changes row contents, not predictions.

#### Limitations
- The purge backup location is recorded, not verified here. Cache `results/cache.sqlite` is deliberately uncommitted and changes with every run.

#### Evidence status
- Implemented and tested (at HEAD; the cache tests are part of the 87 passed)

### 2026-11-08/09 — Audit remediation: reporting corrections and verification script

**Commit(s):** `f7830cb` (correct generator model and cost rates; add live-calls columns), `fdad630` (label Matched/Uninhibited as post-hoc re-thresholdings), `4ab6a76` (small reporting corrections L1+L2+L3+L7), `a920b3f` (regenerate manifest SHAs; refresh cache-entry count), `394cc88` (set MLflow repoURL tag explicitly from the origin remote), `c0285a8` (exclude the pooled run from the ablation export by default), `7ebaca9` (fix BGE rows of the Phase 5 report matrix), `f83f5b9` (verify script: check the Phase 5 report matrix against the benchmark CSV), `9055208` (refresh the stale NLI memo count), `9da25fe` (verification script + report), `296088f` (verify script: check Standard Dev-100 baseline EM — audit Appendix A error), `9408542` (regenerate verification report at HEAD `296088f`, timestamp only)
**Scope:** Audit remediation
**Type:** documentation / infrastructure
**Prediction-changing:** no

#### What changed
- Report corrections: the Phase 5 report's generator is corrected to `openai/gpt-oss-20b` with Groq rates ($0.10/$0.20 per 1M) instead of `llama-3.3-70b-versatile` with llama rates; live-calls columns added; the audit's Appendix A Standard Dev-100 EM corrected from 0.4200 to 0.4400; Matched/Uninhibited comparisons labelled POST-HOC re-thresholdings; manifest SHAs regenerated; `scripts/verify_results.py` (429 lines) with 10 checks and `docs/verification-report.md`.

#### Why it changed
- The audit's own findings H1 (wrong model/cost), H2 (shared cache), H3 (post-hoc significance) required corrections to the record, and a script that recomputes headline figures from raw rows.

#### Files changed
- `scripts/verify_results.py`, `docs/verification-report.md`, `research/retrievers/*`, `research/cost/*`, `research/final_validation_audit.md`, `research/ircot/*`, `research/methodology_audit/ablation_results.csv`, `scripts/export_ablation_results.py`, `scripts/run_experiment.py`, `data/manifests/manifest.json`

#### Tests added or updated
- None (verification script, not a test suite).

#### Evidence
- Commits verified via `git log` and `git show --stat`. `scripts/verify_results.py` re-run for this draft: all 10 checks PASS (Phase 5 cells, report matrix, TrueAdaptive Dev-100, Standard Dev-100 EM 0.44, Test-400 McNemar, −39.8% call reduction, manifest SHAs, cache integrity 27,617 rows / 0 empty, generator name, post-hoc labels). Re-running the script rewrote `docs/verification-report.md` (timestamp and cache-row count only); the file was restored with `git checkout` afterward, so the tree is unchanged.

#### Prediction impact
- None; reporting and verification only.

#### Limitations
- The verification script checks stored figures against stored rows; it cannot detect an error shared by both. One deliberate loose end: `research/methodology_audit/final_methodology_audit.md` still shows a pooled sensitivity row (historical report, per the project record).

#### Evidence status
- Implemented; verification script re-run and passing at HEAD

### 2026-11-08 — TrueAdaptive v1 specification

**Commit:** `6c671d0`
**Scope:** Adaptive retrieval
**Type:** documentation
**Prediction-changing:** no

#### What changed
- OpenSpec change `erag-trueadaptive` (proposal, design, tasks, spec): split into v1 (sequential self-consistency + SC gated behind the Fast Path) and v2 (entropy-gated retrieval, closed-book gate — deferred, not built).

#### Why it changed
- The adaptive build needed a written design with a v1/v2 split before code, per the project's OpenSpec discipline ("one OpenSpec change per step").

#### Files changed
- `openspec/changes/erag-trueadaptive/proposal.md`, `openspec/changes/erag-trueadaptive/design.md`, `openspec/changes/erag-trueadaptive/tasks.md`, `openspec/changes/erag-trueadaptive/specs/adaptive-llm-calling/spec.md`

#### Tests added or updated
- None (design only).

#### Evidence
- Commit verified via `git log` and `git show --stat`. Change documents exist on disk under `openspec/changes/erag-trueadaptive/`.

#### Prediction impact
- None; design only.

#### Limitations
- v2 (closed-book gate, entropy-gated retrieval) is specified, not implemented.

#### Evidence status
- Implemented (as a design)

### 2026-11-08 — TrueAdaptive v1 build

**Commit(s):** `d5c820f` (call-count tests with a mocked LLM), `738dd1e` (sequential self-consistency), `7d5cba4` (SC gated behind the Fast Path), `8a64503` (freeze `configs/erag_trueadaptive.yaml`)
**Scope:** Adaptive retrieval
**Type:** feature
**Prediction-changing:** yes

#### What changed
- `sequential_consistency()` in `src/epistemic/confidence.py` (M=1→3, stop on unassailable majority or ΔH < 0.05 after ≥2 samples, behind `erag.sc_mode`, default `fixed`); SC gated behind the Fast Path (`erag.gate_sc_behind_fast_path`; when skipped, `c0 = min_eff`, recorded as `c0_source: fast_path_min_eff`); direct EIG, incremental claims, never resample, saturation precheck, thresholds unchanged (0.8/0.6/0.4), `max_claims: 5`. Frozen config `configs/erag_trueadaptive.yaml` (must stay frozen — a later step-3 build error that added a key to it was reverted).

#### Why it changed
- Make LLM calls adaptive: easy questions take the fast path (2 mocked calls, vs 5 Balanced / 7 Reference), hard questions get sequential self-consistency and further hops.

#### Files changed
- `src/epistemic/confidence.py`, `src/systems/erag.py`, `tests/test_erag.py`, `configs/erag_trueadaptive.yaml`, `openspec/changes/erag-trueadaptive/tasks.md`

#### Tests added or updated
- `tests/test_erag.py` (+223 lines in `d5c820f`, +20/−9 in `7d5cba4`): mocked-LLM call-count tests establishing fast path 2 calls and 1-hop 5 calls.

#### Evidence
- Commits verified via `git log` and `git show --stat`. Files exist on disk. Benchmark evidence: Dev-100 MiniLM EM 0.50 at 4.91 calls/Q (gate ≤6 calls, EM ≥0.50, met exactly) and Dev-100 BM25 EM 0.56 at 4.58 calls/Q — see the next entry.

#### Prediction impact
- Yes: sequential SC changes confidence values (coarser, M=1→3) and therefore stopping, retrieval, and abstention; gating SC behind the Fast Path changes `c0` for 86/400 Test-400 rows.

#### Limitations
- Closed-book/entropy-gated retrieval is v2, not built. The coarser confidence signal weakens H3 (AUROC on `c0` 0.5915 for TrueAdaptive vs 0.6519 for Reference — see the H1–H6 entry).

#### Evidence status
- Implemented, tested, evaluated on saved benchmark data

### 2026-11-08 — Retriever override in the runner

**Commit:** `e8f3c27`
**Scope:** Retrieval / infrastructure
**Type:** feature
**Prediction-changing:** no (enables a flag; no default changed)

#### What changed
- `scripts/run_experiment.py` reads `retrieval.retriever_type`, enabling `--set retrieval.retriever_type=bm25` (6 lines added).

#### Why it changed
- Without it, the BM25 Dev-100 and Test-400 checks could not be run as overrides; this is the minimal change that enabled the BM25-first track.

#### Files changed
- `scripts/run_experiment.py`

#### Tests added or updated
- None.

#### Evidence
- Commit verified via `git log` and `git show --stat`. Used by every BM25 run recorded after it.

#### Prediction impact
- None by itself; it selects which retriever a run uses.

#### Limitations
- None recorded for this change.

#### Evidence status
- Implemented

### 2026-11-08 — TrueAdaptive v1 Dev-100 validation (MiniLM, then BM25)

**Commit(s):** `ece1c0e` (MiniLM), `ef937fc` (BM25)
**Scope:** Benchmark
**Type:** documentation (result files)
**Prediction-changing:** no

#### What changed
- Saved Dev-100 result files for the frozen v1 config.

#### Why it changed
- The v1 gate (≤6 calls/Q and EM ≥0.50 on Dev-100) had to be checked before Test-400.

#### Files changed
- `results/trueadaptive/erag_trueadaptive_dev.jsonl` (100 rows), `results/trueadaptive/erag_trueadaptive_bm25_dev.jsonl` (100 rows)

#### Tests added or updated
- None.

#### Evidence
- Commits verified via `git log`. Files exist on disk. Recomputed for this draft: MiniLM EM 0.5000, F1 0.6018, 4.91 calls/Q, 0.00 cache hits/Q; BM25 EM 0.5600, F1 0.6495, 4.58 calls/Q, 0.00 cache hits/Q. Gate MET on MiniLM exactly at the EM threshold; BM25 leads MiniLM on dev, which is why BM25 was chosen first for Test-400.

#### Prediction impact
- None; measurement only.

#### Limitations
- Dev-100 is a smoke test, not a verdict (per the project plan); the gate's EM margin on MiniLM is zero.

#### Evidence status
- Evaluated on saved benchmark data

### 2026-11-08 — Test-400 BM25 head-to-head: TrueAdaptive v1 vs IRCoT (frozen)

**Commit:** `d69490f`
**Scope:** Benchmark
**Type:** documentation (result files)
**Prediction-changing:** no

#### What changed
- Saved Test-400 BM25 result files for both frozen systems, run sequentially with fresh cache namespaces.

#### Why it changed
- The first significant frozen-system E-RAG vs IRCoT Test-400 comparison, resolving audit finding H3 (the only previous significant result came from post-hoc test-set re-thresholding).

#### Files changed
- `results/trueadaptive/erag_trueadaptive_test_bm25.jsonl` (401 lines — resume retried 1 failed question, leaving a stale row; deduplicated to N=400), `results/ircot_test_bm25.jsonl` (400 lines)

#### Tests added or updated
- None.

#### Evidence
- Commit verified via `git log`. Files exist on disk. Recomputed for this draft (deduplicated, keeping the last row per id): TrueAdaptive EM 0.4750, F1 0.6192, 4.78 calls/Q, coverage 0.8075, recall 0.8975, 0.00 cache hits/Q; IRCoT EM 0.4200, F1 0.5674, 2.545 calls/Q, coverage 0.78, recall 0.7975, 0.00 cache hits/Q. McNemar paired: b=38, c=16, p=0.0043 (exact 0.0038) — significant. TrueAdaptive also beats Balanced BM25 (0.4450 at 8.95 calls/Q, recomputed from `results/bm25/erag_balanced_bm25_test.jsonl`) by +3.0 pts EM at −46.6% calls. `scripts/verify_results.py` recomputes the same McNemar result (PASS, re-run for this draft). Rounding note: the IRCoT exact mean is 1018/400 = 2.545; the master plan's 2.55 is the half-up rounding of the same value, and Python's `round()` prints 2.54 — this draft uses the exact 2.545 so the two documents cannot disagree.

#### Prediction impact
- None; measurement only.

#### Limitations
- Test-400 is a held-out slice of HotpotQA dev distractor, not the official test set. The TA file's 401st line is a stale resume row (handled by dedupe). The older IRCoT BM25 file (`results/bm25/ircot_bm25_test.jsonl`, EM 0.4100 at 2.59 calls/Q) is a different, earlier run and is not the comparison file.

#### Evidence status
- Evaluated on saved benchmark data — the completed, saved demonstration for the claim "TrueAdaptive v1 beats IRCoT on Test-400 BM25"

### 2026-11-08 — Test-400 error analysis and tuning plan

**Commit:** `ed154d7`
**Scope:** Analysis
**Type:** documentation
**Prediction-changing:** no

#### What changed
- `scripts/analyze_trueadaptive_test400.py` (177 lines) and `docs/trueadaptive-test400-error-analysis.md` (143 lines): the error budget and the ordered tuning plan.

#### Why it changed
- To locate the bottleneck before tuning: the analysis showed reasoning, not retrieval, is the bottleneck (107/133 wrong answers had recall 1.0), which redirected the tuning track from the retriever to the reader.

#### Files changed
- `scripts/analyze_trueadaptive_test400.py`, `docs/trueadaptive-test400-error-analysis.md`

#### Tests added or updated
- None.

#### Evidence
- Commit verified via `git log` and `git show --stat`. Files exist on disk. Key figures recomputed from the stored Test-400 rows for this draft's cross-check: error budget right 190 / wrong 133 / abstained 37 / model-unknown 40; hop-0 draft EM 0.4050 → final 0.4750.

#### Prediction impact
- None; analysis only. Its consequence is a change of direction: tuning steps 1–6 all target the reader/reasoning side, and the retriever is frozen (BM25 first).

#### Limitations
- The analysis is descriptive of one Test-400 run; its tuning order is a plan, not a result.

#### Evidence status
- Implemented (as analysis); evaluated (descriptive, from saved data)

### 2026-11-09 — H1–H6 assessment

**Commit(s):** `3468d08` (assessment script, results JSON, report), `b9ee7ce` (H2 verdict + completion), `348735c` (H2 repro scripts), `ca454eb` and `3e017e9` (verdicts recorded in the master plan)
**Scope:** Hypotheses
**Type:** documentation / analysis
**Prediction-changing:** no

#### What changed
- `scripts/analyze_hypotheses_h1_h6.py` (417 lines), `results/hypotheses_h1_h6.json`, `docs/hypotheses-h1-h6-assessment.md` (203 lines), H2 pair set `data/nli_eval_pairs.jsonl` (60 pairs, 20/class, 20 dev questions), predictions `results/nli_eval_h2.jsonl`, repro scripts `scripts/build_nli_pairs_h2.py`, `scripts/run_nli_h2.py`, `scripts/debug_nli.py`, status doc `docs/hypotheses-current-status.md` (`82c5a6e`).

#### Why it changed
- Complete the existing H1–H6 analyses rather than redrafting hypotheses after seeing results (redrafting risks HARKing; user-confirmed decision).

#### Files changed
- `scripts/analyze_hypotheses_h1_h6.py`, `results/hypotheses_h1_h6.json`, `docs/hypotheses-h1-h6-assessment.md`, `data/nli_eval_pairs.jsonl`, `results/nli_eval_h2.jsonl`, `scripts/build_nli_pairs_h2.py`, `scripts/run_nli_h2.py`, `scripts/debug_nli.py`, `docs/hypotheses-current-status.md`, `docs/tuning-master-plan.md`

#### Tests added or updated
- None (analysis scripts, not a test suite). No live LLM calls were used (analysis of stored results only).

#### Evidence
- Commits verified via `git log` and `git show --stat`. Files exist on disk. Values read from `results/hypotheses_h1_h6.json` for this draft: **H1 SUPPORTED interim** — TA vs Standard-BM25 ΔEM +0.0725, 95% CI [0.0350, 0.1125]; ΔF1 +0.0730, CI [0.0351, 0.1114]; McNemar TA-only 46, STD-only 17, p=0.00034 (confirmatory re-run on the tuned system owed at Phase 2; Holm pending H4). **H2 NOT SUPPORTED** — 60 pairs, macro-F1 0.6825 < 0.70 (criterion missed), contradicted recall 0.75 ≥ 0.70 (passed); main weakness supported recall 0.60. **H3 SUPPORTED by criterion but weakened for TrueAdaptive** — AUROC on `c0` 0.5915, CI [0.5421, 0.6391], vs Reference 0.6519. **H4 dev interim INCONCLUSIVE** — ΔF1 +0.0304, CI [−0.0607, 0.1211]; McNemar p=0.8318; Test-400 ablation not run. **H5 NOT SUPPORTED as stated, but the test is cache-confounded** — stream mem vs nomem identical (EM 0.4000 both, 0.00 retrievals saved/Q); planted override 1/5 among planted, 1/1 among retrieved. **H6 SUPPORTED strongly** — hop-0 incomplete subset (n=192) ΔEM +0.1146, CI [0.0521, 0.1823], p=0.00094; hop-0 complete subset (n=208) ΔEM 0.0000, p=1.0.

#### Prediction impact
- None; analysis only.

#### Limitations
- H1 is interim (v1 system, not the tuned system). H2 is N=60 and the 0.70 threshold was proposed, never confirmed. H4's latency bound ("≤3× Standard") is unmeetable as literally written and needs a dated clarification before Phase 2. H5's verdict rests on an uninformative (replayed) test.

#### Evidence status
- Evaluated on saved benchmark data (H1, H3, H4-dev, H6) and on a 60-pair labelled set (H2); H5 evaluated on a cache-confounded run

### 2026-11-08 — Tuning step 1: reader grounding

**Commit(s):** `c3c97dc` (OpenSpec change), `c591aad` (tasks A+B), `303efb5` (implementation), `2b1118c` (analyzer `--reread` section), `9d1d108` (Dev-100 A/B result), `5bf633b` (archive)
**Scope:** Tuning — reader
**Type:** feature
**Prediction-changing:** yes

#### What changed
- Conditional claim-grounded re-read after the hop loop (`grounded_answer_messages()` in `src/llm/prompts.py`; re-read call in `src/systems/erag.py`), behind `erag.ground_final_read` (default false); triggered when the draft is "unknown"/empty or disagrees with the graph's answer claim, grounded on supported claims (answer-bearing first, cap 5), replacing the draft only on a non-"unknown" re-read.

#### Why it changed
- Error analysis: 70 of the 107 full-recall wrong answers had gold in the trace claims — the reader had the evidence and misused it. A grounded re-read is the direct fix.

#### Files changed
- `src/llm/prompts.py`, `src/systems/erag.py`, `tests/test_erag.py`, `scripts/analyze_trueadaptive_test400.py`, `openspec/changes/tune-reader-grounding/*` (archived to `openspec/changes/archive/2026-11-09-tune-reader-grounding/`), `openspec/specs/reader-grounding/spec.md`

#### Tests added or updated
- `tests/test_erag.py` (+94 lines in `303efb5`); 5 mocked-LLM tests per the project record (count not independently re-verified in this draft)

#### Evidence
- Commits verified via `git log` and `git show --stat`. Files exist on disk. Dev A/B recomputed for this draft from `results/trueadaptive/erag_trueadaptive_bm25_dev_reread.jsonl` (N=100, 0 failed): EM 0.5600 vs 0.5600 flat, F1 0.6611 vs 0.6495, calls 4.75 vs 4.58/Q. Re-read triggered 16/100, fixed 2, broke 1 (net +1) per the project record. Gate PASS; mechanism kept; Test-400 confirmation judges it at the end of tuning. Confound recorded in the change: cache-key v=2 meant the tuned run was effectively all-live (0.02 cache hits/Q); temp-0.0 nondeterminism flipped 8 untouched rows, so the EM tie carries ~±3 rows of noise.

#### Prediction impact
- Yes: the re-read can replace the draft answer, so final answers on triggered rows can change.

#### Limitations
- A wash on dev (net +1 row). One recorded breakage: a correct answer reformatted by the re-read ("1970s and 1980s" → "1970s–1980s").

#### Evidence status
- Implemented, tested, evaluated on saved Dev-100 data (smoke test; Test-400 confirmation pending)

### 2026-11-09 — Tuning step 2: claim extraction

**Commit(s):** `0e51368` (OpenSpec change), `8c9f25e` (build), `c062baf` (archive)
**Scope:** Tuning — claims
**Type:** feature
**Prediction-changing:** yes

#### What changed
- Question-grounded claims in the single extraction call (zero new LLM calls): `CLAIM_SYSTEM` in `src/epistemic/claims.py` revised to also list context claims answering the question (including ones disagreeing with the draft, full names exactly as in context); each claim carries a `source` field (`draft`/`question`, default `draft`); the field is threaded through `Claim.source`, `BeliefGraph.add`, and `build_graph` (`src/epistemic/belief_graph.py`, ~6 lines — a fix found during the build, because the graph boundary dropped it); `max_claims` 5→8 in the A/B. Nothing branches on `source` (measurement only).

#### Why it changed
- Error analysis: 37 full-recall wrong answers never extracted gold as a claim. Diagnosis found no trigger separating them (c0 median 1.0 in both groups), so the fix is to extract question-grounded claims alongside draft-grounded ones.

#### Files changed
- `src/epistemic/claims.py`, `src/epistemic/belief_graph.py`, `src/systems/erag.py`, `tests/test_claims.py` (+120 lines), `tests/test_erag.py`, `scripts/analyze_trueadaptive_test400.py`, `openspec/changes/tune-claim-extraction/*` (archived to `openspec/changes/archive/2026-11-09-tune-claim-extraction/`), `openspec/specs/claim-extraction/spec.md`, `docs/tuning-master-plan.md`

#### Tests added or updated
- `tests/test_claims.py` (7 new mocked tests per the project record), `tests/test_erag.py` (`test_build_graph_preserves_claim_source`)

#### Evidence
- Commits verified via `git log` and `git show --stat`. Files exist on disk. Dev A/B recomputed for this draft from `results/trueadaptive/erag_trueadaptive_bm25_dev_claims.jsonl` (N=100, 0 failed): EM 0.5400 vs step-1 tuned 0.5600 (−2 rows, inside the ±3-row noise band), F1 0.6391 vs 0.6611, calls 4.65 vs 4.75/Q. Mechanism measures per the project record: gold-in-claims among full-recall wrong rows 0.524 (11/21) vs 0.333 baseline (PASS); answer-bearing question-sourced claims 6/100 (gate ≤10% PASS). Gate FAILS on EM only (3/4 pass); the user chose to proceed and keep the mechanism, Test-400 judging it. Tuned value recorded: `max_claims: 8`. Cache note: 2.53 cache hits/Q — namespace reused, only extraction calls were live.

#### Prediction impact
- Yes: question-sourced claims enter the belief graph and can change gap computation, retrieval, and the final answer.

#### Limitations
- EM point estimate fell 2 rows on dev (inside noise). Deferred variants not built: separate second pass (Variant B), incremental-freeze fix (Variant C), cap-only ablation (Variant D).

#### Evidence status
- Implemented, tested, evaluated on saved Dev-100 data (smoke test; Test-400 confirmation pending)

### 2026-11-09 — Tuning step 3: model-unknown prompt (gate failed, mechanism dropped)

**Commit(s):** `0d6942b` (OpenSpec change), `c0b5e67` (build + gate), `afc10f1` (archive)
**Scope:** Tuning — reader prompt
**Type:** feature (then reverted by gate)
**Prediction-changing:** no (mechanism dropped; code remains behind a flag defaulting to `base`)

#### What changed
- Two prompt variants behind `erag.unknown_prompt` (default `"base"`; unknown names fall back to `"base"`): `best_guess` and `cite_first`, implemented in `src/llm/prompts.py` and wired at the draft call in `src/systems/erag.py`. A build error that added `unknown_prompt: base` to the frozen v1 config `configs/erag_trueadaptive.yaml` was reverted (the code already defaults via `.get("unknown_prompt", "base")`).

#### Why it changed
- Error analysis: 40 Test-400 model-unknown rows (draft literally "unknown", answer_conf median 0.875) that `theta_abs` cannot touch. The variants were an attempt to recover them.

#### Files changed
- `src/llm/prompts.py`, `src/systems/erag.py`, `tests/test_prompts.py` (+65 lines), `scripts/analyze_trueadaptive_test400.py`, `openspec/changes/tune-unknown-prompt/*` (archived to `openspec/changes/archive/2026-11-09-tune-unknown-prompt/`), `openspec/specs/unknown-prompt/spec.md`, `docs/tuning-master-plan.md`

#### Tests added or updated
- `tests/test_prompts.py` (6 new tests per the project record)

#### Evidence
- Commits verified via `git log` and `git show --stat`. Files exist on disk. Dev A/Bs recomputed for this draft: best_guess (`results/trueadaptive/erag_trueadaptive_bm25_dev_unknown_a.jsonl`, N=100, 0 failed) EM 0.5500, F1 0.6668, 4.76 calls/Q, unknowns 6/100 (gate needed ≤4 — FAIL); cite_first (`..._unknown_b.jsonl`) EM 0.5600, F1 0.6790, 4.48 calls/Q, unknowns 5/100 (FAIL). Both 3/4 on the gate. Per the pre-registered rule the mechanism was DROPPED; `unknown_prompt` stays `"base"` in the frozen tuned config. Dev is a weak instrument here (7 unknown rows); the 40 Test-400 model-unknown rows remain unrecovered.

#### Prediction impact
- None in the frozen system (dropped). The code path exists but is inert at the default.

#### Limitations
- No third variant inside this change (per the pre-registered rule).

#### Evidence status
- Implemented, tested, evaluated on saved Dev-100 data — negative result, recorded as such

### 2026-11-09 — Tuning step 4: theta_abs (selective answering)

**Commit(s):** `db7b598` (OpenSpec changes for steps 4–6 drafted), `5738181` (analyzer `--theta` section + 9 tests), `4701ac3` (gate verdict), `78df3cd` (archive)
**Scope:** Tuning — abstention threshold
**Type:** configuration (no `src/` change)
**Prediction-changing:** yes (threshold changes which answers are withheld)

#### What changed
- Nothing in `src/`: the threshold is the existing `erag.theta_abs` config value (read only at `src/systems/erag.py:346` and `scripts/profile_efficiency.py:143`, verified by grep for this draft). The measurement is new: `theta_metrics()` / `theta_section` (section 13) in `scripts/analyze_trueadaptive_test400.py` (+111 lines) and `tests/test_analyzer_theta.py` (223 lines, 9 tests). The chosen value is recorded for the frozen tuned config at the end of Phase 1; the frozen v1 config is untouched.

#### Why it changed
- The paper's stated objective (user, 2026-11-09): reduce hallucination first, reduced LLM cost second. Step 4 is therefore selective answering — abstain rather than guess — judged by selective EM and wrong-answer rate, with EM as a guardrail rather than the maximand.

#### Files changed
- `scripts/analyze_trueadaptive_test400.py`, `tests/test_analyzer_theta.py`, `openspec/changes/tune-theta-abs/*` (archived to `openspec/changes/archive/2026-11-09-tune-theta-abs/`), `openspec/specs/theta-abs/spec.md`, `docs/tuning-master-plan.md`, `results/trueadaptive/erag_trueadaptive_bm25_dev_theta_a.jsonl`, `results/trueadaptive/erag_trueadaptive_bm25_dev_theta_b.jsonl`

#### Tests added or updated
- `tests/test_analyzer_theta.py` (9 tests). Fast suite at the time: 69 passed (project record); current full suite at HEAD: 87 passed, 1 failed (see §4.5).

#### Evidence
- Commits verified via `git log` and `git show --stat`. Files exist on disk. The live A/Bs ran 2026-11-09 (100/100, 0 failed each) but the pre-registered cache tripwire fired: live calls/Q 0.04 (A) / 0.02 (B) — ~99% cache replays, because the threshold changes no prompt and no LLM call, so the reused namespace served the step-2 run's cached calls. Per the pre-registered rule both files were DISCARDED as live evidence (they are committed as the experimental record, labelled as replays). The numbers at face value reproduce the pre-registered counterfactual exactly (EM 0.5100, selective EM 0.6456, wrong-answer rate 0.3544, coverage 0.790; A 4.65 calls/Q, B 4.64), verified independently for this draft by running `--theta` on the A file. User decision 2026-11-09: accept the pre-registered counterfactual as the evidence, with a dated amendment in the change's design.md (the tripwire's premise is false for threshold-only steps; the numbers were fixed before the runs, so nothing is cherry-picked). Gate on the counterfactual: both candidates PASS all four measures (selective EM 0.6456 > 0.6353; wrong 0.3544 < 0.3647; EM 0.5100 ≥ 0.51, exactly at the bound; calls within 0.2 of 4.65); identical wrong-rate falls → tie rule selects candidate A, **theta_abs = 0.50**, coverage 0.790. Margins are 1 row, inside the ±3-row dev noise band — the gate is a smoke test and Test-400 is the judge.

#### Prediction impact
- Yes: raising `theta_abs` from 0.4 to 0.50 withholds answers with `answer_conf` below 0.50 (6 newly abstained rows on dev: 3 correct, 3 wrong — a coin flip, per the design's honest finding). The confidence signal does not separate right from wrong at the margin; the best selective-EM gain is +1.03 pts bought with −3.0 pts EM and −6.0 pts coverage.

#### Limitations
- Dev-only evidence, 1-row margins, counterfactual (not live) by the accepted amendment. The 40 Test-400 model-unknown rows are untouched by this threshold.

#### Evidence status
- Implemented (configuration + measurement), tested, evaluated on saved Dev-100 data via the accepted counterfactual (smoke test; Test-400 confirmation pending)

### 2026-11-08 — Authorship mapping (.mailmap)

**Commit(s):** `88f2512` (master), `719c285` (`trueadaptive`)
**Scope:** Repository / attribution
**Type:** infrastructure
**Prediction-changing:** no

#### What changed
- `.mailmap` mapping `E-RAG Engineer <erag@research.local>` to Manoj Adapakala <manoj.adapakala7@gmail.com> (identity supplied by the fork owner, 2026-11-08). `git shortlog` then shows 35 Manoj Adapakala commits; no hashes changed. The GitHub web UI ignores `.mailmap` and still shows "E-RAG Engineer".

#### Why it changed
- Correct attribution of the upstream author's 35 commits without a history rewrite.

#### Files changed
- `.mailmap`

#### Tests added or updated
- None.

#### Evidence
- Commits verified via `git log`. File exists on disk. Master `88f2512` is 1 commit ahead of `origin/master`, unpushed (needs a fresh token).

#### Prediction impact
- None.

#### Limitations
- Display-only; GitHub's web UI does not apply it.

#### Evidence status
- Implemented

### 2026-11-09 — Experiment log added to the master plan

**Commit:** `0ac6d99`
**Scope:** Documentation
**Type:** documentation
**Prediction-changing:** no

#### What changed
- New §12 in `docs/tuning-master-plan.md` (158 lines): a single chronological record of every run, analysis, and decision from the v1 build through step 4, each with config, output file, headline numbers, verdict, and commit; rule recorded that every future run gets an entry the same day and a number appears only if a stored file or a commit backs it.

#### Why it changed
- The fork owner pointed out the traces were scattered across result JSONLs, commits, OpenSpec archives, analysis docs, and memory.

#### Files changed
- `docs/tuning-master-plan.md`

#### Tests added or updated
- None.

#### Evidence
- Commit verified via `git log`. Section exists in the plan on disk. All 16 files it references were verified to exist at the time of writing (per the commit message).

#### Prediction impact
- None.

#### Limitations
- The log is an index, not the evidence itself; the JSONLs and commits remain the source of truth.

#### Evidence status
- Implemented (as a record)

### 2026-11-09 — Tuning step 5: hop-2 SC cap (measurement build + A/B; verdict SUPERSEDED)

**Commit(s):** `5c01ede` (A-build: mocked cap test + `--hopcap` analyzer section), `7a3598c` (close-out + step-7 change draft), archived as `2026-11-09-tune-hop2-sc-cap`
**Scope:** Tuning — hop-depth / call tail
**Type:** configuration (no `src/` change)
**Prediction-changing:** would have been (fewer hops), not adopted

#### What changed
- Key correction, found during design: the plan's SC-cap sketch does not match the code — SC runs at most once per question, at hop 0; the only hop-loop calls are draft (1/hop) + extraction (1/hop). The mechanism is therefore `erag.max_hops=1`, config-only, zero code (`max_hops` is read only at the loop stop, `src/systems/erag.py:240`, verified by grep). A-build: A.1 mocked-LLM tests in `tests/test_erag.py` proving the cap binds (max_hops=1 → hops==1, exactly 5 calls, no hop-2 draft; control max_hops=2 → hops==2, 6 calls) and A.2 `--hopcap` analyzer section 14 (`scripts/analyze_trueadaptive_test400.py`) + 9 tests in `tests/test_analyzer_hopcap.py` (failed before, pass after). The section reproduces the pre-registered numbers exactly: step-2 dev EM 0.5400, 4.65 calls/Q, 10 hop-2 rows, 78 hop-2 calls; Test-400 42 hop-2 rows, 334 calls, tail 54/422; theta_a baseline EM 0.5100, 4.65 calls/Q.

#### Why it changed
- The call tail is the cost lever: 54 Test-400 rows at ≥7 calls consume 422 of 1,910 calls (22%), and 38 of them are hop-2 rows. Hop 2 fixed 4 drafts and broke 2 on test (net +2), so capping it was a candidate saving with a small expected accuracy cost.

#### Files changed
- `tests/test_erag.py`, `scripts/analyze_trueadaptive_test400.py` (§14), `tests/test_analyzer_hopcap.py`, `results/trueadaptive/erag_trueadaptive_bm25_dev_hopcap.jsonl`, `openspec/changes/tune-hop2-sc-cap/*` (archived), `openspec/specs/hop2-sc-cap/spec.md`, `docs/tuning-master-plan.md`

#### Tests added or updated
- `tests/test_analyzer_hopcap.py` (9 tests) + mocked cap tests in `tests/test_erag.py`. Step-5 test files: 29/29 pass (parent run). Fast suite at the time: 111 passed, 1 failed (the known retry mismatch; see §4.5).

#### Evidence
- Commits verified via `git log`. Live A/B ran 2026-11-09 (detached, ~24s, mostly cache replays; 100/100, 0 failed; output `results/trueadaptive/erag_trueadaptive_bm25_dev_hopcap.jsonl`): EM 0.5100 (unchanged), F1 0.5969, calls/Q 4.49 vs baseline 4.65 (−0.16, the expected ~0.15 saving), live calls/Q 0.06 vs baseline 0.04 (+0.02), hop-2 rows 10→0, hop-2 calls 78→0, tail rows 18→12. Numbers verified by the parent two ways (analyzer + independent recompute, exact agreement). Baseline is the post-step-4 tuned dev file (theta_a): EM 0.5100, 4.65 calls/Q, live 0.04. **Gate as written FAILS on the live-calls measure only** (needs calls/Q AND live calls/Q strictly below baseline AND EM ≥ 0.5000): calls/Q pass, EM pass, live calls 0.06 > 0.04 fail. The live-call difference is replay noise: the baseline's 4 live calls were concentrated on 2 rows (including row `5a865bbf`, the known empty-draft row, 3 live calls — empty completions are never cached per the audit-remediation guard); the hopcap run's 6 live calls are 6 different rows × 1. The user did not pick either gate-reading option offered; they asked the adaptivity question instead and chose the learned continuation policy (step 7). **Step 5 therefore closes SUPERSEDED — not passed, not failed; the gate is not re-judged.** `max_hops` stays 2 as a ceiling; the static cap is NOT adopted and is NOT recorded in the frozen-config note.

#### Prediction impact
- None (not adopted). Had it been adopted, hop-2 rows would have stopped at hop 1 at a draft-level cost of −2 rows on test.

#### Limitations
- The A/B is a dev smoke test (N=100); the live-calls measure cannot discriminate between two ~99%-replay runs (the step-5 lesson, already recorded in the plan).

#### Evidence status
- Implemented (measurement + live A/B), tested, evaluated on Dev-100; verdict SUPERSEDED by user choice, not by gate

### 2026-11-09 — Tuning step 6: memory effectiveness (measurement build; E5 cache finding; A/B pending)

**Commit:** `e5da900`
**Scope:** Tuning — memory module effectiveness
**Type:** measurement only (no behavior change; no live run yet)
**Prediction-changing:** no (not yet run)

#### What changed
- A/B measurement build: A.2 `--position` section in `scripts/eval_memory.py` (+366 lines; functions `band_of`, `dedupe_rows`, `load_clusters`, `arm_metrics`, `paired_delta`, `fired_row_paired`, `planted_stats`, `position_section`; flags `--position --nomem --mem --planted --clusters --plant-defs`; bare run unchanged) + 11 tests in `tests/test_eval_memory_position.py` (failed before, pass after; two build bugs fixed — the false-claim check excluded target-entity answers, and the `__main__` guard was moved to end of file). B.1: `mem_store_size` / `mem_texts` row fields added to `run_erag`'s output dict (`src/systems/erag.py:372–373`; verified: `memory.write` runs before the dict is built, `mem_passages` in scope; 0 / [] when memory off) + 2 mocked tests in `tests/test_erag.py` (proven genuine: both fail with KeyError when B.1 is stashed, pass when restored). The 30-row sidecar (5 clusters × 6, positions 0–5 each ×5) was committed as `data/manifests/stream_clusters.json`.
- Gate (pre-registered, in the change): memory enters the frozen Test-400 system ONLY if ALL hold (N=60 deduped, 0 failed/arm): (1) fire-rate floor — mem arm fires on ≥5/60 questions, else "instrument too weak" (memory stays OFF, paper reports under-powered, not a null); (2) effectiveness — ΔEM > 0, OR Δcalls/Q < 0 with ΔEM ≥ −0.02, fired-row paired difference not contradicting the full-stream direction; (3) override test passes — every retrieved planted belief overridden, no planted-arm final answer equals a planted false claim. Clean null → memory stays OFF, H5 stays NOT SUPPORTED. No re-run, no second stream, no gate revision inside this change.
- **Stream extension 30 → 60 questions NOT done.** `data/raw/hotpot_dev_distractor_v1.json` is absent from this VM (verified; `data/raw/` does not exist). The fetch failed a third time (official CMU mirror, both http and https variants, curl (52) Empty reply; no copy exists anywhere under /home/hatch). No Parquet reconstruction was attempted (needs user approval), no questions invented. **The pre-registered fallback is in effect: run N=30 as-is; fire-rate floor becomes ≥5/30.**

#### Why it changed
- `BeliefMemory` (`src/systems/memory.py`: surprise-gated writes, NLI verification gating, contradiction override, decay 0.98, capacity 200) is implemented and wired but disabled by default (`memory.enabled: false`), so all results so far are memory-off. Step 6 is the component test that decides whether memory enters the tuned system. It runs on the post-step-7 tuned system if the policy passes its gates, else on the post-step-4 system.

#### Files changed
- `scripts/eval_memory.py`, `tests/test_eval_memory_position.py`, `src/systems/erag.py` (row fields only), `tests/test_erag.py` (2 mocked tests), `data/manifests/stream_clusters.json`, `openspec/changes/tune-memory-effectiveness/*` (active, not archived), `docs/tuning-master-plan.md`

#### Tests added or updated
- `tests/test_eval_memory_position.py` (11 tests) + 2 mocked tests in `tests/test_erag.py`. Full suite after the build: 111 passed, 1 failed (only the known retry mismatch), parent run.

#### Evidence
- Commits verified via `git log`; files exist on disk. The parent re-ran the `--position` section on the stored E5 files and reproduced every number exactly: nomem EM 0.4000, F1 0.4828, 14.30 calls/Q, 2.50 retrievals/Q, 0.27 cache_hits/Q; fired rows idx 20 (cluster 3, pos 2) and 29 (cluster 4, pos 5); position splits early EM 0.5000 / 14.20 calls, mid 0.4000 / 13.70, late 0.3000 / 15.00 (all ΔEM 0.0000 within bands); planted override 1 unique belief (Becker) / 5 planted, 1/1 retrieved, 0 false-claim violations; `mem_store_size` reports "not recorded" on E5 files, never zero. The tripwire fires correctly on both replayed arms.
- **E5 cache finding (verified by the parent from stored rows — the sharpest finding of this step):** the original E5 suite ran all three arms with no `run.cache_namespace` override (shared default namespace `test_v1`); the mem arm served `cache_hits == llm_calls` on **30/30 rows** (mean 14.30/14.30), and its answers/EM/F1/call counts are identical to the nomem arm (only `mem_used`, `cache_hits`, and latency fields differ). Memory changed no LLM prompt in E5 — **the H5 effectiveness null is a null of a replay, i.e. uninformative, not a real null.** The override mechanism is NOT cache-confounded (local-NLI `mem_events`; the Becker row-20 override stands). Step 6 uses one fresh namespace per arm with a tripwire in tasks.md C.2. The H5 verdict is to be revisited after step 6 with a dated note, not a rewrite. E5 stored files: `results/stream_mem.jsonl`, `results/stream_nomem.jsonl`, `results/stream_planted.jsonl`; manifests `data/manifests/stream.jsonl` (30 Qs), `data/manifests/planted.json` (JSON array, 5 planted beliefs).

#### Prediction impact
- None yet (measurement only; the live A/B has not run).

#### Limitations
- No live evidence yet: the stream A/B awaits the step-7 outcome + a Groq key. The N=30 fallback (vs the designed N=60) halves the instrument's power; the fire-rate floor is ≥5/30.

#### Evidence status
- Implemented (measurement), tested; live A/B pending

### 2026-11-09 — Tuning step 7: learned continuation policy (change drafted; Phase A; Gate A PASS marginal, then RETRAINED — Gate A re-check PASS with margin; final model trained)

**Commit(s):** `7a3598c` (change drafted + step-5 close-out), `fc1a428` (Phase A build + Gate A verdict), `d0fb457` (final model trained, τ = 0.30 — SUPERSEDED), `7872b24` (retrain with the hop-0 definition; Gate A re-check PASS with margin)
**Scope:** Tuning — learned adaptivity (the hop-0 continuation decision)
**Type:** mechanism (offline measurement + trained artifact; wiring in progress, not yet live)
**Prediction-changing:** not yet (policy not wired in at the time of writing)

#### What changed
- Origin: the user asked whether the system is "properly adaptive or just so called using static values" (2026-11-09). The honest answer given: the structure is adaptive (per-question effort 2–9 calls; H6 shows work lands where retrieval was incomplete), but the decision boundaries are hand-set constants and steps 1–6 only calibrated them; the confidence signal is weak (H3 AUROC 0.5915; step-4 coin flip). The user said "make it adaptive" and picked the learned continuation policy over a pre-hoc complexity router (question text only) and calibrated confidence only. OpenSpec change `learned-continuation-policy` drafted (proposal/design/tasks/spec; validate 9 passed, 0 failed).
- Design (v1 scope, tight): at the hop-0 boundary in `run_erag` (after hop-0 draft, claim extraction, NLI verification — where the theta_fast fast-path check and first gap/EIG continuation check currently decide), a learned model replaces the fixed rules when `erag.continuation_policy` names an artifact file (absent = today's static behavior exactly). The model is a logistic regression on hop-0 features predicting P(hop-0 draft is correct); **CONTINUE iff P < τ**, τ chosen by 5-fold cross-validation on dev. It subsumes the theta_fast fast-path rule at hop 0. Unchanged: EIG gap selection, SC procedure, abstention (theta_abs=0.5), max_hops=2 ceiling, hop-1+ continuation (static rules). Every policy-active row must carry a `policy_decision` field ("stop"/"continue"). One fallback model only: a depth-2 decision tree if LR's cross-validated simulation doesn't beat the static baseline; no third model, no feature search after seeing results. Training data is dev only (N=100; label 48/100 drafts correct); Test-400 is never used for training, feature selection, τ choice, or model selection — any Test-400 touch before the Phase 2 freeze invalidates the verdict.
- Phase A (offline measurement, no LLM calls, no `src/` change): A.1 extraction script `scripts/extract_continuation_training.py` → `data/continuation_training_dev.jsonl`; A.2 call accounting; A.3 training script `scripts/train_continuation_policy.py` + counterfactual simulation → `data/continuation_simulation_dev.json`; A.5 `--policy` analyzer section 15 in `scripts/analyze_trueadaptive_test400.py` (+ `--policy-baseline`, `--policy-simulation` flags). Tests-first: 8 tests in `tests/test_continuation_policy.py`, 7 in `tests/test_analyzer_policy.py` (failed before, pass after).
- **Final model trained 2026-11-09** (after the user chose to proceed): `scripts/train_continuation_policy.py --write-artifact` (new flag, refuses to write unless Gate A passes, refuses non-logistic winners — the format is linear-only) wrote `configs/continuation_policy_dev.json` (model type, 12 features in order, coefficients, intercept, scaler means/scales, τ = 0.30, provenance: training file, N=100, labels 48/52, date, OOF AUROC 0.6546, simulated EM 0.5000, simulated calls/Q 3.98, Gate A PASS). Inference is dependency-free: z = intercept + Σ coefᵢ·(xᵢ − meanᵢ)/scaleᵢ, P = sigmoid(z) — no sklearn import in `src/`. Verified by the parent: pure-arithmetic recomputation from the artifact matches the fitted pipeline's predict_proba to 2.2e-16. Final in-sample model at τ=0.30 would STOP 74 / CONTINUE 26 (vs OOF 70/24).
- **RETRAIN 2026-11-09 (commit `7872b24`) — the τ = 0.30 artifact above is SUPERSEDED and must not be used for wiring.** The B.1 subagent found `draft_unknown` was trained on the row `draft` field — the FINAL draft (last hop, possibly re-read-replaced, `erag.py:354`), which does not exist at the hop-0 decision point. The parent verified the two definitions diverge on 16/100 dev rows (15 hop-0-unknown → final real answer, 1 real → unknown, row 5abd44d9); hop-0-unknown count is 20 vs row-draft-unknown 6; the other 11 features agree exactly. `draft_unknown` carried the largest coefficient (−0.767), so the original Gate A pass rested on a definitionally wrong feature. The user chose the retrain. Re-extraction with the hop-0 definition (`trace[0]['answer']`) + re-training, same pre-registered gate: extraction reproduces all verification numbers + hop0_draft_unknown 20; LR, τ = 0.05, simulated EM 0.5152, F1 0.6238, calls/Q 3.92 (saved +0.73), coverage 0.869, STOP 81 / CONTINUE 18, excluded 1/100 (1.0%); OOF AUROC 0.6775; composition STOP on 2/6 fix-rows, 2/3 broke rows saved; τ curve smooth (τ=0.10: EM 0.5204, 3.97 calls). New artifact written (τ = 0.05, `draft_unknown` coef −1.489), verified to 2.2e-16 the same way; suite 127 passed, 1 failed (known retry mismatch); 1 new test + 1 updated test pin the hop-0 definition. The retrain is a methods disclosure for the paper, not a footnote.

#### Why it changed
- Steps 1–6 calibrated static constants; none made the system more adaptive. The learned policy is the first mechanism that replaces a fixed decision boundary with a data-driven one, and it is the direct test of whether the combined hop-0 confidence signal can drive effort better than fixed thresholds (H3 note).

#### Files changed
- `scripts/extract_continuation_training.py`, `scripts/train_continuation_policy.py`, `data/continuation_training_dev.jsonl`, `data/continuation_simulation_dev.json`, `tests/test_continuation_policy.py`, `tests/test_analyzer_policy.py`, `scripts/analyze_trueadaptive_test400.py` (§15), `configs/continuation_policy_dev.json`, `openspec/changes/learned-continuation-policy/*` (active, not archived), `docs/tuning-master-plan.md` (§3.7, §12)

#### Tests added or updated
- `tests/test_continuation_policy.py` (8 tests), `tests/test_analyzer_policy.py` (7 tests). Fast suite: 126 passed, 1 failed (only the known retry mismatch), re-run by the parent for this update (26.44s).

#### Evidence
- Commits verified via `git log`; files exist on disk. Phase A was built by a subagent and verified by the parent by independent re-run (extraction + training scripts re-executed, composition recomputed from the stored traces, fast suite run, `--policy` section run on the baseline). Extraction reproduces every verification number exactly (hop-0 draft EM 0.4800, final EM 0.5100, fixed 6, broke 3, hops {0:45, 1:45, 2:10}, abstained 15, draft-unknown 6, 4.65 calls/Q). Call-accounting invariant is EXACT (0 violations, all 100 rows; rule recorded in design.md Threats: hop-0 = 1 draft + 1 extraction + SC samples (0 if Fast Path skipped, 2 if c0 == 1.0, else 3); later hops = 1 draft + 1 extraction iff the draft changed vs hop 0, +1 for a triggered re-read; EIG probes 0, resample 0). Oracle ceiling: included 83, excluded 17, EM 0.6506, calls/Q 4.61 — saves only 0.04/Q, because 28 of the 48 correct drafts already stop at hop 0 under the static fast path; the oracle's EM is on the 83 included rows only, not comparable to baseline 0.5100 on 100. LR, τ = 0.30, 5-fold CV, OOF only: simulated EM 0.5000, F1 0.5837, calls/Q 3.98 (saved +0.67), coverage 0.766, STOP 70 / CONTINUE 24, excluded 6/100 (6.0%, under the 10% ceiling). OOF AUROC 0.6546 (c0 alone 0.484 on dev). No decision tree was tried — LR passed, so the fallback was not triggered. `--policy` section 15 reproduces the theta_a baseline exactly (EM 0.5100, F1 0.5969, 4.65 calls/Q, 0.04 live, all 100 rows unknown); agreement vs simulation dEM +0.0100, dCalls/Q +0.67. No Test-400 data in training, feature selection, τ choice, or model selection (one `TEST_FILE` path constant in `tests/test_continuation_policy.py`, used only as a string passed to `assert_dev_input` to prove it refuses test paths — the file is never opened).
- **Gate A: PASS, exactly at the floor** (simulated EM 0.5000 ≥ 0.5000, simulated calls/Q 3.98 < 4.65, OOF only). The pass is zero-margin: 0.5000 = 47/94 included rows; one fewer correct row fails it. The parent's composition check: the policy STOPs on 4 of the 6 fix-rows (loses 4 fixes) and saves 1 of 3 breaks; STOP rows 40 correct at hop-0, CONTINUE rows 7 correct at final; 3 of the 6 excluded rows had correct hop-0 drafts. F1 (0.5837 vs 0.5969) and coverage (0.766 vs 0.790) dip below baseline. The saving is bought by stopping on wrong drafts, not by smarter stopping — the oracle ceiling (0.04 calls/Q saved) shows the static fast path already captures the easy stops. Two further limitations are recorded in design.md Threats: the simulation's STOP branch ignores the end-of-run re-read/abstention that would apply live (23/100 dev rows triggered re-read in the stored run; 9 rows have hop-0 answer-claim eff < 0.5), and simulated live calls/Q is a stored upper bound, not a measurement. **This pass is SUPERSEDED by the retrain (commit `7872b24`) — see the retrain bullet above. Gate A re-check: PASS with margin** (simulated EM 0.5152, F1 0.6238, calls/Q 3.92, coverage 0.869, STOP 81 / CONTINUE 18, excluded 1/100; OOF AUROC 0.6775; F1 and coverage now ABOVE baseline; composition STOP on 2/6 fix-rows, 2/3 broke rows saved).
- **B.1 DONE 2026-11-09, committed `a0eb216`, verified by the parent** (see the tasks.md B.1 note for the full verification record): new module `src/epistemic/continuation_policy.py` + wiring in `src/systems/erag.py` (+67/-9); 12 new mocked tests; feature agreement row-for-row 1e-9 on all 100 dev rows; module probabilities match the fitted pipeline to 1.1e-16; decisions reproduce the artifact's in-sample split (STOP 81 / CONTINUE 19); tests proven genuine by stashing the wiring (5 behavior tests fail without it); full suite 139 passed, 1 failed (known retry mismatch); parent-added hardening (load_policy requires exactly the 12 MODEL_FEATURES in order). The live Dev-100 A/B (C.1) and Gate B are pending a Groq key.

#### Prediction impact
- None yet (offline simulation only; the policy is not wired in). If the live Gate B passes, the tuned system's hop-0 continuation becomes model-driven instead of threshold-driven.

#### Limitations
- Dev-only, N=100, zero-margin gate, in-sample optimism on the live run (the final model trains on all 100 dev rows it is then evaluated on — Gate B's agreement check, not the raw live numbers, is the wiring test; Test-400 is the real judge). The simulation assumes the stored hop-1 outcome is the outcome under CONTINUE.

#### Evidence status
- Implemented (offline measurement + trained artifact), tested; wiring in progress; live evaluation pending

### Template entries not found in this repository (recorded, not reproduced as fact)

The following four entries were supplied with the template for §3. Each was checked against this repository and **none of it is present**. They are recorded here so that the absence is explicit rather than silently omitted.

#### Batch 2A: evidence deduplication and telemetry — `not recoverable from repository`

- **Claimed commit:** `4e5f446b2587eb838bcbf69fea2d183b220cf7e6`. Check: `git log --all --oneline` for the hash returns nothing; `git log -1 <hash>` fails with "fatal: bad object". The commit does not exist in any ref of this repository (branches `master`, `trueadaptive`; remotes `origin/master`, `origin/trueadaptive`, `upstream/master`).
- **Claimed tests:** `tests/test_batch2a_dedup_and_telemetry.py`, `tests/test_batch1_characterization.py` — both missing on disk (`test -f` fails). `tests/test_retry_and_tracker.py`, `tests/test_erag.py`, `tests/test_graph.py`, `tests/test_nli.py` do exist, but they are not the Batch 2A tests.
- **Claimed evidence:** "Full offline suite: 46 passed, 2 strict xfailed" — cannot be verified: the commit and its tests do not exist here, so no count can be re-run or checked. Marked `not recoverable from repository`.
- **Claimed behaviors** (whitespace normalization for duplicate passage text, order-safe duplicate grouping, entity-grounded title selection, duplicate counting/telemetry, explicit `loop_stop_reason` / `output_reason` / `fast_path`, retry-test alignment with a six-attempt contract): no commit message in this repository mentions deduplication, telemetry, or "Batch 2A" (`git log --all --grep` for `dedup`, `telemetry`, `Batch 2` returns nothing). Whether duplicate evidence currently multiplies confidence or contradiction penalties in this codebase was not established in this draft.
- **Evidence status:** `not recoverable from repository`

#### Provenance and resume safeguards — `not recoverable from repository`

- **Claimed commit:** `34a487da5ebc70fb09222505d01ba7fdc7a11863`. Check: same as above — "fatal: bad object" in every ref.
- **Claimed test:** `tests/test_provenance_and_resume.py` — missing on disk. **Claimed module:** `src/provenance.py` — missing on disk.
- **Claimed evidence:** "Provenance suite: 27 passed. Combined suite: 73 passed, 2 strict xfailed" — cannot be verified; marked `not recoverable from repository`.
- **What does exist in this repository instead:** row-level retriever provenance on every output row (`4040bfc`), a provenance record (`results/README.md`, 235 lines, `1aface5`), manifest SHAs (`a920b3f`), cache key versioning (`011e5d2`), and runner crash recovery that skips question ids already in the output file (`scripts/run_experiment.py`, per the project record). There is no shared provenance module, no immutable generation identity, no fail-closed resume, and no sidecar metadata in this repository as far as the checks in this draft establish.
- **Evidence status:** `not recoverable from repository` (the claimed change); the substitute provenance work listed above is implemented (see the audit remediation entry)

#### Conflict-policy characterization — `not recoverable from repository`

- **Claimed commit:** `8bdd695781a7fc7652750e6834ddb49ce57ec18b`. Check: "fatal: bad object" in every ref.
- **Claimed test:** `tests/test_conflict_policy.py` — missing on disk.
- **Claimed evidence:** "Initial suite: 9 passed, 4 strict xfailed" — cannot be verified; marked `not recoverable from repository`.
- **Claimed behaviors** (nine-scenario conflict-policy characterization, recorded current vs desired-but-unimplemented behavior): no commit message in this repository mentions conflict policy or veto (`git log --all --grep` for `conflict`, `veto` returns nothing).
- **Evidence status:** `not recoverable from repository`

#### Contradiction veto — `not recoverable from repository`

- **Claimed commit:** "[to be recorded after commit]" in the template itself — no hash was ever supplied.
- **Claimed code:** `answer_claims()`, `answer_critical_claims()`, selecting the lowest-effective-confidence answer-bearing claim in `answer_claim()`, and `output_reason = "abstained_contradiction_veto"`. Checks: `git log --all -S "abstained_contradiction_veto"`, `-S "answer_critical_claims"`, and `-S "answer_claims"` each return no commit; `grep -rn` for those identifiers in `src/` returns nothing. No commit in this repository introduced a contradiction veto, and no such code path exists in the current tree.
- **Claimed evidence:** "Full suite: 88 passed, 1 strict xfailed" — cannot be verified; marked `not recoverable from repository`. (For reference, the full suite measured for this draft at HEAD is 87 passed, 1 failed, 0 xfailed — a different count, a different tree, and not the claimed run.)
- **Evidence status:** `not recoverable from repository`

## 3. Recent repair sequence

Baseline:

- `checkpoint-pre-audit3` target: `6aced98810227ce3404152799a426a97ca6d62a1`

Verification of the baseline: the commit `6aced98` exists. **The tag `checkpoint-pre-audit3` does not exist in this repository** — the baseline is cited by commit hash only.

What follows is the four-entry sequence as supplied with the template, **each with the result of verifying it against this repository**. The template's claims are reproduced below only as supplied claims, not as facts; the verification outcome governs. Full per-entry checks are in §2 ("Template entries not found in this repository").

### 3.1 Batch 2A: evidence deduplication and telemetry

**Claimed commit:** `4e5f446b2587eb838bcbf69fea2d183b220cf7e6`
**Scope:** Batch 2A
**Prediction-changing:** Partial (as supplied)

**Verification outcome: `not recoverable from repository`.** The commit does not exist in any ref (`git log -1` fails with "fatal: bad object"). The claimed tests `tests/test_batch2a_dedup_and_telemetry.py` and `tests/test_batch1_characterization.py` do not exist on disk. No commit message in this repository mentions deduplication, telemetry, or "Batch 2A". The claimed evidence ("Full offline suite: 46 passed, 2 strict xfailed") cannot be verified and is not reproduced as a result. The claimed behaviors (whitespace normalization for duplicate passage text, order-safe duplicate grouping, entity-grounded title selection, duplicate counting/telemetry, explicit `loop_stop_reason` / `output_reason` / `fast_path`, retry-test alignment with the six-attempt contract) have no corresponding code or commit in this repository as far as the checks in this draft establish. Whether duplicate evidence currently multiplies confidence or contradiction penalties in this codebase was not established in this draft.

### 3.2 Provenance and resume safeguards

**Claimed commit:** `34a487da5ebc70fb09222505d01ba7fdc7a11863`
**Scope:** Provenance
**Prediction-changing:** No (as supplied)

**Verification outcome: `not recoverable from repository`.** The commit does not exist in any ref. The claimed test `tests/test_provenance_and_resume.py` and the claimed module `src/provenance.py` do not exist on disk. The claimed evidence ("Provenance suite: 27 passed. Combined suite: 73 passed, 2 strict xfailed") cannot be verified. There is no shared provenance module, immutable generation identity, fail-closed resume, or sidecar metadata in this repository as far as the checks in this draft establish.

What does exist instead (the actual repair in this repository): row-level retriever provenance on every output row (`4040bfc`), the provenance record `results/README.md` (`1aface5`), regenerated manifest SHAs (`a920b3f`), cache key versioning (`011e5d2`), and runner crash recovery that skips question ids already in the output file. None of these is the claimed change.

### 3.3 Conflict-policy characterization

**Claimed commit:** `8bdd695781a7fc7652750e6834ddb49ce57ec18b`
**Scope:** Conflict policy
**Prediction-changing:** No (as supplied)

**Verification outcome: `not recoverable from repository`.** The commit does not exist in any ref. The claimed test `tests/test_conflict_policy.py` does not exist on disk. The claimed evidence ("Initial suite: 9 passed, 4 strict xfailed") cannot be verified. No commit message in this repository mentions conflict policy or veto. The claimed behaviors (a nine-scenario characterization suite recording current vs desired-but-unimplemented behavior) have no corresponding code or commit here.

### 3.4 Contradiction veto

**Claimed commit:** `[to be recorded after commit]` (no hash was ever supplied, including in the template)
**Scope:** Conflict policy
**Prediction-changing:** Yes (as supplied)

**Verification outcome: `not recoverable from repository`.** No commit in this repository introduced a contradiction veto: `git log --all -S "abstained_contradiction_veto"`, `-S "answer_critical_claims"`, and `-S "answer_claims"` each return no commit, and `grep -rn` for those identifiers in `src/` returns nothing. The claimed code (`answer_claims()`, `answer_critical_claims()`, lowest-effective-confidence answer-bearing claim selection in `answer_claim()`, `output_reason = "abstained_contradiction_veto"`) does not exist in the current tree. The claimed evidence ("Full suite: 88 passed, 1 strict xfailed") cannot be verified. (For reference, the full suite measured for this draft at HEAD is 87 passed, 1 failed, 0 xfailed — a different count, a different tree, and not the claimed run.)

**Consequence for the template's §4.4 and §5.** The template lists "Missing-dependency fast path" and "Adaptive retrieval" as deferred/unimplemented and "Contradiction veto" as implemented and tested. In this repository the situation is the reverse on the second point and unrecorded on the first: adaptive retrieval IS implemented and evaluated (TrueAdaptive v1, §2), the contradiction veto is NOT in the repository, and no missing-dependency fast path is recorded anywhere in the commit history searched. §4 and §5 below are written from the verified state, not from the template's.

## 4. Current state

### 4.1 Implemented

- Standard RAG (one-shot) — `src/systems/standard.py`; closed-book comparator
- IRCoT (interleaved retrieve–reason) — `src/systems/ircot.py`
- E-RAG active (fixed self-consistency) — `src/systems/erag.py` (pre-TrueAdaptive behavior preserved behind `sc_mode: fixed`)
- TrueAdaptive v1 — sequential self-consistency (M=1→3, ΔH < 0.05), SC gated behind the Fast Path, direct EIG, incremental claims, never resample (`src/epistemic/confidence.py`, `src/systems/erag.py`, `configs/erag_trueadaptive.yaml`)
- Claim extraction, NLI verification, belief graph, confidence — `src/epistemic/claims.py`, `src/epistemic/nli.py`, `src/epistemic/belief_graph.py`, `src/epistemic/confidence.py`
- Reader grounding re-read (step 1, behind `erag.ground_final_read`, default false)
- Question-grounded claim extraction with per-claim `source` field (step 2; `max_claims: 8` recorded for the tuned config)
- Unknown-prompt variants `best_guess` / `cite_first` (step 3; code present, mechanism dropped by gate, default `base`)
- Abstention threshold `theta_abs = 0.50` selected (step 4; recorded for the frozen tuned config)
- Hop-2 SC cap (step 5): measured, verdict SUPERSEDED — the static cap is NOT adopted; `max_hops` stays 2 as a ceiling
- Memory measurement: `--position` section in `scripts/eval_memory.py`, `mem_store_size` / `mem_texts` row fields in `run_erag` (step 6; live A/B pending)
- Learned continuation policy (step 7): offline measurement + final-model artifact `configs/continuation_policy_dev.json` (RETRAINED, τ = 0.05 — the τ = 0.30 artifact is superseded); wiring into `run_erag` DONE and committed (`a0eb216`), not yet live
- Memory module — `src/systems/memory.py` (surprise-gated writes, NLI verification gating, contradiction override, decay 0.98, capacity 200); `memory.enabled: false` by default
- Retrievers: MiniLM-L6-v2 + FAISS, BM25/BM25Plus, E5, BGE (`src/retrieval/index.py`)
- Audit remediation: empty-completion cache guard, cache key `v: 2` with namespace rotation, row-level retriever provenance, results provenance record (`results/README.md`), verification script (`scripts/verify_results.py`)
- Evaluation: EM/F1/recall/ECE/Brier/AUROC, paired bootstrap, McNemar, Holm (`src/eval/metrics.py`, `src/eval/stats.py`); hypothesis analysis scripts (`scripts/analyze_hypotheses_h1_h6.py`, `scripts/analyze_trueadaptive_test400.py`)

### 4.2 Tested offline

- Test files on disk: `tests/test_analyzer_hopcap.py`, `tests/test_analyzer_policy.py`, `tests/test_analyzer_theta.py`, `tests/test_cache.py`, `tests/test_claims.py`, `tests/test_config.py`, `tests/test_continuation_policy.py`, `tests/test_erag.py`, `tests/test_eval_memory_position.py`, `tests/test_graph.py`, `tests/test_ircot.py`, `tests/test_memory.py`, `tests/test_metrics.py`, `tests/test_nli.py`, `tests/test_prompts.py`, `tests/test_retrieval.py`, `tests/test_retry_and_tracker.py`, `tests/test_standard.py`
- Full suite measured for this update (HEAD `fc1a428` + the uncommitted `--write-artifact` flag on the training script, exercised separately): 126 passed, 1 failed, 0 xfailed — see §4.5. The 1 failure is the known pre-existing retry-test mismatch (see §4.5).
- Mocked-LLM call-count tests for TrueAdaptive v1 (`tests/test_erag.py`, added in `d5c820f`): fast path 2 calls, 1-hop 5 calls. Mocked cap tests for step 5 (`tests/test_erag.py`, added in `5c01ede`): max_hops=1 binds at 5 calls, control reaches hop 2 at 6 calls.

### 4.3 Evaluated on saved benchmark data

Only components with completed, saved experiment artifacts are listed.

- Standard RAG: debug-50 (EM 0.38), dev-100 (EM 0.4400), test-400 MiniLM (EM 0.4050) and BM25 (EM 0.4025)
- IRCoT: dev-100 (EM 0.44), test-400 BM25 fresh (EM 0.4200, 2.545 calls/Q — the `d69490f` comparison file); older BM25 file EM 0.4100
- E-RAG Balanced: test-400 BM25 EM 0.4450 at 8.95 calls/Q; Phase 5 matrix (3 systems × 4 retrievers, 12 cells, recomputed by the verify script)
- TrueAdaptive v1: Dev-100 MiniLM (EM 0.50, 4.91 calls/Q) and BM25 (EM 0.56, 4.58 calls/Q); Test-400 BM25 (EM 0.4750, 4.78 calls/Q) vs IRCoT (EM 0.4200, 2.545 calls/Q), McNemar p=0.0043 — the completed, saved demonstration for the head-to-head claim
- Tuning steps 1–4: Dev-100 BM25 A/Bs (step 1 EM 0.56 flat; step 2 EM 0.54; step 3 both variants failed the gate; step 4 counterfactual EM 0.5100, selective EM 0.6456 — see §2)
- Tuning step 5: Dev-100 BM25 A/B (EM 0.5100 unchanged, calls/Q 4.49 vs 4.65; gate failed on live calls only; verdict SUPERSEDED — see §2)
- Tuning step 7 (offline only, no live run yet): counterfactual simulation on Dev-100 traces (LR, τ = 0.05, OOF, RETRAINED with the hop-0 `draft_unknown` definition): simulated EM 0.5152, F1 0.6238, calls/Q 3.92, STOP 81 / CONTINUE 18, excluded 1/100; Gate A re-check PASS with margin — see §2 (the original τ = 0.30 pass, EM 0.5000, is superseded). The policy is not wired in, so the tuned system's live numbers are unchanged.
- H1 (interim, v1 system), H3, H6 analyses from stored Test-400 rows; H2 NLI evaluation on a 60-pair labelled set
- E5 memory stream: evaluated on saved data (N=30) but uninformative — cache replay, not a null (see §1.4 and the step-6 §2 entry). Memory benefit is therefore NOT in this list.

### 4.4 Deferred or unimplemented

- Missing-dependency fast path: no commit, file, or test in this repository refers to a mechanism by that name (commit history searched for related terms; nothing found). Status `not recoverable from repository`.
- Adaptive retrieval: **no longer deferred** — implemented and evaluated as TrueAdaptive v1 (§2). (Listed as deferred in the supplied template; corrected here.)
- Expected-information-gain query selection: implemented as direct EIG in TrueAdaptive v1 (`eig_strategy: direct` in `configs/erag_trueadaptive.yaml`); RIND/QFS-style token-level information-need detection is not implemented and is impossible via the black-box Groq API (no logits/attention), per the project record.
- Memory-enabled execution: implemented (`src/systems/memory.py`) but disabled by default (`memory.enabled: false`); its benefit is unevaluated (E5 test cache-confounded); the clean re-test is designed as Step 6 — measurement built (`e5da900`), live A/B pending the step-7 outcome + a Groq key.
- Learned continuation policy (step 7): final model trained, artifact RETRAINED (`configs/continuation_policy_dev.json`, τ = 0.05); wiring into `run_erag` (B.1) DONE and committed (`a0eb216`); live Dev-100 A/B (C.1) and Gate B pending a Groq key.
- Memory restoration and compatibility: `not recoverable from repository` — no evidence found.
- Full NLI reliability evaluation: only the 60-pair H2 set (macro-F1 0.6825); a larger evaluation has not been run.
- H4 Test-400 ablation (adaptive vs no-adaptive on Test-400): not run; the run spec is prepared (needs a Groq key).
- Tuned-system Test-400 confirmation (Phase 2, pre-registered verdict): not run; pending the end of tuning.
- Phase 3 new dataset (2WikiMultiHopQA vs MuSiQue, undecided): not started; no tuning on its test split is permitted by the plan.
- TrueAdaptive v2 (closed-book gate, entropy-gated retrieval): specified in `openspec/changes/erag-trueadaptive/`, not built.
- Provenance coverage for deferred runners: no provenance module exists in this repository; the substitute provenance (row-level retriever field, `results/README.md`, manifest SHAs) covers `scripts/run_experiment.py` outputs only.
- MiniLM Test-400 for the tuned system: only if the BM25 Test-400 result is inconclusive (agreed rule); not required after the significant v1 BM25 result.

### 4.5 Current test status

- Command (re-run for this update): `HF_HUB_DISABLE_XET=1 NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 .venv/bin/python -m pytest tests/ -q -p no:cacheprovider --tb=no`
- Completed exit code: 1
- Passed / failed / xfailed counts: **126 passed, 1 failed, 0 xfailed in 26.44s** (HEAD `fc1a428` plus the uncommitted `--write-artifact` flag on `scripts/train_continuation_policy.py`, exercised separately by running the training script)
- Remaining failure: `tests/test_retry_and_tracker.py::test_retry_exhaustion_raises_runtime_error` — the test expects the message "LLM call failed after 4 attempts"; the code retries 6 times (`src/llm/client.py:130`: "1 try + 5 retries = 6 attempts"; line 163 raises "LLM call failed after 6 attempts"). This is a test/code mismatch, not a system regression: the retry count in the code is 6 and the test was written for 4. The project record states it fails on base too; that was not independently re-verified in this draft (it would require checking out the base commit).
- Remaining strict xfails: none observed in this run (0 xfailed).
- Earlier counts for reference: 87 passed, 1 failed at HEAD `0ac6d99` (this draft's original measurement); 111 passed, 1 failed after the step-6 measurement build (`e5da900`). The growth is new tests (hopcap 9, memory-position 11, continuation-policy 8, analyzer-policy 7, plus mocked cap/mem tests), not behavior changes.

### 4.6 Current repository state

- HEAD: `7872b24` ("Step 7 retrain: draft_unknown fixed to hop-0 definition; Gate A re-check PASS with margin", 2026-11-09, branch `trueadaptive`), 16 commits ahead of `origin/trueadaptive`, unpushed (needs a fresh token). Master `88f2512` (.mailmap) is 1 commit ahead of `origin/master`, unpushed.
- Uncommitted changes (as found at the time of this update): modified `openspec/changes/learned-continuation-policy/design.md`, `openspec/changes/learned-continuation-policy/tasks.md`, `scripts/train_continuation_policy.py` (the `--write-artifact` flag, exercised by running the training script), `results/cache.sqlite`, `results/nli_memo.pkl` (both run artifacts, deliberately uncommitted); untracked `configs/continuation_policy_dev.json` (final-model artifact, verified — see the step-7 §2 entry), `configs/erag_adaptive.yaml` (old untested draft), `docs/audit-cache-dataset-integrity.md`, `docs/openspec-setup.md`, `openspec/changes/archive/2026-11-09-tune-hop2-sc-cap/`, `openspec/specs/hop2-sc-cap/`. This document was committed as `3da932b` and is updated here in the same working tree; the B.1 wiring subagent is running concurrently and has not yet written files.
- Checkpoint tag target: the tag `checkpoint-pre-audit3` does not exist in this repository; the commit it is said to point at, `6aced98810227ce3404152799a426a97ca6d62a1`, exists (`6aced98`, 2026-11-08).
- Historical result/cache changes: `results/cache.sqlite` was purged of 55 empty rows in `3064740` (backup recorded outside the repo, not verified in this draft) and has since grown with runs (26,488 rows at the last committed verification report, 27,617 rows when the verify script was re-run for this draft, 0 empty-text rows both times). No result JSONL was modified by the preparation of this document; the verify script's re-run rewrote `docs/verification-report.md` (timestamp and cache-row count only) and the file was restored with `git checkout` afterward.

## 5. Evidence map

| Claim / component | Code path | Test | OpenSpec | Commit | Result artifact | Evidence status |
|---|---|---|---|---|---|---|
| Order-safe duplicate grouping | `not recoverable from repository` (no such code found) | `tests/test_batch2a_dedup_and_telemetry.py` — missing | `not recoverable from repository` | `4e5f446b` — does not exist | N/A | Not recoverable from repository |
| Explicit stop telemetry (`loop_stop_reason`, `output_reason`, `fast_path`) | `not recoverable from repository` (identifiers not found in `src/`) | `tests/test_batch2a_dedup_and_telemetry.py` — missing | `not recoverable from repository` | `4e5f446b` — does not exist | N/A | Not recoverable from repository |
| Fail-closed resume | `not recoverable from repository` (`src/provenance.py` missing) | `tests/test_provenance_and_resume.py` — missing | `not recoverable from repository` | `34a487da` — does not exist | N/A | Not recoverable from repository |
| Contradiction veto | `not recoverable from repository` (identifiers not found in `src/`) | `tests/test_conflict_policy.py` — missing | `not recoverable from repository` | No hash supplied; no commit found by content search | N/A | Not recoverable from repository |
| Missing-dependency stopping | `not recoverable from repository` | `tests/test_batch1_characterization.py` — missing | `not recoverable from repository` | `not recoverable from repository` | N/A | Not implemented (no evidence in repository) |
| Adaptive retrieval (TrueAdaptive v1) | `src/epistemic/confidence.py` (`sequential_consistency()`), `src/systems/erag.py` | `tests/test_erag.py` (mocked call-count tests) | `erag-trueadaptive` | `738dd1e`, `7d5cba4`, `d5c820f`, `8a64503` | `results/trueadaptive/erag_trueadaptive_test_bm25.jsonl` | Implemented and evaluated (Test-400 BM25) |
| Memory benefit | `src/systems/memory.py` | `tests/test_memory.py`, `tests/test_eval_memory_position.py` | `tune-memory-effectiveness` (active; measurement built `e5da900`) | `18b051f`, `e5da900` | `results/stream_mem.jsonl`, `results/stream_nomem.jsonl` | Implemented; NOT evaluated (E5 run is a cache replay, uninformative); clean re-test pending |
| Sequential self-consistency (M=1→3, ΔH<0.05) | `src/epistemic/confidence.py` | `tests/test_erag.py` | `erag-trueadaptive` | `738dd1e` | `results/trueadaptive/erag_trueadaptive_dev.jsonl` | Implemented and tested; evaluated via v1 runs |
| SC gated behind Fast Path | `src/systems/erag.py` | `tests/test_erag.py` | `erag-trueadaptive` | `7d5cba4` | `results/trueadaptive/erag_trueadaptive_test_bm25.jsonl` | Implemented and tested; evaluated via v1 runs |
| Reader grounding re-read (step 1) | `src/llm/prompts.py` (`grounded_answer_messages()`), `src/systems/erag.py` | `tests/test_erag.py` | `tune-reader-grounding` (archived `2026-11-09-tune-reader-grounding`) | `303efb5`, `9d1d108` | `results/trueadaptive/erag_trueadaptive_bm25_dev_reread.jsonl` | Implemented and tested; evaluated on Dev-100 (smoke test) |
| Question-grounded claim extraction, `source` field (step 2) | `src/epistemic/claims.py`, `src/epistemic/belief_graph.py` | `tests/test_claims.py`, `tests/test_erag.py` | `tune-claim-extraction` (archived `2026-11-09-tune-claim-extraction`) | `8c9f25e`, `c062baf` | `results/trueadaptive/erag_trueadaptive_bm25_dev_claims.jsonl` | Implemented and tested; evaluated on Dev-100 (smoke test) |
| Unknown-prompt variants (step 3) | `src/llm/prompts.py`, `src/systems/erag.py` | `tests/test_prompts.py` | `tune-unknown-prompt` (archived `2026-11-09-tune-unknown-prompt`) | `c0b5e67`, `afc10f1` | `results/trueadaptive/erag_trueadaptive_bm25_dev_unknown_a.jsonl`, `..._unknown_b.jsonl` | Implemented and tested; evaluated on Dev-100 — negative result, mechanism dropped |
| Selective answering, `theta_abs = 0.50` (step 4) | `src/systems/erag.py:346` (config value only; no `src/` change) | `tests/test_analyzer_theta.py` | `tune-theta-abs` (archived `2026-11-09-tune-theta-abs`) | `5738181`, `4701ac3`, `78df3cd` | `results/trueadaptive/erag_trueadaptive_bm25_dev_theta_a.jsonl`, `..._theta_b.jsonl` (discarded as live evidence — cache replays) | Implemented; evaluated on Dev-100 via the accepted pre-registered counterfactual (smoke test) |
| Hop-2 SC cap (step 5) | `src/systems/erag.py:240` (`max_hops` read; config only, zero code) | `tests/test_analyzer_hopcap.py`, `tests/test_erag.py` (mocked cap tests) | `tune-hop2-sc-cap` (archived `2026-11-09-tune-hop2-sc-cap`) | `5c01ede`, `7a3598c` | `results/trueadaptive/erag_trueadaptive_bm25_dev_hopcap.jsonl` | Measured; A/B EM 0.5100 unchanged, calls/Q 4.49 vs 4.65; gate failed on live calls only; verdict SUPERSEDED, cap NOT adopted |
| Memory effectiveness measurement (step 6) | `scripts/eval_memory.py` (`--position` section), `src/systems/erag.py:372-373` (`mem_store_size` / `mem_texts` row fields) | `tests/test_eval_memory_position.py`, `tests/test_erag.py` (mocked mem-field tests) | `tune-memory-effectiveness` (active, not archived) | `e5da900` | `data/manifests/stream_clusters.json` (30-row sidecar); E5 files `results/stream_mem.jsonl`, `results/stream_nomem.jsonl`, `results/stream_planted.jsonl` | Measurement built and tested; live A/B pending; E5 cache finding: the H5 null is a replay, uninformative, not a real null |
| Learned continuation policy (step 7, Phase A + retrain + B.1) | `scripts/train_continuation_policy.py`, `scripts/extract_continuation_training.py` (offline); `src/epistemic/continuation_policy.py`, `src/systems/erag.py` (wired) | `tests/test_continuation_policy.py`, `tests/test_analyzer_policy.py`, `tests/test_erag.py` (12 new policy tests) | `learned-continuation-policy` (active, not archived) | `7a3598c`, `fc1a428`, `d0fb457`, `7872b24`, `a0eb216` | `data/continuation_training_dev.jsonl`, `data/continuation_simulation_dev.json`, `configs/continuation_policy_dev.json` | Retrained simulation: EM 0.5152, calls/Q 3.92; Gate A re-check PASS with margin; final model retrained (τ = 0.05); wiring DONE and verified; live evaluation pending |
| TrueAdaptive v1 vs IRCoT, Test-400 BM25 | `src/systems/erag.py`, `src/systems/ircot.py` | N/A (benchmark) | `erag-trueadaptive` | `d69490f` | `results/trueadaptive/erag_trueadaptive_test_bm25.jsonl`, `results/ircot_test_bm25.jsonl` | Evaluated: TA EM 0.4750 vs IRCoT EM 0.4200, McNemar p=0.0043 |
| H1 (E-RAG beats Standard) | N/A (analysis) | N/A (analysis of stored rows) | N/A | `3468d08` | `results/hypotheses_h1_h6.json`, `docs/hypotheses-h1-h6-assessment.md` | Supported interim (v1 system; confirmatory re-run owed) |
| H2 (NLI verifier) | `src/epistemic/nli.py` | `tests/test_nli.py` | N/A | `b9ee7ce`, `348735c` | `data/nli_eval_pairs.jsonl`, `results/nli_eval_h2.jsonl` | Evaluated on 60 pairs: NOT SUPPORTED (macro-F1 0.6825 < 0.70) |
| H3 (self-consistency tracks correctness) | `src/epistemic/confidence.py` | N/A (analysis of stored rows) | N/A | `3468d08` | `results/hypotheses_h1_h6.json` | Supported by criterion, weakened for TrueAdaptive (AUROC on `c0` 0.5915) |
| H6 (gains where retrieval was incomplete) | N/A (analysis) | N/A (analysis of stored rows) | N/A | `3468d08` | `results/hypotheses_h1_h6.json` | Supported strongly (ΔEM +0.1146 in the hop-0-incomplete subset, p=0.00094) |
| Empty-completion cache guard | `src/llm/client.py` | `tests/test_cache.py` | N/A (audit remediation) | `7c32650`, `3064740` | `scripts/verify_results.py` (cache integrity PASS, 27,617 rows, 0 empty) | Implemented and tested |
| Cache key versioning (`v: 2`) | `src/llm/client.py` | `tests/test_cache.py` | N/A (audit remediation) | `011e5d2` | `docs/cache-namespaces.md` | Implemented and tested |
| Row-level retriever provenance | `scripts/run_experiment.py` | N/A | N/A (audit remediation) | `4040bfc` | `results/README.md` | Implemented |
| BM25 retriever | `src/retrieval/index.py` (`BM25Retriever`) | `tests/test_retrieval.py` | `retrieval` (spec) | `6d0c0f8`, `e8f3c27` | `results/bm25/*_test.jsonl`, `results/enriched/*_bm25_test.jsonl` | Implemented, tested, evaluated |
| E5 / BGE retriever wrappers | `src/retrieval/index.py` | `tests/test_retrieval.py` | `retrieval` (spec) | `24dec3d` | `results/enriched/*_e5_test.jsonl`, `results/enriched/*_bge_test.jsonl` | Implemented, tested, evaluated (Phase 5 matrix) |
| Test-400 error analysis | `scripts/analyze_trueadaptive_test400.py` | N/A (analysis) | N/A | `ed154d7` | `docs/trueadaptive-test400-error-analysis.md` | Implemented (as analysis); descriptive, from saved data |
| Memory module (implementation) | `src/systems/memory.py` | `tests/test_memory.py` | `tune-memory-effectiveness` (active; measurement built `e5da900`) | `18b051f`, `e5da900` | `data/manifests/stream.jsonl`, `data/manifests/planted.json`, `data/manifests/stream_clusters.json` | Implemented and tested; benefit not evaluated |

## 6. Claims discipline

Do not write:

- “E-RAG improves accuracy.”
- “E-RAG reduces LLM cost.”
- “E-RAG outperforms IRCoT.”
- “Memory improves efficiency.”
- “The system is robust.”

unless a completed, saved experiment demonstrates the claim.

Instead write:

- “The contradiction veto is implemented and covered by offline tests.”
- “Adaptive retrieval is planned but not yet evaluated.”
- “The current evidence does not establish a benchmark advantage.”
- “Historical results are retained as a separate baseline and were not modified by the recent repair sequence.”

Note on the template's example sentences, against this repository's evidence: the second example ("Adaptive retrieval is planned but not yet evaluated") is no longer true here — adaptive retrieval is implemented and evaluated (TrueAdaptive v1 vs IRCoT on Test-400 BM25, §2). The first example ("The contradiction veto is implemented and covered by offline tests") is also not true here — no contradiction veto exists in this repository (§3.4). The discipline itself stands: every claim in this document is scoped to the completed, saved experiment that demonstrates it, and the examples should be re-checked against the evidence map (§5) before reuse.

## 7. Paper-facing narrative

### Problem

One-shot RAG cannot determine when retrieved evidence is missing, contradictory, or insufficient for a multi-hop answer.

### Approach

E-RAG maintains an explicit belief graph over claims and evidence, uses it to identify uncertainty and conflicts, and controls retrieval, stopping, and abstention.

### Engineering safeguards

Evidence deduplication, run provenance, fail-closed resume, explicit stopping telemetry, and controlled output handling make future runs reproducible and auditable.

Note on the safeguards sentence, against this repository's evidence: of the four safeguards named, only run provenance is implemented here in a verifiable form (row-level retriever provenance, `results/README.md`, manifest SHAs, cache key versioning). Evidence deduplication, fail-closed resume, and explicit stopping telemetry as described in the template's §3 are `not recoverable from repository` (§3.1–§3.2). The safeguards the repository does establish are: the empty-completion cache guard, cache key versioning with namespace rotation, row-level retriever provenance, and the verification script that recomputes headline figures from raw rows.

### Safety controls

The contradiction veto prevents high draft confidence from overriding grounded refutations of answer-critical claims. Dependency-aware stopping is intended to prevent premature fast-path exits.

Note on the safety-controls sentence, against this repository's evidence: no contradiction veto exists in this repository (§3.4), and no missing-dependency fast path is recorded in it (§4.4). What the repository does establish as safety controls is abstention: the system abstains when answer confidence falls below `theta_abs` (0.50 in the tuned configuration, step 4) and when the draft is "unknown" (40 Test-400 rows refused by the reader). The veto sentence should not be used for this repository until a veto is implemented and tested.

### Evaluation plan

Controlled comparisons against one-shot RAG, fixed-budget E-RAG, IRCoT, and component ablations will test quality, retrieval cost, token cost, abstention behavior, and robustness.

### Current evidence boundary

The current repository establishes mechanisms and offline tests, and — beyond that — one completed, saved benchmark demonstration and several analyses, all scoped to their benchmarks:

- **TrueAdaptive v1 beats IRCoT on Test-400 BM25** (HotpotQA dev-distractor slice, N=400, BM25, k=3, frozen systems, 0 cache hits): EM 0.4750 vs 0.4200, F1 0.6192 vs 0.5674, 4.78 vs 2.545 calls/Q; McNemar b=38, c=16, p=0.0043. Artifacts: `results/trueadaptive/erag_trueadaptive_test_bm25.jsonl`, `results/ircot_test_bm25.jsonl`, commit `d69490f`. TrueAdaptive also beats Balanced BM25 (EM 0.4450 at 8.95 calls/Q) by +3.0 pts at −46.6% calls. This is a demonstration on one retriever (BM25) and one held-out dev slice, not a generalization claim: MiniLM Test-400 for v1 was not required under the agreed rule, and the tuned system has not yet been tested on Test-400.
- **H1 supported interim** (v1 system vs Standard-BM25: ΔEM +0.0725, 95% CI [0.0350, 0.1125], p=0.00034); the confirmatory re-run on the tuned system is owed at Phase 2, and Holm correction is pending H4's Test-400 p-value.
- **H6 supported strongly**: all of TrueAdaptive's gain over IRCoT concentrates where hop-0 retrieval was incomplete (n=192, ΔEM +0.1146, CI [0.0521, 0.1823], p=0.00094); zero gain where retrieval was complete (n=208, ΔEM 0.0000). This is the mechanism result, and it is scoped to the same Test-400 BM25 comparison.
- **H2 not supported** (NLI verifier, 60-pair set: macro-F1 0.6825 < 0.70; contradicted recall 0.75 passed). **H5 not supported on a cache-confounded test** (the E5 memory run is a replay, not a null; memory benefit is unevaluated). **H4 Test-400 ablation not yet run** (dev interim inconclusive; the latency bound as written is unmeetable and needs a dated clarification).
- **Tuned system (theta_abs = 0.50, max_claims = 8, reader grounding on, unknown prompt base) judged on dev only so far**: Dev-100 BM25 EM 0.5100, selective EM 0.6456, wrong-answer rate 0.3544, coverage 0.790 — via the accepted pre-registered counterfactual (the live runs were cache replays and were discarded as evidence). The step-5 static hop cap was measured and NOT adopted (EM unchanged, calls/Q 4.49 vs 4.65; verdict SUPERSEDED). Step 7's learned continuation policy passed its offline gate on re-check with margin (counterfactual simulation after the hop-0 retrain: EM 0.5152, 3.92 calls/Q; final model retrained, τ = 0.05 — the original marginal pass, EM 0.5000, is superseded) but is not wired in yet, so the tuned system's live numbers are unchanged. Test-400 confirmation is pending (Phase 2, pre-registered verdict).
- **Cost**: TrueAdaptive v1 uses 4.78 calls/Q on Test-400 BM25 vs 8.95 for Balanced and 2.545 for IRCoT; the Reference→Balanced call reduction is −39.8% (14.22 → 8.56 calls/Q, Test-400 MiniLM), not the "45.4%" figure that circulated earlier. Cost claims are scoped to these measured runs; token and latency figures are reported in `research/cost/` and were not independently recomputed for this draft.

What the evidence does **not** establish: benchmark superiority on any dataset other than the HotpotQA dev-distractor slice; superiority on any retriever other than BM25 for the adaptive system; memory benefits; NLI verifier reliability beyond a 60-pair set; or robustness. The mechanisms are implemented and covered by offline tests (126 passed, 1 failed — the known pre-existing retry-test mismatch — measured 2026-11-09 at HEAD `fc1a428` plus the uncommitted `--write-artifact` flag, exercised separately); the benchmark claims above are the only ones a completed, saved experiment demonstrates.
