# Proposal: E-RAG-TrueAdaptive — Adaptive LLM Calling (v1)

## Status

Draft — prepared 2026-11-08 from `docs/audit-adaptive-llm-calling.md` (§11–§12),
updated to v1/v2 split on branch `trueadaptive` (base `9564676`, the merged
Manoj Phase 5 completion). No live runs yet.

**Decisions — resolved (user, 2026-11-08):**
1. Fixed retrievers for tuning: **MiniLM main, BM25 as second fixed check**,
   both k=3, distractor setting. Never switch retriever mid-tuning.
   (E5/BGE are better on Test-400 — E-RAG/Balanced E5 0.4900, BGE 0.4800
   vs MiniLM 0.4475 — but out of scope for v1; no BGE now.)
2. Adaptive target: **mean calls/Q ≤ 6 on Dev-100, EM ≥ 0.50** (within 1pt
   of Balanced Dev-100 0.5100; Test-400 Balanced 0.4475).
3. Closed-book / entropy-gated retrieval (Gap A) is **v2, NOT v1**.
4. Paper/manuscript does not exist yet — ignored; not a blocker.
5. Upstream Phase 5 results: fetched and **merged into master as
   `9564676`** (BGE/E5 Test-400, 12-cell matrix, Phase 5 report). No
   action needed now; they are reference only for v1.

## Why

E-RAG-Balanced averages 8.56 LLM calls per question on HotpotQA Test-400
(MiniLM), vs 2.51 for IRCoT and 1.00 for Standard, for +2.25pt EM over IRCoT
(0.4475 vs 0.4250). The cost is structural, not just tuning: the audit
traced every call in `src/systems/erag.py` and found the floor is 7 calls
(Reference) / 5 calls (Balanced) even on the easiest question, because
self-consistency (5 / 3 samples) and claim extraction run *before* the
Fast-Path check. Self-consistency alone is 8.61 of 14.22 calls (60.6%) in
the Reference. The current E-RAG is "semi-static": retrieval is
unconditional, self-consistency sampling is fixed-M, and thresholds are
hardcoded YAML floats.

## What Changes — v1

1. **Sequential self-consistency (Gaps B + C):** sample one completion at a
   time (M=1 → 3, cap 3, never 5), stop when the leading answer has an
   unassailable majority or when the change in answer-distribution entropy
   ΔH < 0.05 after at least 2 samples. New `sequential_consistency()` in
   `src/epistemic/confidence.py`, same return shape as `self_consistency`,
   behind a config flag (`erag.sc_mode: sequential | fixed`, default
   `fixed` so existing configs are unaffected).
2. **Gate SC behind the Fast Path:** reorder hop 0 to draft → claims →
   graph/NLI → Fast-Path check → SC only if gaps exist or
   `min_eff < theta_fast`. When SC is skipped, `c0` defaults to the graph's
   own signal (`c0 = min_eff`, recorded as such). This drops the fast-path
   floor from 5 (Balanced) to 2 calls. A/B on Dev-100 against sequential
   SC alone, so its EM effect is isolated.

## Deferred to v2

- **Entropy-gated initial retrieval (Gap A):** closed-book draft + one SC
  sample before any retrieval; skip retrieval and answer from parameters
  (2 calls total) when they agree and the draft is not "unknown". Behind
  `erag.parametric_gate` (default false). This is the only sub-4-call
  mechanism and the riskiest (false skips; closed-book EM is 0.20 on
  Test-400). It is NOT built in v1. Its design stays in `design.md`
  (Mechanism 2, marked v2) for the follow-up change.

## Non-goals (v1 scope guard)

- Not a new retriever, not BGE, not E5, not a new dataset, not an LLM
  fine-tune, not a prompt rewrite, not learned thresholds, not a
  belief-graph redesign. Any of those is a separate OpenSpec change.
- The belief graph, NLI, prompts, model (Groq `openai/gpt-oss-20b`),
  retrievers (MiniLM main / BM25 second check, k=3, distractor), and eval
  harness are frozen for v1. Only `confidence.py` (new sequential sampler),
  `run_erag` (call order), and config (new `configs/erag_trueadaptive.yaml`)
  change.
- Defaults already available are used, not rebuilt: `eig_strategy: direct`,
  `claim_strategy: incremental`, `post_hop_resample: never`,
  `saturation_precheck: true`. Thresholds stay `theta_fast 0.8`,
  `theta_gap 0.6`, `theta_abs 0.4` in v1.
- Compare only ERag-adaptive vs IRCoT, both on the same fixed retriever.

## Impact

- **Code:** `src/epistemic/confidence.py` (new function),
  `src/systems/erag.py` (call order, both flagged),
  `configs/erag_trueadaptive.yaml` (new), `tests/test_erag.py`
  (call-count tests first — see tasks).
- **Tests:** call-count tests with mocked LLM must exist *before* the code
  changes (audit §12 Step B).
- **Cache:** the TrueAdaptive config must use a **new `cache_namespace`**
  (`dev_trueadaptive_v1`); reusing `dev_v1`/`test_v1` would silently
  reuse cached Reference/Balanced completions. Cache hits still count as
  `llm_calls`, so the error would be invisible in call counts.
- **Branches:** work on branch `trueadaptive` from `9564676`; keep
  `master` clean. Nothing is pushed.
- **Evaluation:** tune on Dev-100 only; one Test-400 run at the end
  (TrueAdaptive vs IRCoT, both MiniLM, k=3). No BGE per user direction.

## References

- Audit: `docs/audit-adaptive-llm-calling.md` (2026-11-08, 286 lines)
- Draft config (untested, do not freeze): `configs/erag_adaptive.yaml`
- Baselines: Standard 1.00 calls / 0.4050 EM; IRCoT 2.51 / 0.4250;
  E-RAG-Balanced 8.56 / 0.4475; Reference 14.22 / 0.4525 (Test-400, MiniLM)
- Correction: "45.4% LLM call reduction" is wrong as stated — Reference →
  Balanced is −39.8% calls, −45.9% tokens, −45.0% cost.
