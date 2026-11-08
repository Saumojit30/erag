# Audit: ERag Codebase for Adaptive LLM Calling (E-RAG-TrueAdaptive)

- **Date:** 2026-11-08
- **Repo:** `~/workspace/erag` (local fork; push target `Saumojit30/erag`, upstream `ManojAdapakala/ERag` fetch-only)
- **Scope:** Complete audit of the codebase as it stands locally, focused on building the adaptive LLM-calling part of E-RAG. No `src/` code, configs, or results were modified for this audit. OpenSpec scaffolding only (see `docs/openspec-setup.md`).
- **Method:** Read the actual code (`src/systems/erag.py`, `ircot.py`, `standard.py`, `src/llm/client.py`, `prompts.py`, `src/retrieval/index.py`, `src/epistemic/*`, all `configs/*.yaml`, the Phase 2/3/4/5 runners, `tests/`), recomputed means from `results/*.jsonl`, and checked every claim in the user's audit prompt against `git log --all` and the files on disk.

## 0. Repo state verification (2026-11-08, ~14:40 IST)

| Item | Found | Verdict |
|---|---|---|
| Local HEAD | `f779122` — "build: add missing rank-bm25 dep, pin CPU torch 2.15.0 for transformers 5.22", Author **and** Committer `Saumojit30 <santrasaumojit05@gmail.com>`, AuthorDate preserved | As expected; the only local commit on top of Manoj's base. Diff vs parent `3a4b9ba`: 2 files, 2 insertions (`requirements.txt` +`rank-bm25>=0.2.0`, new `constraints-cpu.txt` with `torch==2.15.0+cpu`). No code change. |
| Manoj base | `3a4b9ba` (2026-11-08 09:57 IST) | Base of our fork. |
| Upstream HEAD | `6aced98` (2026-11-08 14:22 IST), fetched, **not merged** | 2 commits ahead of base: `ed41253` (14:15, Phase 5 BGE + enriched results), `6aced98` (14:22, openspec archive). Local is **1 ahead, 2 behind**. See §9 for the divergence. |
| `git status` | Clean except untracked `configs/erag_adaptive.yaml` | Not clean in the strict sense — the draft adaptive config is untracked and untested. It was **not** committed or pushed. |
| `data/manifests/test.jsonl` SHA-256 | `0346c86f2c8c246ebd4843488172a8efcfed3d021ac8ffbbb0f97b0892f1059b` (400 lines) | **The audit prompt's `891fd4c1…` is WRONG for this copy.** `dev.jsonl` = `0a154a3d…`, `manifest.json` = `099d03f2…`. The prompt's hash must come from a different copy (probably the user's local `d:\erag`). Do not treat the local manifest as the prompt's frozen manifest until the two files are diffed. |
| `paper/` | **Missing.** No `paper/` directory, no `.tex` files anywhere in the repo. | The prompt's target `paper/manuscript_springer.tex` / `references.bib` does not exist in this GitHub-derived copy. Possibly local-only in `d:\erag`. The paper deliverable cannot be built from this repo as-is. |
| `tests/test_retrieval.py` | Exists, **8 test functions** | The prompt's "8/8 passing" claim matches the file's test count (see §8 for run status). |
| `.venv` | Exists, Python 3.12.3, torch **2.15.0+cpu**, transformers 5.22.2, sentence-transformers 6.2.0, faiss-cpu 1.15.1 | Build environment intact. |
| Groq | No API key saved anywhere; Groq calls need `NO_PROXY=localhost,127.0.0.1` in this VM (default `NO_PROXY` with bracketed IPv6 breaks httpx) | Any live run needs a transiently supplied key. No live Groq calls were made in this audit. |
| OpenSpec | `openspec/config.yaml` + `changes/phase-4-ircot-bm25` + `changes/phase-5-four-retrievers` + `.agents/skills/openspec-*` + `.agents/workflows/opsx-*` present; `openspec/specs/` was only `.gitkeep`; no `openspec/project.md`; no CLI binary | CLI now installed locally (see `docs/openspec-setup.md`). This audit added `openspec/project.md` and a `openspec/specs/retrieval/spec.md` stub. `openspec validate --all`: 3 passed, 0 failed. |

## 1. LLM-call trace — `src/systems/erag.py` (`run_erag`, 254 lines)

Every LLM call in E-RAG goes through one choke point, `LLM.chat()` (`src/llm/client.py`), which increments `tracker.llm_calls` — including on cache hits (see §3). The call sites in `run_erag` are:

| # | Call site | Function | Calls | When it runs | Unconditional? |
|---|---|---|---|---|---|
| 1 | Step 1 | Initial retrieval — `retriever.search(q, k=3)` | 0 LLM | Always, before any LLM call | **Yes — retrieval is unconditional.** No parametric-confidence check happens first. This is TrueAdaptive gap #1. |
| 2 | Step 2 | Draft — `llm.chat(answer_messages(q, pool), temp 0.0)` | 1 per hop | Every hop, including hop 0 | Yes (per hop) |
| 3 | Step 3 | Self-consistency — `self_consistency(llm, …, k=sc_samples, temp 0.7)` | `sc_samples` (default **5**; Balanced 3; Cost 2; draft-adaptive 2) | Hop 0 only (`if c0 is None`), unless `no_conf` ablation | **Yes — fixed M, sampled all at once** (a list comprehension over `range(k)` in `confidence.py`). No early stop, no sequential expansion. Gap #2. |
| 4 | Step 4–7 | Claim extraction — `extract_claims(llm, …, max_claims=5)` | 1 per hop, unless `claim_strategy` is `single_atomic` (0) or `incremental` and the draft is unchanged (0, reuses `prev_claims`) | Every hop under the default `full_reextract` | Yes under default config |
| 5 | Step 4–7 | NLI verification — `nli.verify(...)` per claim | 0 LLM | Local cross-encoder, CPU (see §5) | — |
| 6 | Step 4–7 | Belief graph — `build_graph` / `BeliefGraph.update()` | 0 LLM | Deterministic logit math | — |
| 7 | Step 10–11 | EIG query proposal — `propose_queries(llm, claim, …, n=3)` | 1 per hop, unless `eig_strategy == "direct"` (0) or `no_eig` ablation | Every hop that does targeted retrieval, under default `eig_strategy: llm` | Yes under default config |
| 8 | Post-loop | Post-hop resample — `self_consistency(…, k=sc_samples_post_hop or sc_samples)` | `sc_samples` (5 / 3) | Only if `hop > 0`, unless `post_hop_resample == "never"` (Cost, draft-adaptive) or `"conditional"` and the draft is unchanged (Balanced) | Conditional on hop count, but unconditional in the Reference config |

### Call counts per path (arithmetic from the code, then checked against measured means)

Reference config (`configs/base.yaml` + `final.yaml`: sc=5, full_reextract, llm EIG, always resample):

| Path | Draft | SC (hop 0) | Claims | EIG propose | Post-hop SC | **Total** |
|---|---|---|---|---|---|---|
| Fast Path, hop 0 (no gaps, `min_eff >= theta_fast`) | 1 | 5 | 1 | 0 | 0 | **7** |
| 1 hop | 2 | 5 | 2 | 1 | 5 | **15** |
| 2 hops (max) | 3 | 5 | 3 | 2 | 5 | **18** |

Measured mean for the Reference on Test-400 is **14.22** (`results/erag_active_test.jsonl`, recomputed) — consistent with a mix dominated by 1–2 hop questions. The **floor is 7 calls even for the easiest question**, because SC (5) and claim extraction (1) run *before* the Fast-Path check at Step 8/9. That ordering is the single most important structural fact for the adaptive work.

Balanced config (`erag_balanced.yaml`: sc=3, incremental claims, conditional resample, llm EIG):

| Path | Total |
|---|---|
| Fast Path, hop 0 | 1 + 3 + 1 = **5** |
| 1 hop, draft unchanged | 5 + 1 (draft) + 0 (claims reused) + 1 (EIG) + 0 (no resample) = **7** |
| 1 hop, draft changed | 7 + 1 (claims) + 3 (resample) = **11** |
| 2 hops | up to **15** |

Measured mean: **8.56** Test-400 / **8.92** Dev-100. Cost config (sc=2, single_atomic, never, direct EIG): floor **3** (1 draft + 2 SC, 0 claims, 0 EIG), measured mean **3.41** Test-400 at EM 0.395 — too steep an accuracy drop to copy (see §6).

Draft adaptive config (`configs/erag_adaptive.yaml`, untested): floor **4** (1 + 2 + 1), no post-hop SC, no EIG LLM call; projected mean ~5–6. It cannot go below 4 without a code change, because SC still runs before the Fast-Path check.

### Where the "semi-static" problems live (code locations)

1. **Unconditional initial retrieval** — `run_erag`, Step 1: `pool = retriever.search(q, k=k)` runs before any LLM call, before any estimate of whether the model already knows the answer. There is no closed-book / parametric probe anywhere in the file. A question the model could answer from parameters alone still pays retrieval + a full draft + SC + claims.
2. **Fixed-M self-consistency** — `src/epistemic/confidence.py:20-27`: `samples = [llm.chat(...) for i in range(k)]`. All `k` samples are fired unconditionally, at once. There is no notion of consensus so far, no entropy, no "stop after 1 if all agree". `k` is a YAML constant (`sc_samples`), not a function of the question.
3. **Hardcoded thresholds** — `theta_fast: 0.8`, `theta_gap: 0.6`, `theta_abs: 0.4` are plain YAML floats (`configs/base.yaml`), read once per run. Nothing adapts them per question, per hop, or per confidence history. `conf_value()` picks one of two fixed confidence definitions (`majority` / `draft_agreement`) from config.
4. **SC before the Fast-Path gate** — Step 3 runs before Step 8/9. The cheapest possible question still costs 7 (Reference) / 5 (Balanced) calls. Any sub-5 target requires moving or gating the SC call itself, not just tuning its `k`.
5. **Duplicate work after a hop** — under the default `full_reextract` + `always` resample, a hop re-pays a draft (1), a full claim extraction (1), and a full SC (5). The Phase 2 knobs (`claim_strategy`, `post_hop_resample`) already exist to suppress this, but the defaults are the expensive ones, and the knobs are static per-run, not per-question.
6. **EIG proposal is LLM by default** — `targeted_retrieve(..., eig_strategy="llm")` spends 1 LLM call per hop generating 3 candidate queries, then runs 3 probe searches and picks the best by `(1 - claim.eff) * novelty`. The "False-Search" phenomenon (audit §4 below) shows this often buys nothing: the best query returns passages already in the pool.

## 2. Baselines — `ircot.py` and `standard.py`

### IRCoT (`src/systems/ircot.py`, 79 lines)

| Call site | Calls | When |
|---|---|---|
| Initial retrieval | 0 LLM | Always |
| `next_step` — one reasoning sentence, temp 0.0, max_tokens 256 | 1 per step, `max_steps: 4` | Loop; stops early when the sentence starts with "So the answer is:" or is empty |
| Final reader — `llm.chat(answer_messages(q, pool))` | 1 | Always, after the loop |

Total: **1–5 calls/Q, measured mean 2.51 (MiniLM) / 2.59 (BM25)** on Test-400. No SC, no claims, no NLI, no confidence gating — the next retrieval query is just the last reasoning sentence, and retrieval is free (local FAISS/BM25). This is why IRCoT is the cost baseline to beat: its cost scales with *reasoning steps actually taken*, which is already adaptive in a crude way (early stop on answer). E-RAG's extra ~6 calls/Q over IRCoT buy +2.25pt EM (MiniLM: 0.4475 vs 0.4250) and much better calibration (ECE 0.385 vs 0.575, AUROC 0.733 vs 0.500) — the question for TrueAdaptive is how much of that premium is needed per question.

### Standard (`src/systems/standard.py`, 45 lines)

| Call site | Calls |
|---|---|
| Retrieval + one draft answer | **Exactly 1** |
| Closed-book variant | **Exactly 1**, no retrieval |

Measured mean 1.00, EM 0.4050 (MiniLM) / 0.4025 (BM25). The floor for any retrieval system.

## 3. LLM client, prompts, caching — `src/llm/client.py`, `src/llm/prompts.py`

- **Model:** Groq `openai/gpt-oss-20b`, `reasoning_effort: low`, `max_tokens: 1024` (from `configs/base.yaml`). The client passes `reasoning_effort` through only if set; the config comment itself says "confirm the API accepts this; remove it if it errors" — it evidently works, but this is an unverified assumption worth one explicit check before the TrueAdaptive runs.
- **Single choke point:** all LLM calls go through `LLM.chat(messages, tracker, temperature, max_tokens, sample_idx)`. `Tracker` is one instance per question (`llm_calls`, `in_tokens`, `out_tokens`, `latency`, `cache_hits`, `retrievals`, `probe_searches`, `failures`). Runners log `tr.llm_calls` per record, so every mean-calls number in this report is `tracker.llm_calls` averaged over records.
- **Caching — read this carefully:** `results/cache.sqlite`, key = SHA-256 of `{namespace, model, messages, temperature, max_tokens, reasoning_effort, sample_idx}`. On a cache hit the client **still increments `tracker.llm_calls` and adds the cached token counts**, and adds 0.0 latency. So *mean calls ≠ API spend*: a re-run over a warm cache costs $0 and ~0 latency but reports the same call count. Cost claims must therefore be read from tokens, not calls, on warm runs. Conversely, SC samples are distinct cache keys (`sample_idx` 0..k-1), so SC is never deduplicated by the cache.
- **Retries:** 1 try + 5 retries = 6 attempts, exponential backoff `min(2^attempt * 3, 45)`s, then `RuntimeError`. `tracker.failures` counts transient failures. A TrueAdaptive design that makes *more, smaller* calls must budget for retry latency; a design that makes *fewer* calls reduces failure surface.
- **Token accounting:** from Groq `r.usage.prompt_tokens / completion_tokens`; cached values are stored with the text. No token accounting exists for the local NLI or retrieval steps (they are not LLM calls).
- **Prompts:** `answer_messages` (system: "Answer the question using only the context… reply exactly: unknown"; user: context block + question), `closed_book_messages` (same, no context). Claims use a JSON-only system prompt (`CLAIM_SYSTEM`, max N claims, one `answer: true`, `depends_on` DAG). Query proposal uses `QUERY_SYSTEM` ("Write {n} short, different search queries…"). All prompts are shared across systems — the fair-comparison rule depends on this, and TrueAdaptive must not silently change them (any prompt change is a separate, explicitly approved change).
- **Cost formula in the runners:** Phase 5 uses llama-3.3-70b rates ($0.059/1M in, $0.079/1M out) for its CSV "Cost / 1k USD" column; Phase 3 uses Groq 20B rates ($0.10/1M in, $0.20/1M out) in `llm_call_audit.md`. The two are **not comparable** — flag any cost comparison that mixes them.

## 4. Retrieval — `src/retrieval/index.py` (200 lines)

- `MODEL_ALIASES`: `minilm`/`dense` → `all-MiniLM-L6-v2` (384d); `e5` → `intfloat/e5-base-v2` (768d); `bge` → `BAAI/bge-base-en-v1.5` (768d).
- Prefixes (in `Embedder.format_query` / `format_passage`): E5 gets `query: ` / `passage: `; BGE queries get `Represent this sentence for searching relevant passages: ` (passages unmodified); MiniLM gets none. Idempotent (checks `startswith` first).
- `Retriever`: FAISS `IndexFlatIP` over L2-normalised embeddings, cosine via inner product. `BM25Retriever`: `rank-bm25` `BM25Plus`, lowercase alphanumeric tokenisation. Both expose `search(query, k=3)`.
- `RetrieverFactory`: distractor (per-question index built from that item's context paragraphs) or pooled (one shared index). Default setting is **distractor**, k=3. Retrieval is local and free in LLM-call terms; its cost is latency (FAISS search + embedding encoding, ~900ms mean per question in the Phase 1 audit, dominated by embedding the pool) and, for dense models, a model download on first use (E5 ~1.1GB, BGE similar — **neither is in `~/.cache/huggingface` on this VM except the MiniLM/NLI models; a first dense run downloads**).
- No LLM call is made by retrieval itself. The only LLM-adjacent retrieval cost is the EIG proposal call (§1, call site 7) and the probe searches it triggers (`tracker.probe_searches`, 3 per hop under llm-EIG).

## 5. Epistemic layer — `src/epistemic/` (claims, belief_graph, confidence, nli)

| Component | LLM calls | What it does | Cost driver |
|---|---|---|---|
| `confidence.py` — `self_consistency(llm, q, paras, draft, tracker, k, temp 0.7)` | **k per invocation** (see §1) | Samples k completions, normalises answers, returns `conf_majority` (top answer share) and `conf_draft_agreement` (share matching the draft). The *only* confidence signal in the system, and it is expensive. | **The dominant cost: 8.61 of 14.22 calls/Q (60.6%) in the Reference** (`research/cost/llm_call_audit.md`): 5.00 at hop 0 + 3.61 post-hop. |
| `claims.py` — `extract_claims(llm, …, max_claims=5)` | 1 per invocation | LLM decomposes draft + context into ≤5 atomic claims as JSON (`answer: true` on exactly one, `depends_on` DAG). Falls back to a single synthetic claim (`"The answer to … is …"`, `fallback: True`) if parsing fails — that fallback costs **0** LLM calls, which is exactly the `single_atomic` strategy, formalised. | 2.07 calls/Q in the Reference (initial + re-extraction after hops). |
| `nli.py` — `NLI` (`cross-encoder/nli-deberta-v3-base`) | **0 LLM** | Local cross-encoder, sliding 2-sentence windows, entailment/contradiction probs, memoised in `results/nli_memo.pkl` (pickle, MD5 key). `verify()` applies `theta_s`/`theta_c` (0.5) and an optional `pre_filter` (skip passages whose subject entities don't appear). | **Latency, not LLM calls:** ~1,606ms mean per question on CPU (59.7% of unmemoised wall time). `pre_filter: true` (Balanced/Cost) is a latency optimisation, not a call optimisation — don't confuse the two. |
| `belief_graph.py` — `BeliefGraph` | 0 LLM | Logit-space update: `z = logit(c0) + w_s·Σsup − w_c·Σcon`, clipped to ±6, sigmoid; then weakest-link propagation `eff = min(conf, parents' eff)`. `gaps(theta_gap)` = claims not "supported" or with `eff < theta_gap`; `min_eff()` = minimum `eff`; `answer_claim()` = the answer-bearing claim. | ~4ms per question. The graph is cheap; everything expensive is the LLM calls that feed it (draft, SC, claims) and the NLI that scores it. |

Key insight for TrueAdaptive: **the belief graph itself is nearly free**. The adaptivity problem is entirely about *which LLM calls feed the graph, and in what order*. Any design that reorders SC/claims after the Fast-Path check, or replaces a full SC with a sequential one, leaves the graph, NLI, and thresholds untouched — which is why this is a tuning + control-flow change, not a rebuild.

## 6. Configs — thresholds and Phase 2 knobs

| Config | sc | claim_strategy | post_hop_resample | eig_strategy | saturation_precheck | w_c | max_claims | NLI pre_filter | Measured (Test-400, MiniLM) |
|---|---|---|---|---|---|---|---|---|---|
| `base.yaml` + `final.yaml` (Reference) | 5 | full_reextract | always | llm | false | 1.0 | 5 | false | 14.22 calls, EM 0.4525 |
| `erag_balanced.yaml` (Balanced) | 3 | incremental | conditional | llm | true | 1.0 | 5 | true | **8.56 calls, EM 0.4475** |
| `erag_cost.yaml` (Cost) | 2 | single_atomic | never | direct | true | 1.0 | 1 | true | 3.41 calls, EM 0.3950 |
| `erag_adaptive.yaml` (**draft, untested**) | 2 | incremental | never | direct | true | 1.0 | 3 | true | *projected ~5–6, EM unknown* |

Thresholds are identical in all four: `theta_fast 0.8`, `theta_gap 0.6`, `theta_abs 0.4`, `max_hops 2`, `pool_cap 12`, `sc_temperature 0.7`, `confidence_def majority`. `final.yaml` froze `w_s=1.0, w_c=1.0` from a weight grid (AUROC 0.6740, ECE 0.3734, Brier 0.2695 on dev). `base.yaml` still has `w_c: 2.0` — the overlay wins, but the discrepancy is a trap for anyone loading `base.yaml` alone.

Phase 2 knob semantics (all already implemented in `erag.py`, no new code needed to use them):
- `claim_strategy`: `full_reextract` (1 LLM call/hop) | `incremental` (0 if draft unchanged) | `single_atomic` (0 always).
- `post_hop_resample`: `always` | `conditional` (skip if draft unchanged) | `never`.
- `eig_strategy`: `llm` (1 LLM call/hop for query proposal) | `direct` (use the claim text as the query, 0 calls).
- `saturation_precheck`: stop if `len(pool) >= pool_cap (12)` before another hop.
- Ablations: `no_nli | no_conf | no_prop | no_adaptive | no_fast | no_eig` — `no_conf` sets `c0 = 1.0` and skips SC entirely, which is a useful experimental control for measuring SC's value, but not a production setting.

## 7. Runners — what they actually run

| Script | Split | Systems | Notes / traps |
|---|---|---|---|
| `scripts/run_experiment.py` (259 lines) | `debug`/`dev`/`test` per config | one system per invocation (`--config`, `--set` overrides) | Generic runner; writes one JSONL per run with `llm_calls`, tokens, `em`, `f1`, `recall`, `all_gold`, `answer_conf`, `hops`, `pool_titles`. This is the runner TrueAdaptive dev runs should use. |
| `scripts/run_phase2_experiments.py` (381 lines) | **Dev-100** | E-RAG only, sweeps (SC k, resample mode, NLI pre-filter, query strategy, saturation) + Reference/Balanced/Cost comparison | The source of the Phase 2 numbers in §6. Loads `data/manifests/dev.jsonl`. |
| `scripts/run_phase3_evaluation.py` (521 lines) | **Test-400, once** | Closed-book, Standard, IRCoT, E-RAG-Reference, Balanced, Cost | Has a **write guard**: refuses to overwrite frozen `results/{standard,ircot,erag_active,closed_book}_test.jsonl`. Produces `research/cost/cost_effectiveness_matrix_test400.csv` + `operation_cost_test400.csv` + Pareto figures. |
| `scripts/run_phase4_ircot_bm25.py` (320 lines) | **Test-400** | Standard/IRCoT/E-RAG-Balanced × {BM25, MiniLM} | Windows-only process lock (`ctypes.windll` — will crash on Linux if the lock path is hit; the lock is acquired unconditionally at startup, so check this before any Linux run). Outputs `research/ircot/bm25_vs_dense_benchmark.csv`. |
| `scripts/run_phase5_four_retrievers.py` (344 lines) | **Test-400** | Standard/IRCoT/E-RAG-Balanced × {BM25, MiniLM, E5, BGE} = 12 cells | Same Windows-only lock (`results/phase5/.runner.lock`). Reuses BM25/MiniLM runs; only the 6 new E5/BGE cells are run. **Do not run this now** — user constraint: no BGE. |

## 8. Tests

- Total: **48 test functions** across 12 files. `tests/test_retrieval.py` has **8** (embedder normalisation/memo, retriever ranking, distractor factory, manifest integrity/disjointness, gold facts in context, BM25 ranking/factory, prefix formatting, alias resolution) — matching the prompt's "8/8" count.
- Fast tests run in this audit (no Groq, no dense model, no network):
  `NO_PROXY=localhost,127.0.0.1 .venv/bin/python -m pytest tests/test_config.py tests/test_metrics.py -q` → **12 passed in 3.98s**.
- `tests/test_retrieval.py` was **not** run in this audit: its first run attempts to download/load `all-MiniLM-L6-v2` and the run stalled awaiting a confirmation prompt for that download, so it was killed rather than approved blindly. It must be re-run explicitly (with the model cached or the download approved) before any TrueAdaptive work that touches retrieval — do not claim it passes until then. The earlier 18-passed figure from the build session (config+metrics+BM25/cache/claims) is from 2026-11-08 and is not re-verified here except for the 12 above.
- `tests/test_erag.py` (4 tests) uses `MagicMock` LLMs with a scripted `chat.side_effect` (draft, 5 SC samples, claims JSON) — this is the pattern TrueAdaptive unit tests should follow: mock the LLM, assert the *call sequence and count*, not just the answer. No such call-count test exists yet for the adaptive paths (e.g. "fast path costs ≤ N calls", "SC stops after 1 sample when unanimous") — that is a gap the build phase must close first.

## 9. Results verification — claimed numbers vs files on disk

Recomputed from local `results/*.jsonl` (400 rows each unless noted):

| Claim (audit prompt / conversation) | Local verification | Verdict |
|---|---|---|
| Phase 4: E-RAG 0.4450 vs IRCoT 0.4100 EM (BM25) | `research/ircot/bm25_vs_dense_benchmark.csv`: E-RAG-Balanced/BM25 EM **0.4450**, IRCoT/BM25 **0.4100**; All-Gold 0.8650 vs 0.6150 | **Confirmed.** |
| Phase 4: E-RAG +3.50pt EM, +25.00pt All-Gold | 0.4450−0.4100 = +0.0350; 0.8650−0.6150 = +0.2500 | **Confirmed.** |
| Phase 2/3: "45.4% LLM call reduction" | Calls: Reference 14.22 → Balanced 8.56 = **−39.8%**. Tokens: 9,081.6 → 4,915.5 = **−45.9%**. Cost: $1.008 → $0.554 /1k = **−45.0%**. | **Wrong as stated.** There is no 45.4% *call* reduction in the local files. The ~45% figure is a token/cost reduction. Quote it as "−39.8% calls, −45.9% tokens, −45.0% cost" or the paper will be challenged on arithmetic. (The string "45.4" appears nowhere in `research/cost/*.md` as a call reduction.) |
| "Pareto optimality with E-RAG-Balanced" | Balanced EM 0.4475 vs Reference 0.4525 (−0.5pt) at 8.56 vs 14.22 calls; Cost EM 0.3950 at 3.41 calls | **Plausibly supported** — Balanced keeps 98.9% of Reference EM at 60% of the calls. The Pareto figure is in `research/cost/fig_pareto_em_vs_cost.png`; the underlying CSV is `cost_effectiveness_matrix_test400.csv`. |
| Mean calls ~9 vs ~2.5 vs ~1.0 | E-RAG-Balanced/MiniLM **8.56**, IRCoT/MiniLM **2.51**, Standard **1.00** (Test-400) | **Confirmed** (8.56 rounds to ~9; BM25: 8.95 / 2.59 / 1.00). |
| Balanced Dev-100 EM 0.5100 at 8.92 calls | `results/cost_opt/erag_balanced_dev.jsonl`: 100 rows, EM **0.5100**, mean calls **8.92** | **Confirmed.** |
| Cost Dev-100 EM 0.3600 at 3.44 calls | Stated in draft adaptive config header; Cost Test-400 is 0.3950 at 3.41 — dev figure not recomputed here (no `erag_cost_dev.jsonl` mean was printed in this audit; verify before citing) | **Partially confirmed — recheck the dev figure before citing.** |

### Local vs upstream divergence (the important one)

| Item | Local (`f779122`, base `3a4b9ba`) | Upstream (`6aced98`, read via `git show`, **not merged**) |
|---|---|---|
| `results/phase5/erag_balanced_e5_test.jsonl` | **278/400** (122 missing) | **400/400** |
| `results/phase5/*_bge_test.jsonl` | Absent (no BGE files at all) | Present, 400/400 for all 3 systems |
| `research/retrievers/four_retriever_benchmark.csv` | 9 rows; E5 rows are placeholders (N=1, EM 1.0) | 12 rows, all N=400; E-RAG/E5 EM **0.4900**, E-RAG/BGE **0.4800**, IRCoT/BGE **0.4650**, Standard/BGE **0.4525** |
| `research/retrievers/four_retriever_analysis_report.md` | Absent | Present (263 lines, upstream) |
| `results/enriched/` (12 files) | Absent | Present (upstream) |
| `scripts/enrich_results_with_retrieval_metrics.py` | Absent | Present, 232 lines (upstream) |
| `src/`, `configs/`, `tests/` | — | **Zero changes** (`git diff 3a4b9ba..upstream/master -- src/ configs/ tests/` is empty) |

Consequence: upstream has *completed* Phase 5 (including the BGE the user does not want to run now), but it changed **no reasoning code**. Our local copy is behind only on results/reporting, not on architecture. That makes the divergence low-risk for TrueAdaptive: the adaptive work is in `src/systems/erag.py`, which is identical in both copies. The decision to take or skip the upstream Phase 5 results is a reporting decision, not a code-merge decision — and it can be deferred until after TrueAdaptive is built.

## 10. Discrepancies list (consolidated)

1. **`paper/` missing** — no manuscript, no `references.bib`, no `.tex` anywhere. The Springer deliverable cannot be produced from this repo. *Action: locate the paper in `d:\erag` or treat it as a new deliverable.*
2. **Manifest SHA mismatch** — prompt claims `891fd4c1…` for `test.jsonl`; local SHA is `0346c86f…`. *Action: diff the two `test.jsonl` files before any Test-400 run is cited as "frozen".*
3. **"45.4% LLM call reduction" is wrong as stated** — verified −39.8% calls / −45.9% tokens / −45.0% cost (Reference → Balanced). *Action: correct the number wherever it is cited.*
4. **Git status not clean** — untracked `configs/erag_adaptive.yaml` (draft, untested). The prompt's "git status clean" describes `d:\erag`, not this copy. *Action: keep it untracked until Dev-100 validation; do not commit it as part of the audit.*
5. **Prompt commit hashes — all exist, but check the subjects:** `017db9a` (Phase 0 audit), `5ef8533` (Phase 1 cost audit), `cfd1b3c` (Phase 2 cost optimisations), `b944672` (Phase 3 report), `9144d13` (Phase 4), `24dec3d` (E5/BGE wrappers), `e0bdc6a` (Phase 5 openspec), `d1dbb5c` (Phase 5 runner). All 8 resolve in `git log --all`. No discrepancy here — the history is intact.
6. **Phase 5 tasks.md is stale locally** — `openspec list` reports phase-5 as "5/9 tasks" (3.1, 3.2, 4.1, 4.2 unchecked), while upstream's `6aced98` archives the change as complete. The local tasks file was never updated after the upstream completion. *Action: do not mark it complete locally until the upstream results are deliberately taken or skipped.*
7. **Cost-rate inconsistency** — Phase 5 CSV uses llama-3.3-70b rates; Phase 3 audit uses Groq 20B rates. Cost/1k figures from the two phases are not comparable. *Action: pick one rate schedule for TrueAdaptive reporting (Groq 20B, the actual model).*
8. **`reasoning_effort: low` is unconfirmed** — `configs/base.yaml` itself flags it ("confirm the API accepts this"). It works in practice (the build smoke test succeeded), but there is no recorded check that Groq honours it vs ignores it. *Action: one explicit check before TrueAdaptive runs.*
9. **Windows-only process locks** — `run_phase4_ircot_bm25.py` and `run_phase5_four_retrievers.py` call `ctypes.windll` unconditionally. They will crash on this Linux VM if the lock is acquired. *Action: guard or remove the lock before any Linux run of those scripts (or use `run_experiment.py` instead).*
10. **Test coverage gap for adaptivity** — no test asserts LLM *call counts* or call *order* for any adaptive path. `test_erag.py` mocks the LLM but only checks the observational-mode answer. *Action: add call-count tests before changing `erag.py` (see §12, step B).*
11. **E5/BGE models not on this VM** — `~/.cache/huggingface` has no E5/BGE weights. Irrelevant for TrueAdaptive on MiniLM, but a first E5/BGE run would download ~1GB+ per model. *Action: none now (no BGE per user constraint).*

## 11. TrueAdaptive gaps — what "semi-static" means in this code, and the design that fixes it

The audit prompt names three gaps. Each maps to a precise code location and a concrete mechanism:

### Gap A — Unconditional initial retrieval (no parametric-confidence gate)
- **Location:** `run_erag` Step 1, `erag.py` line ~"pool = retriever.search(q, k=k)".
- **Today:** retrieval always runs, then a draft is generated from the pool. A question the model already knows still pays the full pipeline.
- **TrueAdaptive mechanism — entropy-gated initial retrieval:** before any retrieval, generate a **closed-book draft** (1 call, `closed_book_messages`, temp 0.0 — the prompt already exists in `prompts.py`) and probe parametric confidence cheaply. Only retrieve if the probe says the model does not know. Concretely, v1: closed-book draft + **one** SC sample at temp 0.7 (1 call); if the sample agrees with the draft *and* the draft is not "unknown", skip retrieval and answer from parameters (total 2 calls, 0 retrieval). If they disagree or the draft is "unknown", proceed to the normal retrieval loop. This is the only mechanism that can take a question below the current 4-call floor, and the only one that can produce a 2-call path. Risk: closed-book answers on HotpotQA are weak (Closed-Book EM 0.20 on Test-400) — the gate must be conservative (require agreement *and* a non-"unknown" draft), and its false-positive rate (skipping retrieval when retrieval was needed) must be measured on Dev-100 before it is trusted. Keep the gate's decisions logged per question (`tracker` + record field) so the false-skip rate is auditable.

### Gap B — Fixed-M self-consistency (no dynamic sequential sampling)
- **Location:** `src/epistemic/confidence.py:20-27` — `samples = [llm.chat(...) for i in range(k)]`.
- **Today:** all `k` samples fire at once, regardless of consensus. A question where the first two samples agree still pays for 5 (Reference) / 3 (Balanced).
- **TrueAdaptive mechanism — dynamic sequential sampling, M=1 → 3:** sample one completion at a time (same `answer_messages`, temp 0.7, distinct `sample_idx` so the cache still works). After each sample, compute the running answer distribution. Stop when the leading answer has an unassailable majority given the remaining budget, or at M=3. Concretely: stop after 2 samples if they agree (majority is then at least 2/3 regardless of the third); stop after 1 sample only if combined with Gap A (the closed-book probe already counts as a sample — do not double-count it); otherwise take the 3rd. Cap M at 3, never 5, in the TrueAdaptive config. Expected saving: on Dev-100, most questions should resolve in 2 samples instead of 3–5. This must be implemented as a new function (e.g. `sequential_consistency` in `confidence.py`) that returns the same dict shape as `self_consistency` (`conf_majority`, `conf_draft_agreement`, `samples`) so `conf_value()` and the rest of `run_erag` are untouched. The existing `self_consistency` stays as the reference implementation for A/B comparison.

### Gap C — Hardcoded thresholds, no variance stopping
- **Location:** `configs/*.yaml` (`theta_fast`, `theta_gap`, `theta_abs`) + `confidence.py` (no entropy anywhere in the codebase — grep finds no entropy computation).
- **Today:** thresholds are constants; confidence is a point estimate (`conf_majority`), never a distribution, so there is nothing to stop on.
- **TrueAdaptive mechanism — variance stopping, ΔH < 0.05:** after each sequential SC sample, compute the Shannon entropy H of the normalised-answer distribution (over samples so far). Stop sampling when the change in entropy between successive samples is < 0.05 **and** at least 2 samples have been taken — i.e. another sample is no longer changing what we believe. This is the stopping rule named in the audit prompt; implement it exactly as `ΔH < 0.05`, log H per sample, and report the distribution of stopping points on Dev-100. **Do not** make `theta_fast` / `theta_gap` / `theta_abs` learned or per-question in v1: keep them as YAML floats (unchanged: 0.8 / 0.6 / 0.4), log per-question `min_eff` and gaps, and retune them only after the v1 Dev-100 numbers exist. Learning thresholds before the sampling mechanism is stable would confound the experiment.

### Additional mechanisms already available (use them; do not rebuild them)
- **Gate SC behind the Fast Path:** the cheapest structural win after Gap B. Restructure `run_erag` so the order is: draft (1) → claim extraction (1) → graph/NLI (0) → Fast-Path check → SC *only if the graph is not already fast-pathed* (i.e. gaps exist or `min_eff < theta_fast`). This drops the fast-path floor from 5 (Balanced) to 2 calls. It changes the meaning of `c0` (confidence is then only computed when needed), so `c0` must default to the graph's own signal when SC is skipped — define this explicitly in the design (e.g. `c0 = min_eff` when SC is skipped, and record it as such). This is the highest-leverage single change in the audit; it is also the one most likely to change EM, so it needs its own Dev-100 A/B (on/off) rather than being bundled silently with the other changes.
- **Direct EIG + saturation precheck:** already implemented knobs (`eig_strategy: direct`, `saturation_precheck: true`). TrueAdaptive should default to them (saves 1 LLM call per hop and kills the False-Search phenomenon: 43.2% of Fast-Path questions on Test-400 in the Phase 1 audit — 48/111 Reference rows with `hops == 0` had `probe_searches > 0`, all exactly 3 — spent an EIG call + 3 probe searches for zero new passages. On Dev-100 the same definition gives 13/22 = 59.1%, so the 43.2% figure is specific to Test-400. [Verified 2026-11-09 from `results/erag_active_test.jsonl`: 48/111 = 43.2%, all with exactly 3 probe searches. The cache audit's L7 note checked Dev-100 instead of Test-400, which is why it could not reproduce the figure.])
- **Incremental claims + never resample:** already implemented (`claim_strategy: incremental`, `post_hop_resample: never`). TrueAdaptive should default to them, as the draft adaptive config already does.

### What TrueAdaptive is NOT (v1 scope guard)
- Not a new retriever, not BGE, not a new dataset, not an LLM fine-tune, not a prompt rewrite, not learned thresholds, not a belief-graph redesign. Any of those is a separate OpenSpec change.
- The belief graph, NLI, prompts, model, retriever (MiniLM, k=3), and eval harness are **frozen** for v1. Only `confidence.py` (new sequential sampler), `run_erag` (call order + the Gap A gate), and config (new `erag_trueadaptive.yaml` overlay) change.

## 12. Execution plan — build E-RAG-TrueAdaptive FIRST (option 2)

This follows the audit prompt's option 2 and the user's stated order (adaptive first, no BGE now, one main retriever, tune on dev, test once at the end). Each step is a separate commit on a feature branch; nothing is pushed until the user says so.

**Step 0 — OpenSpec change (before any code).** Create `openspec/changes/erag-trueadaptive/` with `proposal.md` (problem, goals, non-goals, the three gaps), `design.md` (the mechanisms in §11, the `c0`-when-SC-skipped definition, cache-key and Tracker compatibility), and `tasks.md` (the steps below as checkable tasks). Validate with the local CLI (`openspec validate erag-trueadaptive`). This is the spec the build is judged against.

**Step A — Branch.** `git checkout -b trueadaptive` from `f779122`. Keep `master` clean so an upstream merge/cherry-pick stays possible. All work happens on this branch.

**Step B — Call-count tests first (no production change yet).** In `tests/test_erag.py`, add mocked-LLM tests asserting exact `tracker.llm_calls` and call order for: fast-path Reference (7), fast-path Balanced (5), 1-hop Balanced, and the new gates (Gap A skip = 2 calls, sequential SC stops at 2 on agreement). These tests must pass against the *current* code for the old paths and fail for the new paths — that is the point. Also re-run `tests/test_retrieval.py` (8 tests) explicitly, with the MiniLM model cached or its download approved, and record the result.

**Step C — Sequential SC (Gap B + C).** Add `sequential_consistency()` to `src/epistemic/confidence.py` (same return shape as `self_consistency`; entropy + ΔH < 0.05 stopping, M cap 3). Wire it behind a config flag (e.g. `erag.sc_mode: sequential | fixed`, default `fixed` so existing configs are unaffected). Unit-test with mocked LLM: unanimous → stops at 2; split → goes to 3.

**Step D — Entropy-gated retrieval (Gap A).** Add the closed-book probe at the top of `run_erag` behind a flag (`erag.parametric_gate: true/false`, default false). Log the gate decision per record. Validate on Dev-100: report the gate's skip rate and false-skip rate (skipped but would have needed retrieval — measurable because Dev-100 has gold answers; a skip is "false" if the closed-book answer is wrong and the retrieval-loop answer would have been right).

**Step E — Gate SC behind the Fast Path.** Restructure the hop-0 order (draft → claims → graph → Fast-Path check → SC only if needed), with the `c0` fallback defined in the Step 0 design. A/B on Dev-100 against Step D alone, so the EM effect of this step is isolated.

**Step F — Config + Dev-100 validation.** Freeze `configs/erag_trueadaptive.yaml` (sc_mode sequential, M cap 3, parametric gate on, direct EIG, incremental claims, never resample, saturation precheck, thresholds unchanged). Run Dev-100 with `scripts/run_experiment.py` (system erag, split dev). Report: mean calls, EM, F1, skip rate, stopping-point distribution, false-skip rate, and the same for IRCoT/MiniLM on Dev-100 as the comparator. **Gate: proceed only if EM is within the user's tolerance of Balanced Dev-100 (0.5100) — see §14; if it is not, tune the gate/SC stopping, not the thresholds.**

**Step G — Test-400, once.** Run E-RAG-TrueAdaptive **and** IRCoT, both MiniLM, k=3, on Test-400 (`scripts/run_phase3_evaluation.py` pattern or `run_experiment.py` with split test; mind the write guard and the Windows-only lock in the Phase 4/5 scripts — do not use those scripts). This is the single Test-400 run. Report EM/F1/recall/All-Gold/coverage/selective EM/ECE/Brier/AUROC/mean calls/mean tokens for both, with McNemar + bootstrap CIs (`src/eval/stats.py` already implements these — use them, don't reimplement).

**Step H — Archive.** Mark the OpenSpec change complete, archive it (`openspec archive erag-trueadaptive`), and only then discuss the next step (architecture tuning, second retriever, new dataset) with the user.

## 13. Risks / conflicts with upstream

1. **Upstream Phase 5 completion is a reporting fork, not a code fork.** Taking it later is a `git show` / cherry-pick of results files, not a merge of `src/`. Risk is low; the risk is *citation* risk (citing local placeholder E5 numbers after upstream has real ones), not code risk.
2. **Divergence grows with every local commit.** We are 1 ahead / 2 behind today. Once `trueadaptive` lands, a future upstream merge of `erag.py` will conflict if Manoj ever touches `erag.py`. Mitigation: keep the TrueAdaptive diff small and well-separated (new function in `confidence.py`, flagged call-order change in `erag.py`), and fetch upstream before each step to check whether he has touched those files.
3. **Cache invalidation.** The TrueAdaptive config must use a **new `cache_namespace`** (e.g. `dev_trueadaptive_v1`, `test_trueadaptive_v1`). Reusing `dev_v1`/`test_v1` would silently reuse cached Reference/Balanced completions and invalidate the comparison — and because cache hits still count as calls (§3), the error would be invisible in the call counts and visible only in the (wrong) answers.
4. **The closed-book gate can silently lose EM.** A gate that skips retrieval too aggressively looks like a call-count win and an EM loss. The false-skip rate (Step D) is the guardrail; if it cannot be measured cleanly on Dev-100, the gate ships off by default.
5. **Groq rate limits / retries.** Fewer, larger calls are safer than many small ones; sequential SC *increases* the number of round trips per question (though it reduces total calls). Watch `tracker.failures` and latency on Dev-100; if retries spike, the sequential sampler is the suspect.
6. **No BGE / no E5 in v1.** E5/BGE would change recall and EM independently of adaptivity and confound the comparison. They stay out until TrueAdaptive is measured on MiniLM.

## 14. Open decisions for the user

1. **Main retriever — confirm MiniLM?** Assumed MiniLM (`all-MiniLM-L6-v2`, 384d, k=3, distractor) for the TrueAdaptive vs IRCoT comparison, per the task brief. Confirm, or pick BM25 (cheapest, no model download, EM slightly lower).
2. **Adaptive target — what is "good enough"?** The draft config targets ≤6 calls/Q with EM within 1pt of Balanced (Dev-100 0.5100 / Test-400 0.4475). TrueAdaptive's mechanisms (Gap A + gated SC) can plausibly go below that on easy questions — but is the target a *mean* (e.g. ≤5 calls/Q), a *ceiling* (e.g. no question over N calls), or an *EM tolerance* (e.g. within 1pt, within 0.5pt)? The Step F gate cannot be applied until this is set.
3. **Is the closed-book gate (Gap A) in scope for v1, or v2?** It is the only sub-4-call mechanism and the riskiest (false skips). Options: (a) v1 with a conservative gate + false-skip measurement; (b) v1 without it (floor 4–5 calls), gate as a follow-up change. Recommend (a) only if the user accepts the Dev-100 false-skip measurement as the decision point.
4. **Paper location.** Where is `paper/manuscript_springer.tex`? If it lives in `d:\erag`, the manifest SHA mismatch (§10.2) needs resolving before any Test-400 number is written into the paper.
5. **Upstream Phase 5 results — take or skip?** Upstream has completed BGE/E5 Test-400 with a report. Do we (a) fetch those result files into our copy later (read-only, for reference), (b) ignore them until after TrueAdaptive, or (c) treat them as the new Phase 5 baseline? Recommend (b) for now.

## Appendix — file inventory (audit-relevant)

- `src/systems/erag.py` (254), `ircot.py` (79), `standard.py` (45), `memory.py` (128, no LLM calls — memory read/write use NLI only)
- `src/llm/client.py` (Tracker + LLM + SQLite cache), `prompts.py` (answer / closed-book / claims / query prompts)
- `src/retrieval/index.py` (200), `src/epistemic/{claims,belief_graph,confidence,nli}.py`, `src/eval/{metrics,stats}.py`, `src/config.py` (24, `load_cfg` deep-merge)
- `configs/base.yaml`, `erag_balanced.yaml`, `erag_cost.yaml`, `final.yaml`, `erag_adaptive.yaml` (draft)
- `scripts/run_experiment.py`, `run_phase2_experiments.py`, `run_phase3_evaluation.py`, `run_phase4_ircot_bm25.py`, `run_phase5_four_retrievers.py`
- `tests/` — 48 test functions; fast subset (config+metrics) 12 passed in this audit
- `research/cost/llm_call_audit.md` (Phase 1 operation inventory — the source of the 14.22 / 8.61 / 4.15 / 1.46 breakdown), `research/cost/cost_effectiveness_matrix_test400.csv`, `research/cost/operation_cost_test400.csv`
- `research/retrievers/four_retriever_benchmark.csv` (local: 9 rows, E5 placeholders), upstream: 12 rows, all N=400

### Commands to reproduce the verification
```bash
cd ~/workspace/erag
git status; git log --oneline -3; git rev-list --left-right --count HEAD...upstream/master
sha256sum data/manifests/test.jsonl   # 0346c86f… (not 891fd4c1…)
ls paper/  # No such file or directory
NO_PROXY=localhost,127.0.0.1 .venv/bin/python -m pytest tests/test_config.py tests/test_metrics.py -q  # 12 passed
~/workspace/tools/openspec/node_modules/.bin/openspec validate --all  # 3 passed, 0 failed
```
