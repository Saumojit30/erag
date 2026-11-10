"""Tests for src/systems/adaptive_rag.py (change adaptive-rag-baseline, C.1).

Tests first: the router classifies each question with the trained
classifier and dispatches to exactly one existing strategy --
closed-book (A), single-step Standard RAG (B), or multi-step IRCoT
(C) -- and records `route` / `route_p` on the result. A missing
classifier file fails loudly at startup, never silently falling
through to one strategy. No live LLM or classifier calls here: the
classifier is faked, and the strategies run against mocked
retriever/LLM.
"""

from unittest.mock import MagicMock

import pytest

from src.llm.client import Tracker
from src.systems.adaptive_rag import (
    DEFAULT_CLASSIFIER_PATH,
    load_classifier,
    run_adaptive_rag,
)


class FakeClassifier:
    """Stand-in for the trained router: always returns one fixed route."""

    def __init__(self, route, prob=0.83):
        self.route = route
        self.prob = prob
        self.seen = []

    def predict(self, question):
        self.seen.append(question)
        return self.route, self.prob


def _item():
    return {"_id": "q1", "question": "What is the capital of France?"}


def _cfg():
    return {"retrieval": {"k": 3}, "ircot": {"max_steps": 4, "pool_cap": 12}}


def _retriever():
    r = MagicMock()
    r.search.return_value = [
        {"title": "Paris", "sentences": ["Paris is the capital."],
         "text": "Paris. Paris is the capital."}
    ]
    return r


def test_route_a_closed_book_no_retrieval():
    llm = MagicMock()
    llm.chat.return_value = "Paris"
    retriever = _retriever()
    tr = Tracker()

    out = run_adaptive_rag(
        _item(), retriever, llm, _cfg(), tr,
        classifier=FakeClassifier("A", 0.91),
    )

    assert out["answer"] == "Paris"
    assert out["route"] == "A"
    assert out["route_p"] == pytest.approx(0.91)
    assert out["pool_titles"] == []
    assert retriever.search.call_count == 0
    assert llm.chat.call_count == 1


def test_route_b_single_step_standard():
    llm = MagicMock()
    llm.chat.return_value = "Paris"
    retriever = _retriever()
    tr = Tracker()

    out = run_adaptive_rag(
        _item(), retriever, llm, _cfg(), tr,
        classifier=FakeClassifier("B", 0.77),
    )

    assert out["answer"] == "Paris"
    assert out["route"] == "B"
    assert out["route_p"] == pytest.approx(0.77)
    assert out["pool_titles"] == ["Paris"]
    assert retriever.search.call_count == 1
    assert llm.chat.call_count == 1


def test_route_c_multi_step_ircot():
    retriever = MagicMock()
    retriever.search.side_effect = [
        [{"title": "Doc A", "sentences": ["Paragraph A."],
          "text": "Doc A. Paragraph A."}],
        [{"title": "Doc B", "sentences": ["Paragraph B."],
          "text": "Doc B. Paragraph B."}],
    ]
    llm = MagicMock()
    llm.chat.side_effect = [
        "First step of reasoning.",
        "So the answer is: Paris.",
        "Paris",
    ]
    tr = Tracker()

    out = run_adaptive_rag(
        _item(), retriever, llm, _cfg(), tr,
        classifier=FakeClassifier("C", 0.64),
    )

    assert out["answer"] == "Paris"
    assert out["route"] == "C"
    assert out["route_p"] == pytest.approx(0.64)
    assert out["hops"] == 2
    assert "Doc B" in out["pool_titles"]


def test_invalid_route_raises():
    llm = MagicMock()
    llm.chat.return_value = "Paris"
    tr = Tracker()

    with pytest.raises(ValueError, match="route"):
        run_adaptive_rag(
            _item(), _retriever(), llm, _cfg(), tr,
            classifier=FakeClassifier("Z"),
        )


def test_missing_classifier_fails_loudly(tmp_path):
    missing = str(tmp_path / "no_such_classifier")
    cfg = _cfg()
    cfg["adaptive_rag"] = {"classifier_path": missing}
    llm = MagicMock()
    llm.chat.return_value = "Paris"
    tr = Tracker()

    with pytest.raises(FileNotFoundError, match="classifier"):
        run_adaptive_rag(_item(), _retriever(), llm, cfg, tr)


def test_load_classifier_missing_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="classifier"):
        load_classifier(str(tmp_path / "no_such_classifier"))


def test_default_classifier_path():
    assert DEFAULT_CLASSIFIER_PATH == "configs/adaptive_rag_classifier"


def test_dispatch_adaptive_rag_branch(monkeypatch):
    from scripts.run_experiment import dispatch

    fake = FakeClassifier("B", 0.88)
    monkeypatch.setattr(
        "src.systems.adaptive_rag.get_classifier", lambda path: fake
    )
    llm = MagicMock()
    llm.chat.return_value = "Paris"
    retriever = _retriever()
    tr = Tracker()

    out = dispatch(
        "adaptive_rag", _item(), retriever, llm, None, _cfg(), tr, None
    )

    assert out["route"] == "B"
    assert out["route_p"] == pytest.approx(0.88)
    assert out["answer"] == "Paris"
