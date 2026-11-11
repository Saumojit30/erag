"""System C: E-RAG adaptive epistemic retrieval system with belief graphs, EIG query selection, Fast Path, and safe abstention."""

from typing import Any, Dict, List, Optional
from src.epistemic.belief_graph import BeliefGraph
from src.epistemic.claims import extract_claims, extract_claims_second_pass, merge_claims
from src.epistemic.confidence import self_consistency, sequential_consistency
from src.epistemic.continuation_policy import decide_policy, hop0_features, load_policy
from src.eval.metrics import normalize_answer
from src.llm.client import Tracker
from src.llm.prompts import answer_messages, contested_answer_messages, grounded_answer_messages

QUERY_SYSTEM = (
    "Write {n} short, different search queries that would find evidence confirming or "
    "refuting the claim. One query per line, no numbering."
)


def propose_queries(llm: Any, claim_text: str, tracker: Tracker, n: int = 3) -> List[str]:
    """Generate candidate follow-up search queries targeting a specific claim."""
    msgs = [
        {"role": "system", "content": QUERY_SYSTEM.format(n=n)},
        {"role": "user", "content": f"Claim: {claim_text}"},
    ]
    raw = llm.chat(msgs, tracker, max_tokens=200, temperature=0.0)
    lines = [
        l.strip(" -*0123456789.").strip()
        for l in raw.splitlines()
        if l.strip(" -*0123456789.").strip()
    ]
    return lines[:n]


def _run_sc(
    llm: Any,
    q: str,
    pool: List[Dict[str, Any]],
    draft: str,
    tracker: Tracker,
    cfg: Dict[str, Any],
    k: int,
) -> Dict[str, Any]:
    """Run self-consistency in the configured mode (TrueAdaptive v1).

    ``erag.sc_mode: sequential`` samples one at a time with entropy
    stopping (cap M=3); anything else uses the fixed reference sampler.
    Both return the same dict shape, so callers are unaffected.
    """
    e = cfg.get("erag", {})
    if e.get("sc_mode", "fixed") == "sequential":
        return sequential_consistency(
            llm,
            q,
            pool,
            draft,
            tracker,
            k=min(int(k), 3),
            temperature=e.get("sc_temperature", 0.7),
        )
    return self_consistency(
        llm,
        q,
        pool,
        draft,
        tracker,
        k=int(k),
        temperature=e.get("sc_temperature", 0.7),
    )


def conf_value(sc: Dict[str, Any], cfg: Dict[str, Any]) -> float:
    """Extract selected confidence definition from self-consistency results."""
    conf_def = cfg.get("erag", {}).get("confidence_def", "majority")
    if conf_def == "majority":
        return float(sc.get("conf_majority", 1.0))
    return float(sc.get("conf_draft_agreement", 1.0))


def build_graph(
    claims: List[Dict[str, Any]],
    passages: List[Dict[str, Any]],
    nli: Any,
    c0: float,
    cfg: Dict[str, Any],
    ablate: set,
) -> BeliefGraph:
    """Build and update the epistemic belief graph from extracted claims and evidence passages."""
    e, n = cfg.get("erag", {}), cfg.get("nli", {})
    w_s = e.get("w_s", 1.0)
    w_c = e.get("w_c", 2.0)
    propagate = "no_prop" not in ablate
    pre_filter = n.get("pre_filter", False)

    g = BeliefGraph(w_s=w_s, w_c=w_c, propagate=propagate)
    for c in claims:
        if "no_nli" in ablate or nli is None:
            ev = {"status": "unresolved", "conflict": False, "sup": [], "con": []}
        else:
            theta_s = n.get("theta_s", 0.5)
            theta_c = n.get("theta_c", 0.5)
            ev = nli.verify(c["text"], passages, theta_s=theta_s, theta_c=theta_c, pre_filter=pre_filter)
        g.add(c["text"], c["answer_bearing"], c["depends_on"], c0, ev, source=c.get("source", "draft"))
    return g.update()


def find_contested(claims: List[Dict[str, Any]], draft: str):
    """Detect a contested final graph (Phase 2.5 H12, pure function).

    `claims` are belief-graph claim dicts (the trace JSON shape: `text`,
    `status`, `source`, `eff`). Contested iff a supported draft-sourced
    claim contains the normalized draft answer AND a supported
    question-sourced claim does not. Returns `(agreeing, disagreeing)`,
    each sorted by `eff` descending, or `None` when not contested.

    Normalization is the repo `normalize_answer` (lowercase, punctuation
    and article removal); the stored-data check used the analyzer's
    `[^a-z0-9 ]` collapse, which agrees on this comparison up to article
    handling. Draft "unknown"/empty is never contested.
    """
    draft_norm = normalize_answer(draft)
    if draft_norm in ("unknown", ""):
        return None
    agreeing = [
        c for c in claims
        if c.get("status") == "supported" and c.get("source", "draft") == "draft"
        and draft_norm in normalize_answer(c.get("text", ""))
    ]
    disagreeing = [
        c for c in claims
        if c.get("status") == "supported" and c.get("source") == "question"
        and draft_norm not in normalize_answer(c.get("text", ""))
    ]
    if not agreeing or not disagreeing:
        return None
    agreeing = sorted(agreeing, key=lambda c: -float(c.get("eff", 0.0)))
    disagreeing = sorted(disagreeing, key=lambda c: -float(c.get("eff", 0.0)))
    return agreeing, disagreeing


def targeted_retrieve(
    llm: Any,
    retriever: Any,
    claim: Any,
    pool: List[Dict[str, Any]],
    k: int,
    ablate: set,
    tracker: Tracker,
    eig_strategy: str = "llm",
    saturation_precheck: bool = False,
) -> List[Dict[str, Any]]:
    """Select next evidence using EIG-inspired uncertainty reduction x pool novelty."""
    seen = {p["title"] for p in pool}
    if "no_eig" in ablate or eig_strategy == "direct":
        queries = [claim.text]
    else:
        proposed = propose_queries(llm, claim.text, tracker, n=3)
        queries = proposed if proposed else [claim.text]

    best, best_score = [], -1.0
    for qy in queries:
        res = retriever.search(qy, k=k)
        tracker.probe_searches += 1
        novelty = sum(1 for r in res if r["title"] not in seen) / max(len(res), 1)
        score = (1.0 - claim.eff) * novelty
        if score > best_score:
            best, best_score = res, score

    tracker.retrievals += 1
    new_passages = [r for r in best if r["title"] not in seen]
    return new_passages


def run_erag(
    item: Dict[str, Any],
    retriever: Any,
    llm: Any,
    nli: Any,
    cfg: Dict[str, Any],
    tracker: Tracker,
    memory: Any = None,
) -> Dict[str, Any]:
    """Execute complete 12-step E-RAG adaptive epistemic retrieval loop."""
    e = cfg.get("erag", {})
    k = cfg["retrieval"].get("k", 3)
    q = item["question"]
    ablate = set(e.get("ablate", []) or cfg.get("ablate", []))
    active = e.get("mode", "active") == "active"
    use_status = "no_nli" not in ablate

    # Phase 2 Optimization Controls (Defaulting strictly to Reference Baseline)
    claim_strategy = e.get("claim_strategy", "full_reextract") # full_reextract | incremental | single_atomic
    post_hop_resample = e.get("post_hop_resample", "always")    # always | conditional | never
    eig_strategy = e.get("eig_strategy", "llm")                 # llm | direct
    saturation_precheck = e.get("saturation_precheck", False)

    # Step 1: Initial retrieval
    pool = retriever.search(q, k=k)
    tracker.retrievals += 1

    mem_passages, mem_events = [], []
    if memory is not None:
        mem_passages, mem_events = memory.read(q, pool, nli, cfg)

    hop, c0, trace, seen_contra = 0, None, [], False
    # TrueAdaptive v1: c0_source records HOW c0 was obtained, because the
    # gated Fast Path changes its meaning (see below). "sc" = from
    # self-consistency; "fast_path_min_eff" = SC skipped, c0 = graph min_eff;
    # "no_conf" = ablation (c0 = 1.0).
    c0_source = None
    sc_skipped_fast_path = False
    initial_draft = None
    prev_claims = None
    # Phase 2.5 H13: second-pass bookkeeping (hop 0 only, flag-gated).
    second_pass_added = 0
    second_extraction_ran = False

    # Learned continuation policy (step 7, B.1): when erag.continuation_policy
    # names an artifact file, the policy replaces the fast-path + first
    # gap-continuation decision at hop 0. Absent = today's static behavior
    # exactly. A missing or malformed artifact raises here (fail loudly,
    # never silently fall back to static behavior). Loaded once per call.
    policy = None
    policy_path = e.get("continuation_policy")
    if policy_path:
        policy = load_policy(policy_path)
    policy_decision = None
    policy_p = None

    while True:
        # Step 2: Generation of draft answer (step 3: reader prompt variant
        # from erag.unknown_prompt, default "base").
        draft = llm.chat(answer_messages(q, pool, variant=e.get("unknown_prompt", "base")), tracker, temperature=0.0)
        if hop == 0:
            initial_draft = draft

        # Step 3: Self-consistency confidence estimation.
        # TrueAdaptive v1 gate (erag.gate_sc_behind_fast_path, active mode,
        # hop 0 only): SC is DEFERRED until after the Fast-Path check, so a
        # question whose claims are already supported costs draft + claims
        # only. The provisional graph below is built with c0 = 1.0 (the
        # same prior the no_conf ablation uses), so its min_eff reflects
        # evidence strength alone; if SC runs, the graph is rebuilt with
        # the real c0 and the provisional graph is never used for retrieval.
        gate_sc = (
            e.get("gate_sc_behind_fast_path", False)
            and active
            and hop == 0
            and c0 is None
            and "no_conf" not in ablate
        )
        deferred_sc = False
        if c0 is None:
            if "no_conf" in ablate:
                c0 = 1.0
                c0_source = "no_conf"
            elif gate_sc:
                deferred_sc = True
            else:
                sc = _run_sc(llm, q, pool, draft, tracker, cfg, k=e.get("sc_samples", 5))
                c0 = conf_value(sc, cfg)
                c0_source = "sc"

        # Step 4, 5, 6, 7: Claim decomposition, NLI verification, belief graph update & propagation
        if claim_strategy == "single_atomic":
            claims = [{
                "text": f'The answer to "{q}" is {draft}.',
                "answer_bearing": True,
                "depends_on": [],
                "fallback": False,
            }]
        elif claim_strategy == "incremental" and hop > 0 and normalize_answer(draft) == normalize_answer(initial_draft) and prev_claims:
            claims = prev_claims
        else:
            claims = extract_claims(llm, q, draft, pool, tracker, max_claims=e.get("max_claims", 5))
            prev_claims = claims

        # Phase 2.5 H13: second extraction pass at hop 0 only. The first
        # pass skips the gold sentence on 33/400 tuned Test-400 rows (the
        # max_claims cap binds on 2/33, parsing never fails), so the fix
        # is coverage, not room: given the claims already extracted, list
        # additional claims the first pass missed. At most +1 LLM call.
        if (hop == 0 and e.get("second_extraction", False)
                and claim_strategy != "single_atomic"):
            extra = extract_claims_second_pass(
                llm, q, draft, pool, claims, tracker,
                max_claims=e.get("max_claims", 5),
            )
            merged = merge_claims(claims, extra)
            second_pass_added = len(merged) - len(claims)
            second_extraction_ran = True
            claims = merged
            prev_claims = claims

        # c0 is None only when SC was deferred by the Fast-Path gate; the
        # provisional graph then uses the 1.0 prior (see Step 3).
        graph = build_graph(claims, pool + mem_passages, nli, c0 if c0 is not None else 1.0, cfg, ablate)
        gaps = graph.gaps(e.get("theta_gap", 0.6), use_status=use_status)
        seen_contra |= any(c.status == "contradicted" for c in graph.claims)

        trace.append({
            "hop": hop,
            "answer": draft,
            "pool": [p["title"] for p in pool],
            "graph": graph.to_json(),
        })

        # Check stopping criteria: observational mode, no_adaptive ablation, or max_hops exhausted
        if not active or "no_adaptive" in ablate or hop >= e.get("max_hops", 2):
            if deferred_sc:
                # SC was deferred and we are stopping without a Fast-Path
                # check (e.g. max_hops == 0): resolve c0 the same way the
                # Fast-Path check would, so c0 is never None on return.
                c0 = graph.min_eff()
                c0_source = "fast_path_min_eff"
                sc_skipped_fast_path = True
            break

        # Step 8 & 9: resolve a deferred SC call, then gap selection / Fast Path.
        if deferred_sc:
            if not gaps and graph.min_eff() >= e.get("theta_fast", 0.8):
                # Fast Path: SC is skipped entirely. c0 falls back to the
                # graph's own min_eff — recorded explicitly in the result.
                c0 = graph.min_eff()
                c0_source = "fast_path_min_eff"
                sc_skipped_fast_path = True
                if policy is None:
                    break
                # Policy active: do NOT break — the policy replaces the
                # Fast-Path decision at hop 0 (it may CONTINUE a row the
                # static system would stop on). Fall through to the policy
                # branch below with c0/c0_source final.
            else:
                sc = _run_sc(llm, q, pool, draft, tracker, cfg, k=e.get("sc_samples", 5))
                c0 = conf_value(sc, cfg)
                c0_source = "sc"
                graph = build_graph(claims, pool + mem_passages, nli, c0, cfg, ablate)
                gaps = graph.gaps(e.get("theta_gap", 0.6), use_status=use_status)
                trace[-1]["graph"] = graph.to_json()

        # Step 8 & 9: Gap selection and No-Gap Fast Path — or, at hop 0,
        # the learned continuation policy (step 7, B.1), which REPLACES the
        # fast-path + first gap-continuation decision. EIG gap selection,
        # SC, abstention, and the max_hops ceiling are unchanged, and hop-1+
        # continuation stays static.
        if hop == 0 and policy is not None:
            features = hop0_features(
                c0=c0,
                c0_source=c0_source,
                sc_skipped=sc_skipped_fast_path,
                graph_claims=graph.to_json(),
                pool_titles=[p["title"] for p in pool],
                # supporting_facts come from the manifest item in eval runs;
                # absent in production (no manifest) -> hop0_recall 0.0.
                supporting_facts=item.get("supporting_facts"),
                question_type=item.get("type"),
                hop0_draft=draft,
            )
            policy_decision, policy_p = decide_policy(policy, features)
            if policy_decision == "stop":
                break
            # CONTINUE: pick the retrieval target.
            # no_conf ablation: the static code always continues with the
            # answer claim as target; the policy decision still governs at
            # hop 0, so CONTINUE keeps that target. (Ablation runs are out
            # of scope for the gate.)
            if "no_conf" in ablate:
                target = graph.answer_claim()
            elif gaps:
                target = graph.weakest(gaps)
            else:
                # Would-be fast-path row (no gaps, min_eff >= theta_fast):
                # weakest claim as target, mirroring the static
                # min_eff < theta_fast fallback branch.
                target = graph.weakest(graph.claims)
        elif "no_conf" in ablate:
            target = graph.answer_claim()
        elif gaps:
            target = graph.weakest(gaps)
        elif "no_fast" in ablate or graph.min_eff() < e.get("theta_fast", 0.8):
            target = graph.weakest(graph.claims)
        else:
            break  # Fast Path: all claims sufficiently supported

        # Saturation check: if pool has reached capacity, further retrieval cannot expand context
        if saturation_precheck and len(pool) >= e.get("pool_cap", 12):
            break

        # Step 10 & 11: EIG-inspired query selection and adaptive retrieval
        new = targeted_retrieve(
            llm, retriever, target, pool, k, ablate, tracker,
            eig_strategy=eig_strategy, saturation_precheck=saturation_precheck
        )
        if not new:
            break
        pool = (pool + new)[: e.get("pool_cap", 12)]
        hop += 1

    # Tune-reader-grounding (step 1): conditional claim-grounded re-read.
    # The final reader never sees the graph's verified claims; when the draft
    # is "unknown" or disagrees with the answer claim, one extra reader call
    # grounded on supported claims can recover the answer. Behind
    # erag.ground_final_read (default false). The original draft stays in
    # trace[-1]["answer"] when replaced (it was recorded there during the hop).
    # No re-read when there is no answer claim or no supported claim to
    # ground on. An empty draft counts as "unknown".
    # `loop_draft` is the draft the loop produced: the post-hop resample
    # decision below must compare against it, not a re-read replacement.
    loop_draft = draft
    grounded_reread = False
    reread_trigger = None
    reread_answer = None
    contested = False
    if e.get("ground_final_read", False):
        answer_claim = graph.answer_claim() if graph.claims else None
        supported = [c for c in graph.claims if c.status == "supported"]
        if answer_claim is not None and supported:
            draft_norm = normalize_answer(draft)
            claim_norm = normalize_answer(answer_claim.text)
            msgs = None
            if draft_norm in ("unknown", ""):
                reread_trigger = "unknown"
            elif draft_norm not in claim_norm:
                reread_trigger = "disagree"
            if reread_trigger is not None:
                grounded = sorted(
                    supported, key=lambda c: (not c.answer_bearing, -c.eff)
                )
                msgs = grounded_answer_messages(
                    q, grounded[: e.get("max_claims", 5)], pool
                )
            elif e.get("contested_resolution", False):
                # Phase 2.5 H12: the draft agrees with its own claims but
                # the context offers a competing answer — resolve the
                # contest with a re-read that states the disagreement.
                found = find_contested(graph.to_json(), draft)
                if found is not None:
                    agreeing, disagreeing = found
                    cap = int(e.get("max_claims", 5))
                    agreeing = agreeing[:cap]
                    disagreeing = disagreeing[: max(0, cap - len(agreeing))]
                    reread_trigger = "contested"
                    contested = True
                    msgs = contested_answer_messages(
                        q, agreeing, disagreeing, pool
                    )
            if reread_trigger is not None:
                reread = llm.chat(msgs, tracker, temperature=0.0)
                grounded_reread = True
                reread_answer = reread
                if normalize_answer(reread) not in ("unknown", ""):
                    draft = reread

    final_conf = c0
    if hop > 0:
        if "no_conf" in ablate or post_hop_resample == "never":
            final_conf = 1.0 if "no_conf" in ablate else c0
        elif post_hop_resample == "conditional" and normalize_answer(loop_draft) == normalize_answer(initial_draft):
            # Answer unchanged despite new evidence: retain prior consensus c0
            final_conf = c0
        else:
            k_post = e.get("sc_samples_post_hop") or e.get("sc_samples", 5)
            sc = _run_sc(llm, q, pool, draft, tracker, cfg, k=k_post)
            final_conf = conf_value(sc, cfg)
        graph = build_graph(claims, pool + mem_passages, nli, final_conf, cfg, ablate)

    ans = graph.answer_claim()

    # Step 12: Safe abstention rule: withheld only if answer claim effective confidence is below threshold
    abstain = "no_conf" not in ablate and (ans.eff < e.get("theta_abs", 0.4))
    answer = "unknown" if (active and abstain) else draft

    if memory is not None and active:
        memory.write(graph, c0, seen_contra, cfg)

    out = {
        "answer": answer,
        "draft": draft,
        "abstained": bool(active and abstain),
        "would_abstain": bool(abstain),
        "answer_conf": float(ans.eff),
        "c0": float(c0),
        # TrueAdaptive v1: how c0 was obtained, and whether the Fast-Path
        # gate skipped SC. c0_source is "sc", "fast_path_min_eff"
        # (c0 = graph min_eff, SC skipped), or "no_conf".
        "c0_source": c0_source,
        "sc_skipped_fast_path": bool(sc_skipped_fast_path),
        "pool_titles": [p["title"] for p in pool],
        "hops": hop,
        "trace": trace,
        "mem_used": len(mem_passages),
        "mem_events": mem_events,
        # Tune-memory-effectiveness (step 6, B.1): measurement-only row
        # fields closing the E5 provenance gap (used-belief texts were
        # not recoverable from stored rows). No logic change.
        "mem_store_size": len(memory.items) if memory is not None else 0,
        "mem_texts": [p["text"] for p in mem_passages],
        "claim_fallbacks": sum(1 for c in claims if c.get("fallback", False)),
    }
    # Learned continuation policy (step 7, B.1): record the decision on
    # policy-active rows only; flag-absent rows carry no such fields.
    if policy_decision is not None:
        out["policy_decision"] = policy_decision
        out["policy_p"] = float(policy_p)
    # Tune-reader-grounding (step 1): record the re-read only when the flag
    # is on, so flag-off runs produce byte-identical records to v1.
    if e.get("ground_final_read", False):
        out["grounded_reread"] = grounded_reread
        out["reread_trigger"] = reread_trigger
        out["reread_answer"] = reread_answer
    # Phase 2.5 H12: record whether the graph was contested, only when
    # the flag is on (flag-off runs stay byte-identical to the tuned system).
    if e.get("contested_resolution", False):
        out["contested"] = contested
    # Phase 2.5 H13: record the second pass, only when the flag is on.
    if e.get("second_extraction", False):
        out["second_pass_added"] = second_pass_added
        out["second_extraction"] = second_extraction_ran
    return out

