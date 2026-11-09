# ERag — Project Context for OpenSpec

## Purpose
ERag is a research codebase comparing three multi-hop RAG systems on HotpotQA —
Standard RAG, IRCoT (Trivedi et al., interleaved reasoning + retrieval), and
E-RAG (Epistemic Retrieval-Augmented Generation: belief graph + NLI verification
+ EIG-inspired targeted retrieval + Fast Path + safe abstention) — for a
Springer journal paper. The current work stream is **E-RAG-TrueAdaptive**:
make E-RAG's LLM calling adaptive so mean calls/question falls well below the
current ~8.6 (Balanced, MiniLM, Test-400) without losing exact-match accuracy
vs IRCoT (~2.5 calls/Q).

## Tech stack
- Python 3.12.3, virtualenv at `.venv/` (torch 2.15.0+cpu, transformers 5.22.2,
  sentence-transformers 6.2.0, faiss-cpu 1.15.1, groq 1.7.0, rank-bm25 0.2.2)
- LLM: Groq API, model `openai/gpt-oss-20b` (`configs/base.yaml`), SQLite
  response cache at `results/cache.sqlite` (namespace per run)
- Retrieval: per-question distractor index, k=3. BM25Plus, or FAISS
  `IndexFlatIP` over MiniLM (384d), E5 (768d, `query:`/`passage:` prefixes),
  BGE (768d, query instruction prefix)
- NLI: local cross-encoder `cross-encoder/nli-deberta-v3-base`, CPU,
  memoised in `results/nli_memo.pkl` — no LLM calls for verification
- Evaluation: HotpotQA only, in `data/manifests/` — `dev.jsonl` (N=100, tune
  here), `test.jsonl` (N=400, frozen, run once at the end)
- Configs are deep-merged YAML: `load_cfg("configs/base.yaml", <overlay>)`

## Conventions for OpenSpec work
- Do not modify `src/`, configs, or `results/` except through an explicit
  OpenSpec change proposal that the user has approved; audit first, change
  second. Every change gets `proposal.md`, `design.md`, `tasks.md` under
  `openspec/changes/<name>/` and is archived only when its tasks are done.
- Fair-comparison rule: retriever, k, prompts, model, and NLI thresholds
  stay identical across Standard / IRCoT / E-RAG in any benchmark. Never
  change reasoning logic or prompts inside a benchmark-only change.
- Tune on Dev-100; Test-400 is run once, at the end, for both systems.
  Never overwrite frozen historical test results
  (`scripts/run_phase3_evaluation.py` has a write guard for this).
- Current user constraints (2026-11-08): adaptive E-RAG first; no BGE runs
  for now; one main retriever (MiniLM) for the E-RAG vs IRCoT comparison;
  a second retriever only after it performs on HotpotQA; new dataset last.
- Upstream is `ManojAdapakala/ERag` (fetch-only, push disabled). This fork's
  push target is `Saumojit30/erag`. Never push to upstream; never merge
  upstream without an explicit user decision — fetch, inspect, then decide
  (merge / cherry-pick one commit / skip).
- Groq calls in this VM need `NO_PROXY=localhost,127.0.0.1` (the VM's
  default `NO_PROXY` with bracketed IPv6 breaks httpx). No API key is
  stored in the repo; the user supplies it transiently per run.
- This repo's OpenSpec CLI is installed locally at
  `~/workspace/tools/openspec` (see `docs/openspec-setup.md`); do not
  install it globally. `openspec/config.yaml` and existing changes are
  not to be overwritten by `openspec init`.
