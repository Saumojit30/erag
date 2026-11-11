"""Phase 2.5 diagnosis (stored data only, no live calls).

Q1: FP-control (eager SC) vs tuned (deferred SC) — which rows flip, and what
    characterizes the gains vs the losses?
Q2: The 53 gold-in-claims full-recall wrong rows (tuned) — why didn't the
    re-read save them? What status do the gold-bearing claims carry?
Q3: The 33 never-claimed full-recall wrong rows — where did extraction fail?
"""
import json
import re
from collections import Counter


def load(path):
    seen = {}
    for line in open(path):
        if line.strip():
            r = json.loads(line)
            seen[r["id"]] = r
    return seen


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


def gold_claims(r):
    g = norm(r["gold"])
    if not g:
        return []
    return [c for hop in (r.get("trace") or []) for c in (hop.get("graph") or [])
            if g in norm(c.get("text", ""))]


def gold_in_claims(r):
    return bool(gold_claims(r))


tuned = load("results/trueadaptive/erag_trueadaptive_tuned_test.jsonl")
fpc = load("results/trueadaptive/erag_fp_control_test.jsonl")
print(f"tuned N={len(tuned)}  fp-control N={len(fpc)}  shared={len(set(tuned) & set(fpc))}")

# ---- Q1: flips ----
gains, losses = [], []
for qid in sorted(set(tuned) & set(fpc)):
    t, f = tuned[qid], fpc[qid]
    if t.get("failed") or f.get("failed"):
        continue
    if f["em"] == 1 and t["em"] == 0:
        gains.append((qid, t, f))
    elif f["em"] == 0 and t["em"] == 1:
        losses.append((qid, t, f))
print(f"\nQ1 flips: FP-control gains {len(gains)}, losses {len(losses)}, net {len(gains) - len(losses)}")


def char(rows, label):
    print(f"  {label} (n={len(rows)}):")
    print(f"    tuned sc_skipped_fast_path: {Counter(t.get('sc_skipped_fast_path') for _, t, _ in rows)}")
    print(f"    fp-ctrl sc_skipped_fast_path: {Counter(f.get('sc_skipped_fast_path') for _, _, f in rows)}")
    print(f"    tuned hops: {Counter(t.get('hops') for _, t, _ in rows)}")
    print(f"    fp-ctrl hops: {Counter(f.get('hops') for _, _, f in rows)}")
    print(f"    tuned policy_decision: {Counter(t.get('policy_decision') for _, t, _ in rows)}")
    print(f"    tuned abstained: {sum(1 for _, t, _ in rows if t.get('abstained'))}  "
          f"unknown: {sum(1 for _, t, _ in rows if t.get('unknown'))}")
    print(f"    fp-ctrl abstained: {sum(1 for _, _, f in rows if f.get('abstained'))}  "
          f"unknown: {sum(1 for _, _, f in rows if f.get('unknown'))}")
    print(f"    tuned llm_calls mean: {sum(t['llm_calls'] for _, t, _ in rows) / max(len(rows), 1):.2f}  "
          f"fp-ctrl: {sum(f['llm_calls'] for _, _, f in rows) / max(len(rows), 1):.2f}")


char(gains, "GAINS (fp-control right, tuned wrong)")
char(losses, "LOSSES (fp-control wrong, tuned right)")

# ---- Q2: gold-in-claims wrong rows (tuned) ----
wrong_full = [r for r in tuned.values()
              if r["em"] == 0 and not r.get("unknown") and not r.get("abstained")
              and r.get("recall") == 1.0 and not r.get("failed")]
gic = [r for r in wrong_full if gold_in_claims(r)]
never = [r for r in wrong_full if not gold_in_claims(r)]
print(f"\nQ2 tuned full-recall wrong (answered): {len(wrong_full)}; "
      f"gold-in-claims {len(gic)}, never-claimed {len(never)}")
print(f"  reread_trigger on gold-in-claims rows: {Counter(r.get('reread_trigger') for r in gic)}")
print(f"  reread_trigger on never-claimed rows: {Counter(r.get('reread_trigger') for r in never)}")

statuses = Counter()
ab_gold = 0
for r in gic:
    for c in gold_claims(r):
        statuses[c.get("status")] += 1
        if c.get("answer_bearing"):
            ab_gold += 1
print(f"  gold-bearing claim statuses: {dict(statuses)}; answer_bearing gold claims: {ab_gold}")
# draft vs gold-bearing claim: does the final answer match a WRONG supported claim?
n_draft_matches_wrong_supported = 0
for r in gic:
    da = norm(r.get("answer", ""))
    for c in [c for hop in (r.get("trace") or []) for c in (hop.get("graph") or [])]:
        if c.get("status") == "supported" and norm(c.get("text", "")) and da and da in norm(c.get("text", "")):
            n_draft_matches_wrong_supported += 1
            break
print(f"  rows whose final answer sits inside a WRONG supported claim: {n_draft_matches_wrong_supported}/{len(gic)}")
print(f"  gold-in-claims rows: c0 median-ish mean={sum(r.get('c0', 0) for r in gic) / len(gic):.2f} "
      f"answer_conf mean={sum(r.get('answer_conf', 0) for r in gic) / len(gic):.2f} "
      f"hops={Counter(r.get('hops') for r in gic)}")

# ---- Q3: never-claimed rows — hop-0 recall from the manifest ----
man = {}
for line in open("data/manifests/test.jsonl"):
    if line.strip():
        m = json.loads(line)
        man[m["_id"]] = m
print(f"\nQ3 manifest N={len(man)}")


def hop0_recall(r):
    m = man.get(r["id"])
    if not m:
        return None
    sf = m.get("supporting_facts", [])
    if isinstance(sf, str):
        sf = json.loads(sf)
    titles = set()
    for s in sf:
        if isinstance(s, (list, tuple)):
            titles.add(norm(s[0]))
        else:
            titles.add(norm(str(s)))
    pool = {norm(t) for t in (r.get("trace") or [{}])[0].get("pool", [])}
    if not titles:
        return None
    return len(titles & pool) / len(titles)


h0 = [(r, hop0_recall(r)) for r in never]
print(f"  never-claimed hop-0 recall: {Counter(v for _, v in h0)}")
print(f"  never-claimed final recall: {Counter(r.get('recall') for r in never)}")
print(f"  never-claimed hops: {Counter(r.get('hops') for r in never)}")
print(f"  never-claimed reread_answer EM on triggered: "
      f"{[(r['id'], r.get('reread_trigger')) for r in never if r.get('reread_trigger')][:5]}")

# ---- bonus: the 43 abstained rows — how many would the re-read / t=0 save? ----
abst = [r for r in tuned.values() if r.get("abstained") and not r.get("failed")]
print(f"\nBonus abstained: {len(abst)}; drafts correct (repo EM on draft): "
      f"{sum(1 for r in abst if norm(r.get('draft', '')) == norm(r.get('gold', '')))}")
print(f"  abstained with gold in claims: {sum(1 for r in abst if gold_in_claims(r))}")
print(f"  abstained reread_trigger: {Counter(r.get('reread_trigger') for r in abst)}")
