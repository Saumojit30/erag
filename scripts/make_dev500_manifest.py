"""Build a Dev-500 manifest (500 fresh HotpotQA dev questions) for H18 decisions.

Source: data/raw_downloads/hotpot_dev_distractor_v1.parquet (HF hotpot_qa,
config distractor, split validation — 7,405 rows, the official dev set).
Excludes every id already used in data/manifests/{debug,dev,test}.jsonl
(550 ids) so the Dev-500 is disjoint from the tuning set (dev-100) and
the held-out confirmation set (test-400). Stratified by (type, level),
seed 29.

Output dir data/manifests_dev500/ holds dev.jsonl (the 500) plus a copy of
test.jsonl: the runner pools dev+test as the retrieval corpus, so the copy
exists only so the Dev-500 questions' own passages are indexed. Never run
split=test from this dir as an evaluation.

Usage:
    .venv/bin/python scripts/make_dev500_manifest.py
"""

import collections
import hashlib
import json
import os
import random
import shutil

import pyarrow.parquet as pq

RAW = "data/raw_downloads/hotpot_dev_distractor_v1.parquet"
EXISTING = ["data/manifests/debug.jsonl", "data/manifests/dev.jsonl",
            "data/manifests/test.jsonl"]
OUT_DIR = "data/manifests_dev500"
N = 500
SEED = 29


def load_ids(path):
    return {json.loads(l)["_id"] for l in open(path) if l.strip()}


def to_manifest_row(r):
    ctx = r["context"]
    titles = ctx["title"]
    sents = ctx["sentences"]
    context = [[t, list(s)] for t, s in zip(titles, sents)]
    sf = r["supporting_facts"]
    supporting = [[t, int(i)] for t, i in zip(sf["title"], sf["sent_id"])]
    return {
        "_id": r["id"],
        "answer": r["answer"],
        "question": r["question"],
        "supporting_facts": supporting,
        "context": context,
        "type": r["type"],
        "level": r["level"],
    }


def main():
    table = pq.read_table(RAW)
    rows = [to_manifest_row(r) for r in table.to_pylist()]
    print(f"raw rows: {len(rows)}")
    used = set()
    for p in EXISTING:
        used |= load_ids(p)
    print(f"excluded existing ids: {len(used)}")
    pool = [r for r in rows if r["_id"] not in used]
    print(f"pool after exclusion: {len(pool)}")
    assert len(rows) == 7405, "expected the full 7,405-row official dev set"
    assert len(pool) == 7405 - len(used)

    strata = collections.defaultdict(list)
    for r in pool:
        strata[(r["type"], r["level"])].append(r)
    rng = random.Random(SEED)
    for v in strata.values():
        rng.shuffle(v)
    dev = []
    for key in sorted(strata):
        v = strata[key]
        nd = round(N * len(v) / len(pool))
        dev += v[:nd]
    rng.shuffle(dev)
    dev = dev[:N]
    assert len(dev) == N
    assert len({r["_id"] for r in dev}) == N
    assert not ({r["_id"] for r in dev} & used), "overlap with existing splits"
    # Most questions have 10 passages; 60/7405 in the raw file have 2-9
    # (near-duplicate titles merged). The existing Test-400 already
    # contains two such rows, and the runner handles variable context.
    ctx_dist = collections.Counter(len(r["context"]) for r in dev)
    assert min(ctx_dist) >= 2, "every Q needs at least its 2 gold passages"

    os.makedirs(OUT_DIR, exist_ok=True)
    dev_path = os.path.join(OUT_DIR, "dev.jsonl")
    with open(dev_path, "w", encoding="utf-8") as f:
        for r in dev:
            f.write(json.dumps(r) + "\n")
    shutil.copy("data/manifests/test.jsonl",
                os.path.join(OUT_DIR, "test.jsonl"))
    counts = collections.Counter((r["type"], r["level"]) for r in dev)
    manifest = {
        "source": "hotpot_qa distractor validation (7,405 rows)",
        "source_file": os.path.basename(RAW),
        "n_dev": N,
        "seed": SEED,
        "excluded_ids": sorted(used),
        "excluded_note": "debug-50 + dev-100 + test-400 ids; Dev-500 is "
                          "disjoint from the tuning set and the held-out "
                          "Test-400 confirmation set",
        "corpus_note": "test.jsonl here is a copy of the Test-400 file, "
                       "present only so the runner's pooled dev+test "
                       "retrieval corpus includes the Dev-500 questions' "
                       "own passages. Never evaluate split=test from this dir.",
        "strata": {f"{k[0]}/{k[1]}": v for k, v in sorted(counts.items())},
        "context_lengths": {str(k): v for k, v in sorted(ctx_dist.items())},
        "sha256": hashlib.sha256(open(dev_path, "rb").read()).hexdigest(),
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"wrote {dev_path} ({N} rows), strata: {dict(counts)}")
    print("sha256:", manifest["sha256"])


if __name__ == "__main__":
    main()
