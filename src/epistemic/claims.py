"""Claim decomposition: extract atomic factual claims and dependency indices from generated answers."""

import json
import re
from typing import Any, Dict, List
from src.eval.metrics import normalize_answer
from src.llm.prompts import context_block

CLAIM_SYSTEM = (
    "You list the short factual claims that must be true for an answer to be correct. "
    "Use at most {n} claims. Each claim is one self-contained sentence that names its entities "
    '(no pronouns). Mark exactly one claim that states the final answer with "answer": true. '
    '"depends_on" lists the 0-based indexes of EARLIER claims it relies on. '
    "After the claims that support the given Answer, also list claims from the Context that "
    "answer the Question, including any that disagree with the given Answer or give a different "
    "name, date, or value. Use full names exactly as written in the Context, not shortened forms "
    'from the Answer. Each claim carries a "source": "draft" for claims supporting the given '
    'Answer, "question" for claims from the Context that answer the Question. '
    'Return only JSON: {{"claims": [{{"text": "...", "answer": false, "depends_on": [], "source": "draft"}}]}}'
)


def _parse(raw: str, max_claims: int, default_source: str = "draft") -> List[Dict[str, Any]]:
    """Parse structured JSON claim decomposition from LLM response."""
    if not raw or not isinstance(raw, str):
        return []
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return []
    try:
        rows = json.loads(m.group(0)).get("claims", [])
    except Exception:
        return []

    out: List[Dict[str, Any]] = []
    for r in rows[:max_claims]:
        if not isinstance(r, dict) or not str(r.get("text", "")).strip():
            continue
        # Dependencies must point only to EARLIER claims in the list (enforces DAG acyclicity)
        deps = [
            d for d in r.get("depends_on", [])
            if isinstance(d, int) and 0 <= d < len(out)
        ]
        # "source" is advisory metadata for measurement: "draft" for claims
        # supporting the given answer, "question" for claims from the context
        # that answer the question. Absent or invalid values default to
        # `default_source` ("draft" for the first pass, "question" for the
        # second pass — the second pass only ever adds context claims).
        # Backward compatible with old mock JSON and stored responses.
        source = r.get("source")
        if source not in ("draft", "question"):
            source = default_source
        out.append({
            "text": str(r["text"]).strip(),
            "answer_bearing": bool(r.get("answer")),
            "depends_on": deps,
            "fallback": False,
            "source": source,
        })

    # Ensure at least one claim is marked as the answer-bearing claim
    if out and not any(c["answer_bearing"] for c in out):
        out[-1]["answer_bearing"] = True
    return out


def extract_claims(
    llm: Any,
    question: str,
    answer: str,
    paras: List[dict],
    tracker: Any,
    max_claims: int = 5,
) -> List[Dict[str, Any]]:
    """Prompt the LLM to decompose answer and context into atomic verifiable claims."""
    msgs = [
        {"role": "system", "content": CLAIM_SYSTEM.format(n=max_claims)},
        {
            "role": "user",
            "content": f"Question: {question}\nAnswer: {answer}\nContext:\n{context_block(paras)}\n\nJSON:",
        },
    ]

    raw_response = llm.chat(msgs, tracker, temperature=0.0)
    claims = _parse(raw_response, max_claims)

    if not claims:
        # Fallback to single atomic claim when structured generation fails
        claims = [
            {
                "text": f'The answer to "{question}" is {answer}.',
                "answer_bearing": True,
                "depends_on": [],
                "fallback": True,
                "source": "draft",
            }
        ]
    return claims


SECOND_PASS_SYSTEM = (
    "You already listed claims about this question. List ADDITIONAL short "
    "factual claims from the Context that bear on the Question and are NOT "
    "already covered by the claims below — especially claims stating a name, "
    "date, or value that could be the answer. Each claim is one "
    "self-contained sentence that names its entities (no pronouns). Mark "
    "exactly one claim that states the final answer with \"answer\": true. "
    "\"depends_on\" lists the 0-based indexes of EARLIER claims it relies on. "
    "Use at most {n} claims. Return only JSON: "
    "{{\"claims\": [{{\"text\": \"...\", \"answer\": false, \"depends_on\": [], "
    "\"source\": \"question\"}}]}}"
)


def second_pass_messages(question: str, draft: str, existing_claims: List[Dict[str, Any]],
                         paras: List[dict], max_claims: int = 5) -> List[Dict[str, Any]]:
    """Messages for the coverage-driven second extraction pass (Phase 2.5 H13)."""
    existing_block = "\n".join(
        f"[{i + 1}] {c.get('text', '')}" for i, c in enumerate(existing_claims)
    )
    return [
        {"role": "system", "content": SECOND_PASS_SYSTEM.format(n=max_claims)},
        {
            "role": "user",
            "content": (
                f"Question: {question}\nAnswer: {draft}\n\n"
                f"Claims already listed:\n{existing_block}\n\n"
                f"Context:\n{context_block(paras)}\n\nJSON:"
            ),
        },
    ]


def extract_claims_second_pass(
    llm: Any,
    question: str,
    draft: str,
    paras: List[dict],
    existing_claims: List[Dict[str, Any]],
    tracker: Any,
    max_claims: int = 5,
) -> List[Dict[str, Any]]:
    """Second extraction pass (Phase 2.5 H13): additional claims the first
    pass missed, given the claims already extracted. No fallback claim —
    an empty second pass simply adds nothing."""
    msgs = second_pass_messages(question, draft, existing_claims, paras, max_claims)
    raw_response = llm.chat(msgs, tracker, temperature=0.0)
    return _parse(raw_response, max_claims, default_source="question")


def merge_claims(existing: List[Dict[str, Any]],
                 additional: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge a second-pass claim list into the first-pass list (Phase 2.5 H13,
    pure function). An additional claim whose normalized text matches an
    existing claim is dropped; the rest append in returned order."""
    seen = {normalize_answer(c.get("text", "")) for c in existing}
    merged = list(existing)
    for c in additional:
        key = normalize_answer(c.get("text", ""))
        if key and key not in seen:
            seen.add(key)
            merged.append(c)
    return merged

