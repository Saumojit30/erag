"""Tests for scripts/train_adaptive_rag_router.py (change adaptive-rag-baseline, B.1).

Tests first: these must fail before the training script exists and
pass after. They cover only the pure, fast parts -- the label
mapping, the class-weight computation, and the Test-400 refusal
guard. The fine-tuning loop itself is verified by Gate AR-1 (held-out
accuracy), not by unit tests.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from train_adaptive_rag_router import (  # noqa: E402
    LABEL_TO_ID,
    class_weights,
    refuse_test_overlap,
)


def test_label_mapping():
    assert LABEL_TO_ID == {"A": 0, "B": 1, "C": 2}


def test_class_weights_inverse_frequency():
    # 19 / 532 / 549 over N=1100: A gets the largest weight.
    w = class_weights({"A": 19, "B": 532, "C": 549})
    assert len(w) == 3
    assert w[0] > w[1] > w[2]
    # Inverse frequency normalized to mean 1: w_i = (N / (3 * n_i)).
    assert w[0] == pytest.approx(1100 / (3 * 19), rel=1e-6)
    assert w[2] == pytest.approx(1100 / (3 * 549), rel=1e-6)


def test_refuse_test_overlap(tmp_path):
    test_qs = {"what is the capital of france?"}
    clean = [{"question": "Who wrote Hamlet?", "label": "B"}]
    refuse_test_overlap(clean, test_qs)  # no raise
    bad = [{"question": "What is the capital of France?", "label": "B"}]
    with pytest.raises(ValueError, match="Test-400"):
        refuse_test_overlap(bad, test_qs)


def test_training_file_has_no_test_overlap():
    rows = [json.loads(l) for l in open(REPO / "data/adaptive_rag_training.jsonl")]
    test_qs = {json.loads(l)["question"].strip().lower()
               for l in open(REPO / "data/manifests/test.jsonl")}
    refuse_test_overlap(rows, test_qs)  # must not raise
    assert len(rows) == 1100
