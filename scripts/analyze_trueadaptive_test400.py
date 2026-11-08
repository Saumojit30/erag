"""Error analysis for TrueAdaptive v1 Test-400 BM25 (and Dev-100 BM25 check).

Read-only: recomputes breakdowns from stored result files, no LLM calls.
Usage: .venv/bin/python scripts/analyze_trueadaptive_test400.py [--reread] [--ta-dev PATH]

--reread prints section 10, the claim-grounded re-read summary (tuning step 1):
trigger rate, re-read EM, and rows fixed/broken by the re-read, for the TA dev
file and the TA test file. --ta-dev PATH points the dev analysis at a different
file (the tuned dev A/B output). Without flags the script behaves exactly as
before; on a v1 file (no `grounded_reread` field) section 10 reports 0 triggers.

Method notes (read before citing any number here):
- Rows are deduped by id keeping the LAST row: the resume retried 1 failed
  Test-400 question, leaving a stale failed row in the file (401 lines -> 400).
- "unknown" and "abstained" are DIFFERENT fields. `abstained` = the system
  withheld the answer because ans.eff < theta_abs (0.4). `unknown` = the
  final answer text is "unknown", which also happens when the reader model
  itself says "unknown" (40 rows) despite high confidence. Conflating them
  corrupts the abstention analysis; this script keeps them separate.
- EM here uses the repo's exact_match (src/eval/metrics.py), not a local
  normalizer, so the numbers match the reported EM exactly.
- The theta_abs sweep is a counterfactual on STORED rows (draft + answer_conf
  are stored, so no re-run is needed). Selection must use the DEV sweep only;
  the TEST sweep is a diagnostic and must never be used to pick a threshold.
"""

import argparse
import json
import re
import sys
from statistics import mean

sys.path.insert(0, ".")
from src.eval.metrics import exact_match

REPO = "results/trueadaptive/erag_trueadaptive_test_bm25.jsonl"
IRCO = "results/ircot_test_bm25.jsonl"
DEV = "results/trueadaptive/erag_trueadaptive_bm25_dev.jsonl"


def load(path):
    rows = [json.loads(line) for line in open(path) if line.strip()]
    seen = {}
    for r in rows:
        seen[r["id"]] = r
    return list(seen.values())


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


def gold_in_claims(r):
    g = norm(r["gold"])
    if not g:
        return False
    for hop in (r.get("trace") or []):
        for c in hop.get("graph") or []:
            if g in norm(c.get("text", "")):
                return True
    return False


def section(title):
    print(f"\n=== {title} ===")


def reread_section(label, rows):
    """Section 10 (tuning step 1): what the claim-grounded re-read did.

    Triggered rows carry grounded_reread=True. The original (pre-re-read)
    draft is trace[-1]["answer"] — the loop's final draft, recorded there
    during the hop; the post-re-read draft is the record's "draft" field.
    Comparing their repo-EM isolates the re-read from the abstention rule,
    which can still withhold a fixed answer (reported separately below).
    """
    ok = [r for r in rows if not r.get("failed", False)]
    trig = [r for r in ok if r.get("grounded_reread")]
    section(f"10. Claim-grounded re-read ({label})")
    if not trig:
        print(f"no re-read rows (0/{len(ok)} triggered) — v1 file or flag off")
        return
    reasons = {}
    for r in trig:
        reasons[r.get("reread_trigger")] = reasons.get(r.get("reread_trigger"), 0) + 1
    print(f"triggered: {len(trig)}/{len(ok)} ({len(trig) / len(ok):.1%}) by reason: {reasons}")
    print(f"  re-read answer EM (repo exact_match on reread_answer): "
          f"{mean(1.0 if exact_match(r.get('reread_answer', ''), r['gold']) else 0.0 for r in trig):.4f}")
    orig_em = [1.0 if exact_match((r.get("trace") or [{}])[-1].get("answer", ""), r["gold"]) else 0.0 for r in trig]
    final_em = [1.0 if exact_match(r.get("draft", ""), r["gold"]) else 0.0 for r in trig]
    fixed = sum(1 for o, f in zip(orig_em, final_em) if o == 0 and f == 1)
    broke = sum(1 for o, f in zip(orig_em, final_em) if o == 1 and f == 0)
    print(f"  draft EM on triggered rows: original {mean(orig_em):.4f} -> after re-read {mean(final_em):.4f}; "
          f"fixed {fixed}, broke {broke} (net {fixed - broke:+d})")
    fixed_rows = [r for r, o, f in zip(trig, orig_em, final_em) if o == 0 and f == 1]
    print(f"  of the {fixed} fixed rows, {sum(1 for r in fixed_rows if r['em'] == 1)} ended correct "
          f"in the final answer (em==1); {sum(1 for r in fixed_rows if r.get('abstained'))} "
          f"were withheld by abstention")
    print(f"  mean calls on triggered rows: {mean(r['llm_calls'] for r in trig):.2f} "
          f"(+1 each vs the same question without the re-read)")


def main():
    ap = argparse.ArgumentParser(description="TrueAdaptive error analysis")
    ap.add_argument("--reread", action="store_true",
                    help="print section 10, the claim-grounded re-read summary")
    ap.add_argument("--ta-dev", default=DEV,
                    help="dev results file (default: %(default)s)")
    args = ap.parse_args()

    ta = load(REPO)
    ir = load(IRCO)
    dev = load(args.ta_dev)
    ir_by_id = {r["id"]: r for r in ir}
    print(f"TA Test-400 N={len(ta)}  IRCoT N={len(ir)}  TA Dev-100 N={len(dev)}")

    section("1. Overall (deduped)")
    for name, rows in [("TA test", ta), ("IR test", ir), ("TA dev", dev)]:
        ok = [r for r in rows if not r.get("failed", False)]
        ans = [r for r in ok if not r.get("unknown", False)]
        print(f"{name}: EM={mean(r['em'] for r in ok):.4f} F1={mean(r['f1'] for r in ok):.4f} "
              f"calls={mean(r['llm_calls'] for r in ok):.2f} coverage={len(ans)/len(rows):.3f} "
              f"recall={mean(r['recall'] for r in ok if r.get('recall') is not None):.4f}")

    section("2. Error budget (400 questions)")
    right = [r for r in ta if r["em"] == 1]
    wrong = [r for r in ta if r["em"] == 0 and not r.get("unknown")]
    sys_ab = [r for r in ta if r.get("abstained")]
    mod_unk = [r for r in ta if r.get("unknown") and not r.get("abstained")]
    print(f"right: {len(right)}  wrong (answered): {len(wrong)}  "
          f"system-abstained: {len(sys_ab)}  model-said-unknown: {len(mod_unk)} "
          f"(sums to {len(right) + len(wrong) + len(sys_ab) + len(mod_unk)})")

    section("3. The two unknown populations (do not conflate)")
    print(f"system-abstained: {len(sys_ab)} rows, answer_conf median="
          f"{sorted(r.get('answer_conf', 0) for r in sys_ab)[len(sys_ab) // 2]:.3f} "
          f"(max {max(r.get('answer_conf', 0) for r in sys_ab):.3f}, consistent with theta_abs=0.4)")
    print(f"  draft correct (repo EM): {sum(1 for r in sys_ab if exact_match(r.get('draft', ''), r['gold']))}/{len(sys_ab)}")
    print(f"  recall==1.0: {sum(1 for r in sys_ab if r.get('recall') == 1.0)}")
    print(f"  by hops: { {h: sum(1 for r in sys_ab if r['hops'] == h) for h in sorted(set(r['hops'] for r in sys_ab))} }")
    print(f"model-said-unknown: {len(mod_unk)} rows (draft literally 'unknown'), "
          f"answer_conf median={sorted(r.get('answer_conf', 0) for r in mod_unk)[len(mod_unk) // 2]:.3f}, "
          f"c0 median={sorted(r.get('c0', 0) for r in mod_unk)[len(mod_unk) // 2]:.3f}")
    print(f"  recall==1.0: {sum(1 for r in mod_unk if r.get('recall') == 1.0)}; "
          f"mean calls {mean(r['llm_calls'] for r in mod_unk):.2f} (full budget spent, then 'unknown')")
    print(f"  some hop produced a real answer: "
          f"{sum(1 for r in mod_unk if any((h.get('answer') or '').strip().lower() != 'unknown' for h in (r.get('trace') or [])))}/{len(mod_unk)} "
          f"(reader refuses from hop 0; hops do not overwrite a good answer)")

    section("4. theta_abs sweep (counterfactual on stored rows)")
    print("System-abstained rows with answer_conf >= t answer with their draft; "
          "model-unknown rows stay unknown; answered rows keep their answer.")
    for label, rows in [("DEV (selection set)", dev), ("TEST (diagnostic only)", ta)]:
        ok = [r for r in rows if not r.get("failed", False)]
        print(f"{label} (N={len(ok)}, current EM={mean(r['em'] for r in ok):.4f}):")
        for t in [0.0, 0.1, 0.2, 0.25, 0.3, 0.35, 0.4]:
            ems, cov = [], 0
            for r in ok:
                if r.get("abstained"):
                    if r.get("answer_conf", 0) >= t:
                        ems.append(1.0 if exact_match(r.get("draft", ""), r["gold"]) else 0.0)
                        cov += 1
                    else:
                        ems.append(0.0)
                else:
                    ems.append(float(r["em"]))
                    cov += 0 if r.get("unknown") else 1
            print(f"  t={t:.2f}: EM={mean(ems):.4f} coverage={cov / len(ok):.3f}")

    section("5. Wrong answers — retrieval or reasoning?")
    print(f"wrong (answered): {len(wrong)}")
    rec_full = [r for r in wrong if r.get("recall") == 1.0]
    rec_part = [r for r in wrong if r.get("recall") is not None and r.get("recall") < 1.0]
    print(f"  recall==1.0 (evidence present, reasoning failed): {len(rec_full)}/{len(wrong)}")
    print(f"  recall<1.0 (retrieval missed gold): {len(rec_part)}")
    hit = sum(1 for r in rec_full if gold_in_claims(r))
    print(f"  of the {len(rec_full)} full-recall wrong: gold in some trace claim: {hit} "
          f"(reader/graph bottleneck); gold NEVER a claim: {len(rec_full) - hit} (claim-extraction bottleneck)")
    print(f"  control — correct rows with gold in claims: "
          f"{sum(1 for r in right if gold_in_claims(r))}/{len(right)}")
    hop0_em = mean(1.0 if exact_match((r.get("trace") or [{}])[0].get("answer", ""), r["gold"]) else 0.0
                   for r in ta if not r.get("failed", False))
    final_em = mean(r["em"] for r in ta if not r.get("failed", False))
    fixed = sum(1 for r in ta if not exact_match((r.get("trace") or [{}])[0].get("answer", ""), r["gold"]) and r["em"] == 1)
    broke = sum(1 for r in ta if exact_match((r.get("trace") or [{}])[0].get("answer", ""), r["gold"]) and r["em"] == 0)
    print(f"  hop-0 draft EM: {hop0_em:.4f} vs final EM: {final_em:.4f}; "
          f"hops fixed {fixed}, broke {broke} (net {fixed - broke:+d})")

    section("6. Call tail (calls >= 7)")
    tail = [r for r in ta if r["llm_calls"] >= 7]
    print(f"rows >=7 calls: {len(tail)} ({len(tail) / len(ta):.0%}), "
          f"{sum(r['llm_calls'] for r in tail)} of {sum(r['llm_calls'] for r in ta)} calls "
          f"({sum(r['llm_calls'] for r in tail) / sum(r['llm_calls'] for r in ta):.0%} of all calls)")
    print(f"  tail by hops: { {h: sum(1 for r in tail if r['hops'] == h) for h in sorted(set(r['hops'] for r in tail))} }")
    print(f"  tail EM: {mean(r['em'] for r in tail):.4f}; tail abstained/model-unknown: "
          f"{sum(1 for r in tail if r.get('unknown'))}")
    print(f"  mean calls by hops: { {h: round(mean(r['llm_calls'] for r in ta if r['hops'] == h), 2) for h in sorted(set(r['hops'] for r in ta))} }")

    section("7. Fast-path SC skips")
    skip = [r for r in ta if r.get("sc_skipped_fast_path")]
    noskip = [r for r in ta if not r.get("sc_skipped_fast_path")]
    print(f"skipped SC: {len(skip)} rows, mean calls {mean(r['llm_calls'] for r in skip):.2f}, "
          f"EM {mean(r['em'] for r in skip):.4f}, unknown {sum(1 for r in skip if r.get('unknown'))}")
    print(f"not skipped: {len(noskip)} rows, mean calls {mean(r['llm_calls'] for r in noskip):.2f}, "
          f"EM {mean(r['em'] for r in noskip):.4f}, unknown {sum(1 for r in noskip if r.get('unknown'))}")

    section("8. TA vs IRCoT win/loss pairs")
    wins = [r for r in ta if r["id"] in ir_by_id and r["em"] == 1 and ir_by_id[r["id"]]["em"] == 0]
    loss = [r for r in ta if r["id"] in ir_by_id and r["em"] == 0 and ir_by_id[r["id"]]["em"] == 1]
    print(f"TA-only correct: {len(wins)}; IR-only correct: {len(loss)}")
    print(f"  wins: mean recall {mean(r['recall'] for r in wins if r.get('recall') is not None):.3f}, "
          f"mean calls {mean(r['llm_calls'] for r in wins):.2f}")
    print(f"  losses: mean recall {mean(r['recall'] for r in loss if r.get('recall') is not None):.3f}, "
          f"mean calls {mean(r['llm_calls'] for r in loss):.2f}")
    print(f"  IRCoT abstained/model-unknown: {sum(1 for r in ir if r.get('unknown'))} vs TA: "
          f"{sum(1 for r in ta if r.get('unknown'))}")

    section("9. Failed rows")
    raw = [json.loads(line) for line in open(REPO) if line.strip()]
    for r in raw:
        if r.get("failed", False):
            print(f"  id={r['id']} error={str(r.get('error'))[:200]}")

    if args.reread:
        reread_section("TA dev", dev)
        reread_section("TA test", ta)


if __name__ == "__main__":
    main()
