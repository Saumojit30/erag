"""System C: E-RAG adaptive epistemic retrieval system with belief graphs, EIG query selection, Fast Path, and safe abstention."""

from typing import Any, Dict, List, Optional
from src.epistemic.belief_graph import BeliefGraph
from src.epistemic.claims import extract_claims
from src.epistemic.confidence import self_consistency, sequential_consistency
from src.eval.metrics import normalize_answer
from src.llm.client import Tracker
from src.llm.prompts import answer_messages, grounded_answer_messages

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

    while True:
        # Step 2: Generation of draft answer
        draft = llm.chat(answer_messages(q, pool), tracker, temperature=0.0)
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
                break
            sc = _run_sc(llm, q, pool, draft, tracker, cfg, k=e.get("sc_samples", 5))
            c0 = conf_value(sc, cfg)
            c0_source = "sc"
            graph = build_graph(claims, pool + mem_passages, nli, c0, cfg, ablate)
            gaps = graph.gaps(e.get("theta_gap", 0.6), use_status=use_status)
            trace[-1]["graph"] = graph.to_json()

        # Step 8 & 9: Gap selection and No-Gap Fast Path
        if "no_conf" in ablate:
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
    if e.get("ground_final_read", False):
        answer_claim = graph.answer_claim() if graph.claims else None
        supported = [c for c in graph.claims if c.status == "supported"]
        if answer_claim is not None and supported:
            draft_norm = normalize_answer(draft)
            claim_norm = normalize_answer(answer_claim.text)
            if draft_norm in ("unknown", ""):
                reread_trigger = "unknown"
            elif draft_norm not in claim_norm:
                reread_trigger = "disagree"
            if reread_trigger is not None:
                grounded = sorted(
                    supported, key=lambda c: (not c.answer_bearing, -c.eff)
                )
                reread = llm.chat(
                    grounded_answer_messages(
                        q, grounded[: e.get("max_claims", 5)], pool
                    ),
                    tracker,
                    temperature=0.0,
                )
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
        "claim_fallbacks": sum(1 for c in claims if c.get("fallback", False)),
    }
    # Tune-reader-grounding (step 1): record the re-read only when the flag
    # is on, so flag-off runs produce byte-identical records to v1.
    if e.get("ground_final_read", False):
        out["grounded_reread"] = grounded_reread
        out["reread_trigger"] = reread_trigger
        out["reread_answer"] = reread_answer
    return out

