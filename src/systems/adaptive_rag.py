"""Adaptive-RAG routing baseline (change adaptive-rag-baseline, C.1).

Routes each question up front with a small trained 3-class
classifier (DistilBERT, configs/adaptive_rag_classifier/) and
dispatches to exactly one existing strategy -- no new retrieval or
generation code:

- A -- no retrieval: run_closed_book
- B -- single-step: run_standard
- C -- multi-step: run_ircot

The chosen strategy's result dict is returned plus `route` and
`route_p` (the classifier's max class probability). The runner
writes extra keys from the system dict into the output row
(`rec.update(r)` in scripts/run_experiment.py), so every
Adaptive-RAG row carries its route.

The classifier is loaded once per process (path from
`adaptive_rag.classifier_path` in config, default
`configs/adaptive_rag_classifier/`). A missing classifier file is
a loud FileNotFoundError at startup, never a silent fall-through
to one strategy.
"""

from pathlib import Path
from typing import Any, Dict, Tuple

from src.systems.ircot import run_ircot
from src.systems.standard import run_closed_book, run_standard

DEFAULT_CLASSIFIER_PATH = "configs/adaptive_rag_classifier"
LABEL_TO_ROUTE = {0: "A", 1: "B", 2: "C"}
ROUTES = ("A", "B", "C")

_ROUTER = None
_ROUTER_PATH = None


class RouterClassifier:
    """DistilBERT 3-class complexity router loaded from a saved artifact."""

    def __init__(self, path):
        # Lazy imports: loading torch/transformers is slow, and the
        # mocked tests never need the real model.
        import torch
        from transformers import (
            DistilBertForSequenceClassification,
            DistilBertTokenizerFast,
        )

        self._torch = torch
        self._tokenizer = DistilBertTokenizerFast.from_pretrained(str(path))
        self._model = DistilBertForSequenceClassification.from_pretrained(
            str(path)
        )
        self._model.eval()

    def predict(self, question: str) -> Tuple[str, float]:
        """Return (route, max class probability) for one question."""
        inputs = self._tokenizer(
            question, return_tensors="pt", truncation=True, max_length=64
        )
        with self._torch.no_grad():
            logits = self._model(**inputs).logits
        probs = self._torch.softmax(logits, dim=-1)[0]
        idx = int(probs.argmax().item())
        return LABEL_TO_ROUTE[idx], float(probs[idx].item())


def load_classifier(path) -> RouterClassifier:
    """Load the router from `path`; raise loudly if it is missing."""
    p = Path(path)
    if not p.is_dir():
        raise FileNotFoundError(
            f"Adaptive-RAG classifier not found at {path!r}: "
            "run scripts/train_adaptive_rag_router.py first; "
            "the run must never silently fall through to one strategy."
        )
    has_weights = (p / "model.safetensors").exists() or (
        p / "pytorch_model.bin"
    ).exists()
    if not (p / "config.json").exists() or not has_weights:
        raise FileNotFoundError(
            f"Adaptive-RAG classifier at {path!r} is incomplete "
            "(needs config.json and model weights); refusing to run."
        )
    return RouterClassifier(p)


def get_classifier(path) -> RouterClassifier:
    """Return the process-wide router, loading it once per path."""
    global _ROUTER, _ROUTER_PATH
    if _ROUTER is None or _ROUTER_PATH != str(path):
        _ROUTER = load_classifier(path)
        _ROUTER_PATH = str(path)
    return _ROUTER


def _classify(question: str, classifier) -> Tuple[str, float]:
    """Ask a classifier (object with .predict, or a callable) for a route."""
    if classifier is None:
        raise ValueError("No classifier supplied to the Adaptive-RAG router.")
    if callable(getattr(classifier, "predict", None)):
        route, prob = classifier.predict(question)
    elif callable(classifier):
        route, prob = classifier(question)
    else:
        raise ValueError(
            "Adaptive-RAG classifier must expose .predict(question) "
            "-> (route, probability)."
        )
    if route not in ROUTES:
        raise ValueError(
            f"Adaptive-RAG router returned invalid route {route!r}; "
            f"expected one of {ROUTES}."
        )
    return route, float(prob)


def run_adaptive_rag(
    item: Dict[str, Any],
    retriever: Any,
    llm: Any,
    cfg: Dict[str, Any],
    tracker: Any,
    classifier=None,
) -> Dict[str, Any]:
    """Classify the question, run exactly one existing strategy, tag the route."""
    if classifier is None:
        path = cfg.get("adaptive_rag", {}).get(
            "classifier_path", DEFAULT_CLASSIFIER_PATH
        )
        classifier = get_classifier(path)

    route, route_p = _classify(item["question"], classifier)

    if route == "A":
        out = run_closed_book(item, retriever, llm, cfg, tracker)
    elif route == "B":
        out = run_standard(item, retriever, llm, cfg, tracker)
    else:  # route == "C"
        out = run_ircot(item, retriever, llm, cfg, tracker)

    out = dict(out)
    out["route"] = route
    out["route_p"] = route_p
    return out
