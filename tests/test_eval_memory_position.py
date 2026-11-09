"""Tests for the --position section of scripts/eval_memory.py (step 6, A.2).

Genuine tests-first: these tests define the section's API and its
verification numbers before the implementation exists. They use mocked
rows, plus one end-to-end test that reproduces the E5 numbers from the
stored stream files (pinned verification, not a live run).
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import eval_memory

REPO = os.path.join(os.path.dirname(__file__), "..")


def _row(qid, em=1, f1=1.0, calls=10, hits=0, ret=2, mem_used=0,
         events=None, store=None, texts=None):
    r = {
        "id": qid, "em": em, "f1": f1, "llm_calls": calls,
        "cache_hits": hits, "retrievals": ret, "mem_used": mem_used,
        "mem_events": events or [], "failed": False,
    }
    if store is not None:
        r["mem_store_size"] = store
    if texts is not None:
        r["mem_texts"] = texts
    return r


def _clusters(qids_positions):
    # qids_positions: {qid: position}
    return {
        qid: {"cluster": "c", "cluster_index": 0, "position": pos}
        for qid, pos in qids_positions.items()
    }


def test_band_of_boundaries():
    assert eval_memory.band_of(0) == "early"
    assert eval_memory.band_of(1) == "early"
    assert eval_memory.band_of(2) == "mid"
    assert eval_memory.band_of(3) == "mid"
    assert eval_memory.band_of(4) == "late"
    assert eval_memory.band_of(5) == "late"
    assert eval_memory.band_of(6) is None
    assert eval_memory.band_of(None) is None


def test_dedupe_rows_keeps_last():
    rows = [_row("a", em=0), _row("b", em=1), _row("a", em=1)]
    out = eval_memory.dedupe_rows(rows)
    assert len(out) == 2
    assert [r for r in out if r["id"] == "a"][0]["em"] == 1


def test_arm_metrics_basic():
    rows = [
        _row("q1", em=1, f1=0.8, calls=10, hits=2, ret=3, mem_used=1),
        _row("q2", em=0, f1=0.2, calls=12, hits=0, ret=2, mem_used=0),
    ]
    m = eval_memory.arm_metrics(rows, _clusters({"q1": 0, "q2": 4}))
    assert m["n"] == 2
    assert m["em"] == 0.5
    assert m["f1"] == 0.5
    assert m["calls"] == 11.0
    assert m["live_calls"] == 10.0  # (8 + 12) / 2
    assert m["cache_hits"] == 1.0
    assert m["retrievals"] == 2.5
    assert m["fired"] == 1
    assert m["fire_rate"] == 0.5
    assert m["bands"]["early"]["n"] == 1
    assert m["bands"]["early"]["em"] == 1.0
    assert m["bands"]["late"]["n"] == 1
    assert m["bands"]["late"]["em"] == 0.0


def test_arm_metrics_missing_store_fields_reported_not_recorded():
    # E5 rows carry no mem_store_size / mem_texts: report as not recorded,
    # never as zero (zero would mean "empty store", a different claim).
    rows = [_row("q1", em=1, mem_used=1), _row("q2", em=0, mem_used=0)]
    m = eval_memory.arm_metrics(rows, _clusters({"q1": 0, "q2": 1}))
    assert m["store_size_mean"] is None
    assert m["bands"]["early"]["store_size_mean"] is None


def test_arm_metrics_with_store_fields():
    rows = [
        _row("q1", em=1, mem_used=1, store=3, texts=["belief one"]),
        _row("q2", em=0, mem_used=0, store=3, texts=[]),
    ]
    m = eval_memory.arm_metrics(rows, _clusters({"q1": 0, "q2": 1}))
    assert m["store_size_mean"] == 3.0
    assert m["store_texts_seen"] == ["belief one"]


def test_paired_band_delta_within_band():
    nomem = [_row("q1", em=0, calls=10), _row("q2", em=1, calls=12),
             _row("q3", em=0, calls=10)]
    mem = [_row("q1", em=1, calls=10), _row("q2", em=1, calls=8),
           _row("q3", em=0, calls=10)]
    clusters = _clusters({"q1": 0, "q2": 0, "q3": 4})
    d = eval_memory.paired_delta(nomem, mem, clusters)
    assert d["overall"]["d_em"] == 1.0 / 3.0
    assert d["overall"]["d_calls"] == -4.0 / 3.0  # (0 - 4 + 0) / 3
    assert d["bands"]["early"]["d_em"] == 0.5
    assert d["bands"]["early"]["d_calls"] == -2.0  # (0 - 4) / 2
    assert d["bands"]["late"]["d_em"] == 0.0
    assert d["bands"]["late"]["d_calls"] == 0.0


def test_fired_row_paired_restricts_to_fired():
    nomem = [_row("q1", em=0, calls=10), _row("q2", em=1, calls=10)]
    mem = [_row("q1", em=1, calls=8, mem_used=1),
           _row("q2", em=0, calls=10, mem_used=0)]
    clusters = _clusters({"q1": 0, "q2": 1})
    d = eval_memory.fired_row_paired(nomem, mem, clusters)
    assert d["n_fired"] == 1
    assert d["d_em"] == 1.0
    assert d["d_calls"] == -2.0


def test_planted_override_stats():
    plant_defs = [
        {"text": "Wolfgang Becker is a French film director born in Paris."},
        {"text": "Paul Hindemith was born in 1875 in Frankfurt, Germany."},
    ]
    rows = [
        _row("q1", events=[{"event": "overridden",
                            "belief": "Wolfgang Becker is a French film director born in Paris.",
                            "by": ["Wolfgang Becker"]}],
             texts=[]),
        _row("q2", mem_used=1,
             texts=["Paul Hindemith was born in 1875 in Frankfurt, Germany."]),
    ]
    s = eval_memory.planted_stats(rows, plant_defs)
    assert s["n_planted"] == 2
    assert s["n_retrieved"] == 2  # 1 overridden + 1 returned as a passage
    assert s["n_overridden"] == 1
    assert s["override_rate_retrieved"] == 0.5
    assert s["override_rate_planted"] == 0.5
    assert s["overridden_beliefs"] == [
        "Wolfgang Becker is a French film director born in Paris."
    ]


def test_planted_false_claim_in_answer():
    plant_defs = [{"text": "Elizabeth Taylor was born on February 27, 1890 in London."}]
    bad = dict(_row("q1"), answer="1890")
    good = dict(_row("q2"), answer="1932")
    unknown = dict(_row("q3"), answer="unknown")
    s = eval_memory.planted_stats([bad, good, unknown], plant_defs)
    assert len(s["false_claim_answers"]) == 1
    assert s["false_claim_answers"][0]["id"] == "q1"
    assert s["false_claim_answers"][0]["answer"] == "1890"


def test_load_clusters_missing_file_returns_empty():
    assert eval_memory.load_clusters("/tmp/does-not-exist-clusters.json") == {}


# --- E5 end-to-end reproduction (pinned verification) -----------------------

E5_CLUSTERS = [
    ("Music Composers", ["Paul Hindemith", "Maurice Ravel", "Béla Bartók",
                         "Bernhard Heiden", "Benjamin Britten",
                         "Suvini Zerboni"]),
    ("WWII Battles", ["Battle of Manila (1945)", "Battle of Guam (1944)",
                      "Battle of Saipan", "Battle of Stones River",
                      "Spring 1945 offensive in Italy", "Seven Days Battles"]),
    ("Universities", ["University of Colorado", "Columbia University",
                      "University of Rochester", "Ateneo de Davao University",
                      "University of Leeds", "University of Vermont"]),
    ("Film Directors", ["Wolfgang Becker", "Paul Andrew Williams",
                        "Vladimir Danilevich", "Jacques Audiard", "Jean Vigo",
                        "Lester James Peries", "The Lone Ranger (2013 film)",
                        "Poetry in Motion (film)"]),
    ("Actors & Writers", ["Elizabeth Taylor", "Margaret Landon",
                          "Antonin Artaud", "Henry Roth",
                          "Robert Erskine Childers", "Terry Richardson",
                          "Li Yitong (actress)", "Unbroken (film)"]),
]


def _e5_sidecar():
    stream = [json.loads(l) for l in
              open(os.path.join(REPO, "data/manifests/stream.jsonl"))
              if l.strip()]
    sidecar = {}
    counts = {}
    for r in stream:
        titles = {t for t, _ in r.get("supporting_facts", [])}
        ci = next(i for i, (_, tl) in enumerate(E5_CLUSTERS)
                  if titles & set(tl))
        pos = counts.get(ci, 0)
        counts[ci] = pos + 1
        sidecar[r["_id"]] = {"cluster": E5_CLUSTERS[ci][0],
                             "cluster_index": ci, "position": pos}
    return sidecar


def test_e5_reproduction():
    clusters = _e5_sidecar()
    res = eval_memory.position_section(
        os.path.join(REPO, "results/stream_nomem.jsonl"),
        os.path.join(REPO, "results/stream_mem.jsonl"),
        os.path.join(REPO, "results/stream_planted.jsonl"),
        clusters,
        os.path.join(REPO, "data/manifests/planted.json"),
    )
    nomem = res["nomem"]
    mem = res["mem"]
    # Float means are compared rounded to the printed precision (4dp for
    # EM/F1, 2dp for per-question rates): the section prints rounded
    # values, and the verification is that the printed numbers match.
    assert round(nomem["em"], 4) == 0.4000
    assert round(nomem["f1"], 4) == 0.4828
    assert round(nomem["calls"], 2) == 14.30
    assert round(nomem["retrievals"], 2) == 2.50
    assert round(nomem["cache_hits"], 2) == 0.27
    assert round(mem["em"], 4) == 0.4000
    assert round(mem["cache_hits"], 2) == 14.30
    assert round(mem["live_calls"], 2) == 0.0  # the E5 replay
    assert res["fired_qids"] and len(res["fired_qids"]) == 2
    # fired rows are idx 20 (cluster 3, pos 2) and idx 29 (cluster 4, pos 5)
    fired_pairs = sorted(
        (clusters[qid]["cluster_index"], clusters[qid]["position"])
        for qid in res["fired_qids"])
    assert fired_pairs == [(3, 2), (4, 5)]
    bands = res["bands"]
    assert round(bands["early"]["nomem_em"], 4) == 0.5000
    assert round(bands["early"]["nomem_calls"], 2) == 14.20
    assert round(bands["mid"]["nomem_em"], 4) == 0.4000
    assert round(bands["mid"]["nomem_calls"], 2) == 13.70
    assert round(bands["late"]["nomem_em"], 4) == 0.3000
    assert round(bands["late"]["nomem_calls"], 2) == 15.00
    planted = res["planted_stats"]
    assert planted["n_overridden"] == 1
    assert planted["overridden_beliefs"] == [
        "Wolfgang Becker is a French film director born in Paris."
    ]
    assert planted["n_retrieved"] == 1
    assert planted["override_rate_retrieved"] == 1.0
    assert planted["false_claim_answers"] == []
    # E5 store fields were never recorded: reported, not zeroed.
    assert nomem["store_size_mean"] is None
    assert mem["store_size_mean"] is None
