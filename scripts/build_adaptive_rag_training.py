"""Build the Adaptive-RAG router training set (change adaptive-rag-baseline, A.1).

Labels follow the Adaptive-RAG paper's two methods (Jeong et al.,
NAACL 2024, §3.2 and Limitations):
  (1) outcome-based: the simplest strategy that answers correctly
      sets the label (closed-book correct -> A; closed-book wrong but
      single-step correct -> B; single-step wrong -> C);
  (2) dataset-bias fallback: single-hop datasets -> B, multi-hop
      datasets -> C.

Construction (decided 2026-11-10, recorded BEFORE training):
  A: HotpotQA dev questions where the STORED closed-book run was
     correct (results/closed_book_dev.jsonl, EM=1). 19 questions.
     Outcome-based; no new LLM calls. The A class is thin because
     only 19/100 dev questions are answerable without retrieval --
     the paper's own small classifier gets the A class right only
     ~27% of the time (Table 6), so a thin A is expected, not a
     defect. Stage 2 (when a Groq key is available): outcome-label
     a TriviaQA sample with closed-book runs to add genuine A
     examples and rebalance.
  B: SQuAD v1.1 train sample, 500 questions (dataset bias:
     single-hop -> B), + dev questions where closed-book failed
     but Standard succeeded, 32 questions (outcome-based).
  C: 2WikiMultiHopQA TRAIN sample, 500 questions (dataset bias:
     multi-hop -> C; TRAIN split only -- 2Wiki dev/test are Phase 3
     material and never enter this file), + dev questions where
     Standard failed, 49 questions (outcome-based + dataset bias).

Total 1,100 rows. Majority class ~50% (C), so Gate AR-1's
"above majority-class rate" floor is meaningful.

Guards: the script asserts no Test-400 row enters the file (it
checks every question's normalized text against
data/manifests/test.jsonl), asserts no duplicate questions, and
asserts the dev-labeled counts reproduce exactly (A=19, B=32,
C=49). Sampling is deterministic (seed 42).
"""

import json
import random
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEED = 42
SQUAD_N = 500
WIKI_N = 500

DEV_LABELS = {"A": 19, "B": 32, "C": 49}  # from stored runs, verified 2026-11-10


def norm(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


def outcome_label_dev():
    """Label the 100 dev questions from the three stored dev runs.

    A: closed-book correct. B: closed-book wrong, Standard correct.
    C: Standard wrong (IRCoT correct or all fail -- multi-hop
    dataset bias says C).
    """
    def load(p):
        return {r.get("id") or r.get("_id"): r
                for r in (json.loads(l) for l in open(p))}

    cb = load(REPO / "results/closed_book_dev.jsonl")
    st = load(REPO / "results/standard_dev.jsonl")
    ir = load(REPO / "results/ircot_dev.jsonl")
    dev = {r["_id"]: r for r in
           (json.loads(l) for l in open(REPO / "data/manifests/dev.jsonl"))}
    ids = sorted(set(cb) & set(st) & set(ir) & set(dev))
    assert len(ids) == 100, f"expected 100 common dev ids, got {len(ids)}"
    out = []
    for i in ids:
        q = dev[i]["question"]
        if cb[i].get("em", 0) == 1:
            out.append({"question": q, "label": "A", "source": "hotpotqa_dev_outcome"})
        elif st[i].get("em", 0) == 1:
            out.append({"question": q, "label": "B", "source": "hotpotqa_dev_outcome"})
        else:
            out.append({"question": q, "label": "C", "source": "hotpotqa_dev_outcome"})
    return out


def squad_sample(n: int, rng: random.Random):
    """Single-hop SQuAD v1.1 train questions -> B (dataset bias)."""
    d = json.load(open(REPO / "data/raw_downloads/squad-train-v1.1.json"))
    qs = []
    for a in d["data"]:
        for p in a["paragraphs"]:
            for qa in p["qas"]:
                qs.append(qa["question"])
    rng.shuffle(qs)
    seen, out = set(), []
    for q in qs:
        if norm(q) in seen:
            continue
        seen.add(norm(q))
        out.append({"question": q, "label": "B", "source": "squad_v1_train_bias"})
        if len(out) == n:
            return out
    raise AssertionError(f"only {len(out)} unique SQuAD questions, wanted {n}")


def wiki_sample(n: int, rng: random.Random):
    """Multi-hop 2Wiki TRAIN questions -> C (dataset bias).

    TRAIN split only. 2Wiki dev/test are Phase 3 material and are
    never read here.
    """
    import pandas as pd

    df = pd.read_parquet(REPO / "data/raw_downloads/2wiki-train.parquet")
    qs = df["question"].dropna().astype(str).tolist()
    rng.shuffle(qs)
    seen, out = set(), []
    for q in qs:
        if norm(q) in seen:
            continue
        seen.add(norm(q))
        out.append({"question": q, "label": "C", "source": "2wiki_train_bias"})
        if len(out) == n:
            return out
    raise AssertionError(f"only {len(out)} unique 2Wiki questions, wanted {n}")


def main() -> None:
    rng = random.Random(SEED)
    rows = outcome_label_dev()
    rows += squad_sample(SQUAD_N, rng)
    rows += wiki_sample(WIKI_N, rng)

    # Verification (must hold before the file is written).
    counts = {"A": 0, "B": 0, "C": 0}
    for r in rows:
        counts[r["label"]] += 1
    dev_counts = {"A": 0, "B": 0, "C": 0}
    for r in rows:
        if r["source"] == "hotpotqa_dev_outcome":
            dev_counts[r["label"]] += 1
    assert dev_counts == DEV_LABELS, f"dev labels {dev_counts} != {DEV_LABELS}"
    assert len({norm(r["question"]) for r in rows}) == len(rows), "duplicate questions"
    test_qs = {norm(json.loads(l)["question"])
               for l in open(REPO / "data/manifests/test.jsonl")}
    overlap = [r["question"] for r in rows if norm(r["question"]) in test_qs]
    assert not overlap, f"Test-400 overlap: {overlap[:3]}"

    rng.shuffle(rows)
    out_path = REPO / "data/adaptive_rag_training.jsonl"
    with open(out_path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {out_path}: N={len(rows)} counts={counts} "
          f"(dev outcome A/B/C = {dev_counts})")
    print("zero Test-400 overlap: verified; no duplicate questions: verified")


if __name__ == "__main__":
    main()
