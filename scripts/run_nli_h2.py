"""Run the repo NLI (src/epistemic/nli.py, cross-encoder/nli-deberta-v3-base)
over the H2 pair set and save predictions.

- Passages are reconstructed from data/manifests/dev.jsonl by qid (the gold
  paragraphs); the script asserts the stored premise matches them exactly.
- verify() is called with the production defaults theta_s=0.5, theta_c=0.5,
  pre_filter=False (configs/base.yaml nli thetas). Predicted = verify()['status'].
- The NLI memo (results/nli_memo.pkl) is a pure cache; to keep this task
  read-only except for the output file, memo_path is redirected to /tmp
  before any scoring. This cannot change predictions (memo keys are hashes
  of claim+windows and values are the computed (max_ent, max_con)).
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.epistemic.nli import NLI

DEV = ROOT / "data/manifests/dev.jsonl"
PAIRS = ROOT / "data/nli_eval_pairs.jsonl"
OUT = ROOT / "results/nli_eval_h2.jsonl"

rows = {}
for l in open(DEV):
    r = json.loads(l)
    rows[r["_id"]] = r

def gold_paras(r):
    titles = {t for t, _ in r["supporting_facts"]}
    return [{"title": t, "sentences": s} for t, s in r["context"] if t in titles]

pairs = [json.loads(l) for l in open(PAIRS)]
print(f"loaded {len(pairs)} pairs")

nli = NLI()  # loads cross-encoder/nli-deberta-v3-base from HF cache
print(f"model: {nli.name}; i_ent={nli.i_ent} i_con={nli.i_con}; "
      f"labels={nli.model.config.id2label}")
nli.memo_path = Path("/tmp/nli_memo_h2.pkl")  # keep repo memo untouched

out = []
for p in pairs:
    r = rows[p["qid"]]
    passages = gold_paras(r)
    stored = [s.strip() for _, ss in
              [(t, s) for t, s in r["context"] if t in {t2 for t2, _ in r["supporting_facts"]}]
              for s in ss]
    assert stored == [s.strip() for s in p["premise"]], f"premise mismatch for {p['id']}"
    res = nli.verify(p["hypothesis"], passages)  # defaults theta_s=0.5, theta_c=0.5
    per_passage = []
    for pg in passages:
        e, c = nli.best(p["hypothesis"], pg)
        per_passage.append({"title": pg["title"], "max_ent": round(e, 4), "max_con": round(c, 4)})
    out.append({
        "id": p["id"],
        "gold": p["gold"],
        "predicted": res["status"],
        "scores": {
            "max_ent": round(max((x for _, x in res["sup"]), default=0.0), 4),
            "max_con": round(max((x for _, x in res["con"]), default=0.0), 4),
            "sup": [[t, round(v, 4)] for t, v in res["sup"]],
            "con": [[t, round(v, 4)] for t, v in res["con"]],
            "conflict": res["conflict"],
            "per_passage": per_passage,
        },
    })

with open(OUT, "w") as f:
    for o in out:
        f.write(json.dumps(o, ensure_ascii=False) + "\n")
print(f"wrote {len(out)} predictions to {OUT}")
from collections import Counter
print("predicted dist:", Counter(o["predicted"] for o in out))
print("gold dist:", Counter(o["gold"] for o in out))
