# Tasks: Tune-Memory-Effectiveness (tuning step 6)

Drafted 2026-11-09 from `docs/tuning-master-plan.md` (§3.6), the H5
assessment, `research/openspec_memory.md`, D-009, and fresh recomputation
from the stored E5 stream files (proposal.md, Why). Branch
`trueadaptive`. Nothing is pushed. Do not start the build until the
proposal is approved — the user approves by saying go (or by tapping the
offer); the build then follows this file.

## 0. OpenSpec change (before any code)

- [ ] 0.1 Create `openspec/changes/tune-memory-effectiveness/` with
  `proposal.md`, `design.md`, `tasks.md` (this file),
  `specs/memory-effectiveness/spec.md`.
- [x] 0.2 Validate with the local CLI:
  `~/workspace/tools/openspec/node_modules/.bin/openspec validate --all`
  and `.../openspec validate tune-memory-effectiveness` — must be 0
  failed before any code change. DONE 2026-11-09: `validate --all`
  8 passed, 0 failed (re-validated after the A.2/B.1 build).

## A. Tests first (mocked LLM, no production change yet)

- [x] A.0 **Prerequisite check — raw pool file.** Confirm whether
  `data/raw/hotpot_dev_distractor_v1.json` exists in the VM. It was
  ABSENT when this change was drafted (2026-11-09) — the extension
  (B.0) needs it. If absent, fetch it from the official HotpotQA
  release (the file `scripts/make_stream.py` was built against),
  verify it against the SHA recorded in the repo's audit/manifest
  docs if one is recorded, otherwise record the SHA of the fetched
  file in the sidecar (B.0). Do NOT commit the raw file. If the raw
  file genuinely cannot be obtained, use the pre-registered fallback
  (B.0 fallback): run N=30 as-is; do NOT invent new questions from
  the frozen debug/dev/test manifests. OUTCOME 2026-11-09 (third
  fetch failure overall): both CMU mirror variants returned curl
  (52) Empty reply; `data/raw/` still does not exist. B.0 NOT run,
  no Parquet reconstruction attempted, no questions invented. The
  pre-registered N=30 fallback stands; the 30-row sidecar is
  `data/manifests/stream_clusters.json` (5 clusters x 6, positions
  0–5).
- [x] A.1 In `tests/test_erag.py` (mocked LLM), add tests that a
  `run_erag` row carries `mem_store_size` (int, post-row store size)
  and `mem_texts` (list of texts of the passages memory returned for
  that question; `[]` when memory is off or nothing fired). Mock a
  memory object with a known item list and known `read` return; the
  test asserts the row fields match the mock, and that with
  `memory=None` both fields are `0` / `[]`. No production change yet
  (B.1 implements the fields). DONE 2026-11-09 by the parent:
  deferred from the subagent build to avoid a `tests/test_erag.py`
  collision with the step-5 build in flight; added after the step-5
  commit 5c01ede. Two tests (`test_run_erag_row_carries_mem_fields`,
  `test_run_erag_row_mem_fields_off`), proven genuine by stashing
  B.1 (both fail with KeyError) and restoring it (both pass).
- [x] A.2 Extend `scripts/eval_memory.py` with a `--position` section
  (new function + CLI flags taking the three run files and the
  sidecar path; keep the existing E5 behavior unchanged when the
  flags are absent). It reports, per arm: EM, F1, mean `llm_calls`/Q,
  mean LIVE calls/Q (`llm_calls − cache_hits`), mean retrievals/Q,
  mean `cache_hits`/Q, fire rate (rows with `mem_used > 0`), mean
  `mem_store_size` by position band, `mem_events` (overrides); the
  position split (early 0–1, mid 2–3, late 4–5) with the paired
  mem-vs-nomem difference WITHIN each band; the fired-row paired
  difference (mem-arm minus nomem-arm EM/calls on the same
  questions, restricted to rows where the mem arm fired); and the
  planted override rate among retrieved beliefs plus the
  false-claim-in-answer check (design.md Gate 3). Verify the
  measurement path BEFORE any live run (design.md correction note):
  the fields the section reads must be fields the runner actually
  writes — `mem_used`, `mem_events`, `llm_calls`, `cache_hits`,
  `retrievals`, `em`, `f1`, `answer`, `gold` are already written
  (verified against `results/stream_mem.jsonl`); `mem_store_size`
  and `mem_texts` come from B.1. Verification: run the section on
  the E5 files
  (`results/stream_nomem.jsonl`, `results/stream_mem.jsonl`,
  `results/stream_planted.jsonl`, sidecar built from the original 5
  clusters) and it MUST reproduce: nomem EM 0.4000, F1 0.4828,
  14.30 calls/Q, 2.50 retrievals/Q, 0.27 cache_hits/Q; mem identical
  except cache_hits/Q 14.30 and fired rows idx 20 (cluster 3, pos 2)
  and 29 (cluster 4, pos 5); position splits early EM 0.5000 /
  14.20 calls, mid EM 0.4000 / 13.70 calls, late EM 0.3000 /
  15.00 calls; planted override 1 unique belief (Becker) / 5
  planted, 1/1 retrieved. If it does not reproduce these numbers,
  the section is wrong — fix it before any live run. DONE
  2026-11-09: `--position` section implemented + 11 tests in
  `tests/test_eval_memory_position.py` (failed before, pass after);
  the parent re-ran it on the E5 files and reproduced every number
  exactly (nomem EM 0.4000, F1 0.4828, 14.30 calls/Q, 2.50
  retrievals/Q, 0.27 cache_hits/Q; fired idx 20/29; position splits
  early 0.5000/14.20, mid 0.4000/13.70, late 0.3000/15.00; planted
  1/5, 1/1 retrieved, 0 violations; tripwire fires correctly on
  the replayed mem/planted arms). Two bugs fixed during the build
  (false-claim check excluded target-entity answers; `__main__`
  guard moved to end of file). `mem_store_size` reports "not
  recorded" on E5 files, never zero.

## B. Implementation

- [ ] B.0 **Extend the stream manifest 30 → 60.** Write
  `scripts/make_stream_extended.py` (new file; do NOT edit
  `scripts/make_stream.py` or the first 30 rows). It loads the
  existing `data/manifests/stream.jsonl`, verifies the first 30 rows
  are unchanged (assert on ids in order), then appends 5 new
  entity-sharing clusters × 6 questions built by the identical
  construction as `make_stream.py`: each cluster is a title list of
  named entities, 6 distinct questions per cluster selected in
  raw-file order, no id overlap with `debug`/`dev`/`test`/`stream`,
  no duplicate questions. It writes the extended manifest to
  `data/manifests/stream.jsonl` (60 rows) and the sidecar
  `data/manifests/stream_clusters.json`: `{qid: {cluster,
  cluster_index, position}}` for all 60 rows, plus the 5 new title
  lists and the raw-file SHA. Assertions (fail loudly, do not
  silently truncate): 60 rows total; 10 clusters × 6; first 30 rows
  byte-identical to the pre-extension file (keep a backup at
  `data/manifests/stream.jsonl.orig30` before writing); zero id
  overlap with debug/dev/test; zero duplicate questions. The 5 new
  title lists are chosen by the implementer from entity families
  with ≥6 available questions in the raw pool, and MUST be recorded
  in the sidecar and the commit message — the construction rule is
  pre-registered here, the specific entities are not. **Fallback
  (pre-registered):** if A.0 fails and the raw file cannot be
  obtained, skip B.0, run N=30 as-is, and record in the commit
  message that the extension was not possible; the fire-rate floor
  (design.md Gate 1) governs interpretation at N=30.
- [x] B.1 Add the two measurement-only row fields to `run_erag`'s
  output dict in `src/systems/erag.py` (near the existing
  `"mem_used"` / `"mem_events"` lines, ~367–368):
  `"mem_store_size": len(memory.items) if memory is not None else 0`
  (post-row store size — `memory.write` runs before the dict is
  built, line ~350) and `"mem_texts": [p["text"] for p in
  mem_passages]`. No logic change, no flag, no behavior change when
  memory is off. Covered by the A.1 mocked tests. This closes the E5
  provenance gap (used-belief texts were not recoverable from stored
  rows) and lets the gate distinguish "nothing was written" from
  "beliefs were written but never matched". DONE 2026-11-09: fields
  added at `src/systems/erag.py:372–373`; verified before editing
  that `memory.write` runs before the dict is built and
  `mem_passages` is in scope.
- [x] B.2 Fast suite green after B.0/B.1 (the suite as in steps 1–3:
  cache, config, metrics, erag, retrieval, claims, prompts). The
  known pre-existing failure
  (`test_retry_exhaustion_raises_runtime_error`, expects "after 4
  attempts", code says 6; fails on base too) stays untouched. DONE
  2026-11-09: full suite 111 passed, 1 failed (only the known
  pre-existing retry-test mismatch), verified by the parent.

## C. Stream A/B (live — needs a Groq key, transiently, none saved)

- [ ] C.1 Three runs on the tuned system (post-steps-4/5), in order
  nomem → mem → planted, sequential, detached. The `--set` for each
  MUST be verified against the step-4/5 changes before running
  (carry ALL tuned values forward: `theta_abs` from step 4,
  `max_hops` from step 5, `ground_final_read=true`,
  `max_claims=8`, `unknown_prompt=base`; if step 4 was skipped,
  `theta_abs` stays 0.4; if step 5's cap failed, `max_hops` stays
  2). Single `--set` with all overrides (step-1 lesson: repeated
  `--set` flags overwrite; only the last survives). Fresh cache
  namespace per arm (the E5 lesson — NEVER reuse one namespace
  across arms, and never reuse a dev/test namespace). Output to NEW
  files (do not overwrite `results/stream_mem.jsonl` /
  `stream_nomem.jsonl` / `stream_planted.jsonl` or any dev/test
  file). Prepared commands (verify against `run_experiment.py` and
  the step-4/5 changes before running; needs a Groq key transiently,
  none saved; also set `HF_HUB_DISABLE_XET=1`,
  `NO_PROXY=localhost,127.0.0.1`,
  `no_proxy=localhost,127.0.0.1`):
  - nomem: `.venv/bin/python scripts/run_experiment.py --config configs/base.yaml configs/erag_trueadaptive.yaml --set retrieval.retriever_type=bm25 data.split=stream run.cache_namespace=stream_tuned_nomem_v1 run.name=stream_tuned_nomem_v1 erag.ground_final_read=true erag.max_claims=8 [plus step-4/5 tuned values]`
  - mem: same, with `run.cache_namespace=stream_tuned_mem_v1 run.name=stream_tuned_mem_v1 memory.enabled=true`
  - planted: same as mem, with `run.cache_namespace=stream_tuned_planted_v1 run.name=stream_tuned_planted_v1 memory.enabled=true memory.plant=data/manifests/planted.json`
  Then analyze with: `.venv/bin/python scripts/eval_memory.py --position --nomem results/stream_tuned_nomem_v1.jsonl --mem results/stream_tuned_mem_v1.jsonl --planted results/stream_tuned_planted_v1.jsonl --clusters data/manifests/stream_clusters.json` (flag names per the A.2 implementation; adjust the command to match what A.2 actually built).
- [ ] C.2 Check the tripwire FIRST, before reading any EM number:
  mean live calls/Q (`llm_calls − cache_hits`) per arm must be
  close to mean `llm_calls`/Q (i.e. `cache_hits`/Q near 0). If any
  arm's live calls/Q is ~0, that arm replayed and its results are
  discarded, not analyzed — find the namespace error, fix it, and
  re-run that arm in a fresh namespace. Record per-arm
  `cache_hits`/Q in the commit message. Then compare EM, calls/Q,
  live calls/Q, retrievals/Q, fire rate, position splits, fired-row
  paired difference, store growth, and override rate. Deduplicate
  rows by id keeping the LAST row; expect N=60 (or N=30 on the B.0
  fallback), 0 failed rows per arm.

## D. Gate (pre-registered, design.md)

- [ ] D.1 Memory enters the frozen Test-400 system ONLY if ALL of:
  (1) the mem arm fires on ≥5 of 60 questions (≥5 of 30 on the B.0
  fallback); (2) ΔEM (mem − nomem) > 0, OR Δcalls/Q < 0 with
  ΔEM ≥ −0.02 — AND the fired-row paired difference does not
  contradict the full-stream direction; (3) the override test
  passes (every retrieved planted belief overridden; no planted-arm
  final answer equals a planted false claim; if zero planted beliefs
  are retrieved, the override half is unresolved and the gate does
  not pass). If (1) fails, the verdict is "instrument too weak"
  (design.md) — memory stays OFF, no re-run. If (1) and (3) pass
  but (2) fails, the verdict is a clean null — memory stays OFF, H5
  stays NOT SUPPORTED, paper reports mechanism-verified /
  effectiveness-not-demonstrated. If the gate passes, record
  `memory.enabled: true` (thresholds unchanged) in the frozen-config
  note (the tuned config file itself is written at the end of Phase
  1, not here). Do NOT run Test-400 for this step.
- [ ] D.2 Commit the change (tests + analyzer + extension script +
  sidecar + extended manifest + three stream result files) on
  `trueadaptive`, with the gate verdict and per-arm numbers
  (including `cache_hits`/Q and the firing count) in the commit
  message. Do NOT commit `results/cache.sqlite` or
  `results/nli_memo.pkl`.

## E. Archive + next step

- [ ] E.1 Archive the change with `openspec archive
  tune-memory-effectiveness -y` (always `-y` in this environment —
  without it the command blocks on an interactive prompt with no
  TTY). Verify the archived change is under
  `openspec/changes/archive/2026-11-09-tune-memory-effectiveness/`
  and the spec merged to `openspec/specs/memory-effectiveness/`.
- [ ] E.2 Re-validate: `openspec validate --all` must be 0 failed.
  Update the master plan (§3.6 outcome + §2.1 status + §9 decision
  3b) and `docs/hypotheses-current-status.md` (H5 verdict) with the
  result. After step 6 closes: freeze
  `configs/erag_trueadaptive_tuned.yaml` (incl. the memory on/off
  decision from this step), then Phase 2 Test-400 confirmation.
