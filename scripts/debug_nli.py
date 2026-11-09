import json, sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pathlib import Path
from src.epistemic.nli import NLI

rows = {}
for l in open(ROOT / "data/manifests/dev.jsonl"):
    r = json.loads(l); rows[r["_id"]] = r
pairs = {json.loads(l)["id"]: json.loads(l) for l in open(ROOT / "data/nli_eval_pairs.jsonl")}
preds = {json.loads(l)["id"]: json.loads(l) for l in open(ROOT / "results/nli_eval_h2.jsonl")}

def gold_paras(r):
    titles = {t for t, _ in r["supporting_facts"]}
    return [{"title": t, "sentences": s} for t, s in r["context"] if t in titles]

nli = NLI()
nli.memo_path = Path("/tmp/nli_memo_h2.pkl")
print(f"labels={nli.model.config.id2label} i_ent={nli.i_ent} i_con={nli.i_con}")

for pid in sys.argv[1:]:
    p = pairs[pid]
    passages = gold_paras(rows[p["qid"]])
    print(f"\n===== {pid} gold={p['gold']} pred={preds[pid]['predicted']} =====")
    print("HYP:", p["hypothesis"])
    print("entities:", NLI._extract_subject_entities(p["hypothesis"]))
    for pg in passages:
        wins = nli._windows(pg)
        P = nli._probs(wins, p["hypothesis"])
        for w, pr in zip(wins, P):
            print(f"  [{pg['title']}] ent={pr[nli.i_ent]:.4f} con={pr[nli.i_con]:.4f} neu={pr[3-nli.i_ent-nli.i_con]:.4f} :: {w[:110]}")
    print("  verify:", {k: v for k, v in nli.verify(p["hypothesis"], passages).items() if k in ("status","sup","con")})
