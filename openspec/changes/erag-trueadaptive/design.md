# Design: E-RAG-TrueAdaptive (v1)

Source: `docs/audit-adaptive-llm-calling.md` §11. This design records the
mechanisms exactly as audited; anything not listed here is out of scope
for v1. **Gap A (entropy-gated retrieval) is v2, not v1** — its design is
kept below as Mechanism 2 (deferred) so the follow-up change starts from
a written spec, but no code for it is built in v1.

## Mechanism 1 — Sequential self-consistency (Gaps B + C) — v1

- **Location:** new `sequential_consistency()` in
  `src/epistemic/confidence.py`. The existing `self_consistency()` stays
  as the reference implementation for A/B comparison.
- **Behaviour:** sample one completion at a time (same `answer_messages`,
  temp 0.7, distinct `sample_idx` so the cache still works). After each
  sample, compute the running normalised-answer distribution and its
  Shannon entropy H (natural log).
- **Stopping:** stop when the leading answer has an unassailable majority
  given the remaining budget (e.g. stop after 2 samples if they agree —
  majority is then at least 2/3 regardless of the third), or when
  ΔH < 0.05 **and** at least 2 samples have been taken. Cap M at 3, never 5.
  A single sample (k=1) returns immediately.
- **Return shape:** identical to `self_consistency`
  (`conf_majority`, `conf_draft_agreement`, `samples`) so `conf_value()`
  and the rest of `run_erag` are untouched, plus `entropy`,
  `entropy_history`, `n_samples`, `stopped_early` for diagnostics.
  Log H per sample; report the distribution of stopping points on Dev-100.
- **Flag:** `erag.sc_mode: sequential | fixed`, default `fixed`.
  In `run_erag` the SC call site dispatches through a single helper so
  both the hop-0 call and the post-hop resample use the same mode. The
  sequential cap is `min(sc_samples, 3)`.

## Mechanism 2 — Entropy-gated initial retrieval (Gap A) — DEFERRED to v2

- **Status:** NOT built in v1. No `parametric_gate` flag, no closed-book
  probe in `run_erag`, no gate logging in v1.
- **Design (kept for v2):** top of `run_erag`, behind `erag.parametric_gate`
  (default false). Before any retrieval, generate a closed-book draft
  (1 call, `closed_book_messages`, temp 0.0 — prompt already exists in
  `src/llm/prompts.py`) plus one SC sample at temp 0.7 (1 call). If the
  sample agrees with the draft *and* the draft is not "unknown", skip
  retrieval and answer from parameters — 2 calls total, 0 retrieval.
  Otherwise proceed to the normal retrieval loop. Do not double-count the
  probe sample as a later SC sample.
- **Guardrail:** the gate must be conservative. Closed-book EM is 0.20 on
  Test-400, so false skips are the main risk. Log the gate decision per
  record (`tracker` + record field). On Dev-100 report the skip rate and
  the false-skip rate (a skip is "false" if the closed-book answer is
  wrong and the retrieval-loop answer would have been right). If the
  false-skip rate cannot be measured cleanly, the gate ships off by
  default.
- **Note:** this is the only mechanism that can take a question below the
  current 4-call floor, and the only one that can produce a 2-call path.

## Mechanism 3 — Gate SC behind the Fast Path — v1

- **Location:** hop-0 order in `run_erag`, behind
  `erag.gate_sc_behind_fast_path` (default false). Applies only in active
  mode, only on hop 0, only when SC has not run yet (`c0 is None`) and the
  `no_conf` ablation is not set. Observational mode and `no_adaptive`
  keep the existing order.
- **New order:** draft (1) → claim extraction (1) → graph/NLI (0) →
  Fast-Path check → SC *only if* gaps exist or `min_eff < theta_fast`.
- **Provisional graph:** the pre-SC graph is built with provisional
  `c0 = 1.0` (the same prior the `no_conf` ablation uses), so its
  `min_eff` reflects evidence strength alone. If the Fast Path is taken,
  SC is skipped. If it is not taken, SC runs (sequential or fixed per
  `sc_mode`) and the graph is **rebuilt** with the real `c0`, so the
  graph that drives retrieval is never based on the provisional value.
- **Effect:** fast-path floor drops from 5 (Balanced) to 2 calls.
- **`c0` definition when SC is skipped:** `c0 = min_eff` of the
  provisional graph, recorded as such in the result
  (`c0_source: "fast_path_min_eff"`, `sc_skipped_fast_path: true`).
  When SC runs, `c0_source: "sc"`. This changes the meaning of `c0`,
  so it must be explicit in code and in results, not silent.
- **Isolation:** A/B on Dev-100 against sequential SC alone (Mechanism 1),
  so the EM effect of this step is measured on its own. The two changes
  land in separate commits for exactly this reason.

## Config — `configs/erag_trueadaptive.yaml` (v1, frozen at Step F)

- `sc_mode: sequential`, M cap 3 (`sc_samples: 3`),
  `gate_sc_behind_fast_path: true`, `parametric_gate` NOT set (v2),
  `eig_strategy: direct`, `claim_strategy: incremental`,
  `post_hop_resample: never`, `saturation_precheck: true`.
- Thresholds unchanged: `theta_fast 0.8`, `theta_gap 0.6`, `theta_abs 0.4`.
- `max_claims: 5` (the draft's 3 is ungrounded — audit §10; revert to 5
  before touching thresholds if EM drops).
- **New `cache_namespace`** (`dev_trueadaptive_v1`,
  `test_trueadaptive_v1`). Never reuse `dev_v1`/`test_v1`.
- Prompts unchanged. Any prompt change is a separate, explicitly approved
  change.

## Testing

- Call-count tests first, with mocked LLM (`tests/test_erag.py` pattern:
  counting mock whose `chat` increments `tracker.llm_calls`, mirroring the
  real `LLM.chat`), asserting exact `tracker.llm_calls` and call order
  for: fast-path Reference (7), fast-path Balanced (5), 1-hop Balanced (7),
  sequential SC stops at 2 on agreement, SC skipped on fast path (2 calls),
  v1 1-hop (5 calls). Tests for old paths must pass against current code;
  tests for new paths must fail until the code lands.
- `tests/test_retrieval.py` (8 tests) — re-run status, 2026-11-08: **8/8
  passed** after downloading MiniLM with `HF_HUB_DISABLE_XET=1`
  (the XET endpoint returns 403 in this VM; plain HTTPS download works).
  Model weights now cached in `~/.cache/huggingface`.
- Dev-100 validation via `scripts/run_experiment.py` (system erag, split
  dev). Test-400 once, via `run_experiment.py` with split test — do **not**
  use `run_phase4_ircot_bm25.py` or `run_phase5_four_retrievers.py`
  (Windows-only `ctypes.windll` lock crashes on this Linux VM; also the
  Phase 3 write guard refuses to overwrite frozen results).

## Risks

- Sequential SC increases round trips per question (fewer total calls, more
  sequential latency); watch `tracker.failures` and latency on Dev-100.
- Divergence from upstream grows with every local commit; keep the diff
  small and well-separated. Upstream `6aced98` is merged into master as
  `9564676` and changed zero lines in `src/` / `configs/` / `tests/`.
- Groq: no key is saved; live runs need a transiently supplied key, and
  `NO_PROXY=localhost,127.0.0.1` is required in this VM.
