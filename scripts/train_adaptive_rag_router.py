"""Train the Adaptive-RAG complexity router (change adaptive-rag-baseline, B.1).

Fine-tunes DistilBERT (distilbert-base-uncased, ~66M) for 3-class
question-complexity classification on data/adaptive_rag_training.jsonl
(A.1). Stratified 80/20 split (seed 42); class weights (inverse
frequency) because the A class is thin (19/1100 -- only 19 dev
questions are answerable without retrieval, and the paper's own
small classifier gets the A class right only ~27% of the time).

Output artifact: configs/adaptive_rag_classifier/ (model +
tokenizer + metadata.json with model type, training file, N, class
counts, date, held-out accuracy, per-class accuracy, majority-class
rate, hyperparameters).

Guards: refuses to train if any training question matches a Test-400
question (re-verified at train time, not just at build time).
CPU-only training in the repo venv.
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
import torch
from sklearn.model_selection import train_test_split

REPO = Path(__file__).resolve().parent.parent
LABEL_TO_ID = {"A": 0, "B": 1, "C": 2}
ID_TO_LABEL = {v: k for k, v in LABEL_TO_ID.items()}
SEED = 42


def norm(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


def refuse_test_overlap(rows, test_qs) -> None:
    """Raise if any training row's question matches a Test-400 question."""
    bad = [r["question"] for r in rows if norm(r["question"]) in test_qs]
    if bad:
        raise ValueError(f"Test-400 overlap in training data: {bad[:3]}")


def class_weights(counts) -> list:
    """Inverse-frequency weights normalized to mean 1: w_i = N / (3 * n_i)."""
    total = sum(counts.values())
    return [total / (3 * counts[k]) for k in ("A", "B", "C")]


def load_test_questions():
    return {norm(json.loads(l)["question"])
            for l in open(REPO / "data/manifests/test.jsonl")}


def main() -> None:
    ap = argparse.ArgumentParser(description="Train the Adaptive-RAG router.")
    ap.add_argument("--train-file", default=str(REPO / "data/adaptive_rag_training.jsonl"))
    ap.add_argument("--out-dir", default=str(REPO / "configs/adaptive_rag_classifier"))
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--max-len", type=int, default=64)
    a = ap.parse_args()

    from transformers import (
        DistilBertForSequenceClassification,
        DistilBertTokenizerFast,
        Trainer,
        TrainingArguments,
    )

    rows = [json.loads(l) for l in open(a.train_file)]
    refuse_test_overlap(rows, load_test_questions())
    counts = Counter(r["label"] for r in rows)
    weights = torch.tensor(class_weights(counts), dtype=torch.float)
    print(f"training rows: {len(rows)} counts={dict(counts)} weights={weights.tolist()}")

    texts = [r["question"] for r in rows]
    labels = [LABEL_TO_ID[r["label"]] for r in rows]
    train_idx, held_idx = train_test_split(
        range(len(rows)), test_size=0.2, random_state=SEED,
        stratify=labels)
    print(f"train={len(train_idx)} held-out={len(held_idx)} "
          f"(majority-class rate on held-out: "
          f"{max(Counter(labels[i] for i in held_idx).values()) / len(held_idx):.4f})")

    tok = DistilBertTokenizerFast.from_pretrained("distilbert-base-uncased")

    def encode(idxs):
        enc = tok([texts[i] for i in idxs], truncation=True,
                  padding=True, max_length=a.max_len)
        return {"input_ids": enc["input_ids"],
                "attention_mask": enc["attention_mask"],
                "labels": [labels[i] for i in idxs]}

    class RouterDataset(torch.utils.data.Dataset):
        def __init__(self, idxs):
            self.enc = encode(idxs)

        def __len__(self):
            return len(self.enc["labels"])

        def __getitem__(self, i):
            return {k: torch.tensor(v[i]) for k, v in self.enc.items()}

    class WeightedTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, **kw):
            labels_t = inputs.pop("labels")
            out = model(**inputs)
            loss = torch.nn.functional.cross_entropy(
                out.logits, labels_t, weight=weights.to(out.logits.device))
            return (loss, out) if return_outputs else loss

    model = DistilBertForSequenceClassification.from_pretrained(
        "distilbert-base-uncased", num_labels=3)
    args = TrainingArguments(
        output_dir="/tmp/adaptive_rag_trainer",
        num_train_epochs=a.epochs,
        per_device_train_batch_size=a.batch_size,
        learning_rate=a.lr,
        logging_steps=20,
        save_strategy="no",
        report_to=[],
        seed=SEED,
        data_seed=SEED,
    )
    trainer = WeightedTrainer(model=model, args=args,
                              train_dataset=RouterDataset(train_idx))
    trainer.train()

    # Held-out evaluation (the Gate AR-1 numbers).
    model.eval()
    held = RouterDataset(held_idx)
    preds, gold = [], []
    with torch.no_grad():
        for i in range(0, len(held), a.batch_size):
            batch = {k: torch.stack([held[j][k] for j in range(i, min(i + a.batch_size, len(held)))])
                     for k in ("input_ids", "attention_mask")}
            logits = model(**batch).logits
            preds += logits.argmax(dim=-1).tolist()
    gold = [labels[i] for i in held_idx]
    acc = float(np.mean([p == g for p, g in zip(preds, gold)]))
    per_class = {}
    for k in range(3):
        idx = [j for j, g in enumerate(gold) if g == k]
        per_class[ID_TO_LABEL[k]] = (float(np.mean([preds[j] == gold[j] for j in idx]))
                                     if idx else None)
    maj = max(Counter(gold).values()) / len(gold)
    print(f"held-out accuracy: {acc:.4f} (majority-class rate: {maj:.4f})")
    print(f"per-class accuracy: {per_class}")

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)
    metadata = {
        "model": "distilbert-base-uncased",
        "task": "adaptive-rag complexity router (A/B/C)",
        "training_file": str(Path(a.train_file).relative_to(REPO)),
        "n_train_total": len(rows),
        "class_counts": dict(counts),
        "held_out_n": len(held_idx),
        "held_out_accuracy": acc,
        "per_class_accuracy": per_class,
        "majority_class_rate": maj,
        "hyperparameters": {"epochs": a.epochs, "batch_size": a.batch_size,
                            "lr": a.lr, "max_len": a.max_len, "seed": SEED,
                            "class_weights": weights.tolist()},
        "date": str(date.today()),
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    print(f"artifact written to {out_dir}")


if __name__ == "__main__":
    main()
