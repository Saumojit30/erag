"""Learned continuation policy (tuning step 7, B.1).

A logistic regression on hop-0 features predicting P(hop-0 draft correct);
run_erag CONTINUES iff P < tau, else STOPs. Inference is dependency-free
pure arithmetic (no sklearn in src/) and mirrors the offline training
pipeline exactly: z = intercept + sum(coef_i * (x_i - mean_i) / scale_i),
P = sigmoid(z).

The live feature function hop0_features MUST match
scripts/extract_continuation_training.py extract_features exactly, same
definitions — see tests/test_erag.py::test_policy_features_agree_with_
training_set, which proves agreement row-for-row against the stored
training set (tolerance 1e-9). A live/stored mismatch breaks the
simulation equivalence, so change either definition only together with
the other and the agreement test.
"""

import json
import math
from typing import Any, Dict, List, Optional, Tuple

# Feature names in order, mirroring extract_continuation_training.py
# FEATURES. MODEL_FEATURES is the subset the artifact scores (the training
# script excludes sc_skipped because it duplicates fast_path exactly).
FEATURES = [
    "c0",
    "fast_path",
    "n_supported",
    "n_unresolved",
    "n_contradicted",
    "n_conflict",
    "ab_supported",
    "ab_contradicted",
    "mean_claim_conf",
    "hop0_recall",
    "type_comparison",
    "draft_unknown",
    "sc_skipped",
]
MODEL_FEATURES = [f for f in FEATURES if f != "sc_skipped"]


def load_policy(path: str) -> Dict[str, Any]:
    """Load and validate a continuation-policy artifact.

    Raises FileNotFoundError for a missing file and ValueError for a
    malformed artifact — never silently fall back to static behavior
    (the caller must fail loudly instead).
    """
    try:
        with open(path) as f:
            raw = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"continuation policy artifact not found: {path}"
        ) from None
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"continuation policy artifact is not valid JSON: {path}: {exc}"
        ) from None
    if not isinstance(raw, dict):
        raise ValueError(f"continuation policy artifact must be a JSON object: {path}")
    if raw.get("model") != "logistic_regression":
        raise ValueError(
            f"continuation policy artifact model must be logistic_regression, "
            f"got {raw.get('model')!r}: {path}"
        )
    features = raw.get("features")
    if (
        not isinstance(features, list)
        or not features
        or any(not isinstance(f, str) for f in features)
    ):
        raise ValueError(
            f"continuation policy artifact 'features' must be a non-empty "
            f"list of names: {path}"
        )
    # The coefficients are positional, so the artifact's feature list
    # must be exactly the 12 MODEL_FEATURES in order — a shorter or
    # differently-named list would otherwise score on a wrong subset
    # (silently, or via KeyError) instead of failing loudly here.
    if list(features) != MODEL_FEATURES:
        raise ValueError(
            f"continuation policy artifact 'features' must be exactly "
            f"{MODEL_FEATURES}, got {list(features)}: {path}"
        )
    for key in ("coefficients", "scaler_mean", "scaler_scale"):
        vals = raw.get(key)
        if (
            not isinstance(vals, list)
            or len(vals) != len(features)
            or any(not isinstance(v, (int, float)) for v in vals)
        ):
            raise ValueError(
                f"continuation policy artifact {key!r} must be a list of "
                f"{len(features)} numbers: {path}"
            )
    if any(float(s) == 0.0 for s in raw["scaler_scale"]):
        raise ValueError(
            f"continuation policy artifact 'scaler_scale' must be nonzero: {path}"
        )
    if not isinstance(raw.get("intercept"), (int, float)):
        raise ValueError(
            f"continuation policy artifact 'intercept' must be a number: {path}"
        )
    tau = raw.get("tau")
    if not isinstance(tau, (int, float)) or not (0.0 < float(tau) < 1.0):
        raise ValueError(
            f"continuation policy artifact 'tau' must be a number in (0, 1): {path}"
        )
    return raw


def hop0_features(
    c0: Optional[float],
    c0_source: Optional[str],
    sc_skipped: bool,
    graph_claims: List[Dict[str, Any]],
    pool_titles: List[str],
    supporting_facts: Optional[List],
    question_type: Optional[str],
    hop0_draft: str,
) -> Dict[str, float]:
    """Hop-0 features for the continuation policy, defined EXACTLY as in
    scripts/extract_continuation_training.py extract_features.

    - c0: the hop-0 confidence (0.0 if unset).
    - fast_path / sc_skipped: 1 iff the Fast Path skipped SC.
    - n_supported / n_unresolved / n_contradicted: claim-status counts in
      the hop-0 graph; n_conflict: claims with conflict set.
    - ab_supported / ab_contradicted: any answer-bearing claim with that
      status.
    - mean_claim_conf: mean of claim conf (0.0 if no claims).
    - hop0_recall: supporting-facts recall recomputed from the manifest
      supporting_facts vs the hop-0 pool titles; 0.0 when there are no
      supporting facts (e.g. production runs with no manifest item).
    - type_comparison: 1 iff the question type is "comparison".
    - draft_unknown: 1 iff the HOP-0 draft is exactly the string
      "unknown" (exact match, NOT is_unknown(), NOT the row's final
      draft field — the hop-0 draft is what exists at decision time).
    """
    claims = graph_claims or []
    statuses = [c.get("status") for c in claims]
    ab = [c for c in claims if c.get("answer_bearing")]
    confs = [c.get("conf", 0.0) for c in claims]
    gold = {t for t, _ in (supporting_facts or [])}
    pool = set(pool_titles or [])
    hop0_recall = (len(gold & pool) / len(gold)) if gold else 0.0
    return {
        "c0": float(c0 if c0 is not None else 0.0),
        "fast_path": 1 if c0_source == "fast_path_min_eff" else 0,
        "n_supported": statuses.count("supported"),
        "n_unresolved": statuses.count("unresolved"),
        "n_contradicted": statuses.count("contradicted"),
        "n_conflict": sum(1 for c in claims if c.get("conflict")),
        "ab_supported": 1 if any(c.get("status") == "supported" for c in ab) else 0,
        "ab_contradicted": 1
        if any(c.get("status") == "contradicted" for c in ab)
        else 0,
        "mean_claim_conf": (sum(confs) / len(confs)) if confs else 0.0,
        "hop0_recall": hop0_recall,
        "type_comparison": 1 if question_type == "comparison" else 0,
        "draft_unknown": 1 if hop0_draft == "unknown" else 0,
        "sc_skipped": 1 if sc_skipped else 0,
    }


def policy_probability(artifact: Dict[str, Any], features: Dict[str, float]) -> float:
    """P(hop-0 draft correct) by pure arithmetic from the artifact."""
    z = float(artifact["intercept"])
    for name, coef, mean, scale in zip(
        artifact["features"],
        artifact["coefficients"],
        artifact["scaler_mean"],
        artifact["scaler_scale"],
    ):
        x = float(features[name])
        z += coef * ((x - mean) / scale if scale != 0.0 else 0.0)
    # Numerically stable sigmoid.
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def decide_policy(artifact: Dict[str, Any], features: Dict[str, float]) -> Tuple[str, float]:
    """(decision, P): CONTINUE iff P < tau, else STOP."""
    p = policy_probability(artifact, features)
    return ("continue", p) if p < float(artifact["tau"]) else ("stop", p)
