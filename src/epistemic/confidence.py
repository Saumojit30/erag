"""Self-consistency confidence estimation over sampled model completions."""

import math
from collections import Counter
from typing import Any, Dict, List
from src.eval.metrics import normalize_answer
from src.llm.prompts import answer_messages


def _consensus(samples: List[str], draft: str) -> Dict[str, Any]:
    """Consensus statistics for a list of sampled completions."""
    norm_samples = [normalize_answer(s) for s in samples]
    norm_draft = normalize_answer(draft)
    counts = Counter(norm_samples)
    top_answer, top_count = counts.most_common(1)[0]
    n_draft_match = sum(1 for s in norm_samples if s == norm_draft)
    k = len(samples)
    return {
        "majority": top_answer,
        "conf_majority": float(top_count / k),
        "conf_draft_agreement": float(n_draft_match / k),
        "samples": list(samples),
    }


def _entropy(norm_samples: List[str]) -> float:
    """Shannon entropy (natural log) of the normalised-answer distribution."""
    n = len(norm_samples)
    if n <= 1:
        return 0.0
    counts = Counter(norm_samples)
    return -sum((c / n) * math.log(c / n) for c in counts.values())


def self_consistency(
    llm: Any,
    question: str,
    paras: List[dict],
    draft: str,
    tracker: Any,
    k: int = 5,
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """Sample k independent completions at temperature > 0 and calculate consensus confidence."""
    msgs = answer_messages(question, paras)
    samples = [
        llm.chat(
            msgs,
            tracker,
            temperature=temperature,
            sample_idx=i,
        )
        for i in range(k)
    ]

    return _consensus(samples, draft)


def sequential_consistency(
    llm: Any,
    question: str,
    paras: List[dict],
    draft: str,
    tracker: Any,
    k: int = 3,
    temperature: float = 0.7,
    delta_h: float = 0.05,
) -> Dict[str, Any]:
    """Sample completions one at a time, stopping early on consensus.

    TrueAdaptive v1 (Gaps B + C): instead of firing all ``k`` samples at
    once, sample sequentially and stop when either

    * the leading answer has an unassailable majority given the remaining
      budget (e.g. after 2 agreeing samples out of a cap of 3, the leader
      holds at least 2/3 no matter what the third sample says), or
    * the change in answer-distribution entropy ΔH < ``delta_h`` (default
      0.05) after at least 2 samples — another sample is no longer
      changing what we believe.

    ``k`` is a cap (default 3, never 5 in v1), not a fixed count.
    Return shape is identical to :func:`self_consistency`, plus
    ``entropy``, ``entropy_history``, ``n_samples`` and ``stopped_early``
    for diagnostics.
    """
    cap = max(int(k), 1)
    msgs = answer_messages(question, paras)
    samples: List[str] = []
    entropy_history: List[float] = []
    stopped_early = False

    for i in range(cap):
        samples.append(
            llm.chat(
                msgs,
                tracker,
                temperature=temperature,
                sample_idx=i,
            )
        )
        norm = [normalize_answer(s) for s in samples]
        entropy_history.append(_entropy(norm))
        if len(samples) < 2:
            continue
        counts = Counter(norm)
        top_count = counts.most_common(1)[0][1]
        remaining = cap - len(samples)
        # Unassailable majority: even if every remaining sample went to a
        # single rival, the leader still holds more votes than that rival
        # could ever reach (rival max = non-leader samples so far + remaining).
        if top_count > (len(samples) - top_count) + remaining:
            stopped_early = True
            break
        if len(entropy_history) >= 2:
            d_h = abs(entropy_history[-1] - entropy_history[-2])
            if d_h < delta_h:
                stopped_early = True
                break

    out = _consensus(samples, draft)
    out["entropy"] = entropy_history[-1] if entropy_history else 0.0
    out["entropy_history"] = entropy_history
    out["n_samples"] = len(samples)
    out["stopped_early"] = stopped_early
    return out
