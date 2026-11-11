"""Prompt definitions and message formatters for LLM generation."""

import logging

logger = logging.getLogger(__name__)

ANSWER_SYSTEM = (
    "Answer the question using only the context. Reply with only the short answer, "
    "no explanation. If the context does not contain the answer, reply exactly: unknown"
)

# Tune-unknown-prompt (step 3): pre-registered reader variants behind
# erag.unknown_prompt (default "base"). Exact texts from
# openspec/changes/tune-unknown-prompt/design.md. "best_guess" separates
# "not in context" from "uncertain"; "cite_first" locates the most
# relevant sentence before answering.
BEST_GUESS_SYSTEM = (
    "Answer the question using only the context. Reply with only the short "
    "answer, no explanation. If the context contains evidence relevant to the "
    "question, give your best short answer from that evidence even if you are "
    "not certain. Reply exactly 'unknown' only if the context contains nothing "
    "relevant to the question."
)

CITE_FIRST_SYSTEM = (
    "Answer the question using only the context. First identify the single "
    "sentence in the context most relevant to the question, then reply with "
    "only the short answer from that sentence, no explanation. If no sentence "
    "in the context is relevant to the question, reply exactly: unknown"
)

UNKNOWN_PROMPT_SYSTEMS = {
    "base": ANSWER_SYSTEM,
    "best_guess": BEST_GUESS_SYSTEM,
    "cite_first": CITE_FIRST_SYSTEM,
}

GROUNDED_ANSWER_SYSTEM = (
    "Answer the question using the verified claims first, then the context. "
    "Reply with only the short answer, no explanation. If neither the claims "
    "nor the context contain the answer, reply exactly: unknown"
)


def context_block(paras: list) -> str:
    """Format a list of paragraph dicts into a numbered context block."""
    return "\n\n".join(
        f"[{i+1}] {p['title']}: " + (" ".join(p["sentences"]) if isinstance(p.get("sentences"), list) else p.get("text", ""))
        for i, p in enumerate(paras)
    )


def answer_messages(question: str, paras: list, variant: str = "base") -> list:
    """Messages for context-grounded short-answer question answering.

    `variant` selects the reader system prompt ("base", "best_guess", or
    "cite_first", step 3). An unknown variant name falls back to "base"
    (logged, not an error — a typo must not crash a run).
    """
    system = UNKNOWN_PROMPT_SYSTEMS.get(variant)
    if system is None:
        logger.warning("unknown unknown_prompt variant %r, falling back to 'base'", variant)
        system = ANSWER_SYSTEM
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": f"Context:\n{context_block(paras)}\n\nQuestion: {question}\nAnswer:",
        },
    ]


def grounded_answer_messages(question: str, claims: list, paras: list) -> list:
    """Messages for a claim-grounded re-read: verified claims first, then context.

    `claims` are belief-graph Claim objects (or dicts) with a `text` field;
    only supported claims should be passed in by the caller.
    """
    claims_block = "\n".join(
        f"[{i + 1}] {c.text if hasattr(c, 'text') else c.get('text', '')}"
        for i, c in enumerate(claims)
    )
    return [
        {"role": "system", "content": GROUNDED_ANSWER_SYSTEM},
        {
            "role": "user",
            "content": f"Verified claims:\n{claims_block}\n\nContext:\n{context_block(paras)}\n\nQuestion: {question}\nAnswer:",
        },
    ]


CONTESTED_ANSWER_SYSTEM = (
    "Some verified claims support the current answer and others support a "
    "different answer — the claims disagree. Decide which answer is best "
    "supported by the context. Reply with only the short answer, no "
    "explanation. If neither side is supported by the context, reply "
    "exactly: unknown"
)


def contested_answer_messages(question: str, agreeing: list, disagreeing: list,
                              paras: list) -> list:
    """Messages for a contested-claim re-read (Phase 2.5 H12).

    `agreeing` are supported draft-sourced claims containing the draft;
    `disagreeing` are supported question-sourced claims that do not. Both
    are Claim objects (or dicts) with a `text` field. The two sides are
    listed under separate headings so the reader decides by the evidence
    rather than repeating the draft.
    """
    agree_block = "\n".join(
        f"[{i + 1}] {c.text if hasattr(c, 'text') else c.get('text', '')}"
        for i, c in enumerate(agreeing)
    )
    disagree_block = "\n".join(
        f"[{i + 1}] {c.text if hasattr(c, 'text') else c.get('text', '')}"
        for i, c in enumerate(disagreeing)
    )
    return [
        {"role": "system", "content": CONTESTED_ANSWER_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Claims supporting the current answer:\n{agree_block}\n\n"
                f"Claims supporting a different answer:\n{disagree_block}\n\n"
                f"Context:\n{context_block(paras)}\n\nQuestion: {question}\nAnswer:"
            ),
        },
    ]


SUPPORT_RANKED_SYSTEM = (
    "Answer only from the verified claims below — they are the strongest "
    "verified evidence. Reply with only the short answer, no "
    "explanation. If none of the claims supports an answer, reply "
    "exactly: unknown"
)


def support_ranked_answer_messages(question: str, top_claims: list,
                                   paras: list) -> list:
    """Messages for a support-ranked re-read (Phase 2.6 H15).

    `top_claims` are the top-k supported claims by `eff`. Only these
    claims are listed, so the reader chooses by the strongest verified
    evidence rather than repeating the draft. Items are Claim objects
    (or dicts) with a `text` field.
    """
    claims_block = "\n".join(
        f"[{i + 1}] {c.text if hasattr(c, 'text') else c.get('text', '')}"
        for i, c in enumerate(top_claims)
    )
    return [
        {"role": "system", "content": SUPPORT_RANKED_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Strongest verified claims:\n{claims_block}\n\n"
                f"Context:\n{context_block(paras)}\n\nQuestion: {question}\nAnswer:"
            ),
        },
    ]


EXTRACTIVE_SYSTEM = (
    "Answer only from the verified claims below. Reply with only the "
    "short answer, no explanation. If none of the claims supports an "
    "answer, reply exactly: unknown"
)


def extractive_answer_messages(question: str, claims: list) -> list:
    """Messages for an extractive final read (Phase 2.7 H19).

    `claims` are supported claims (Claim objects or dicts) with a `text`
    field. The user message carries ONLY the claims block — deliberately
    NO context block, unlike `support_ranked_answer_messages()`. The
    restriction is the mechanism: the reader cannot fall back to raw
    context, so the answer must come from a verified claim.
    """
    claims_block = "\n".join(
        f"[{i + 1}] {c.text if hasattr(c, 'text') else c.get('text', '')}"
        for i, c in enumerate(claims)
    )
    return [
        {"role": "system", "content": EXTRACTIVE_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Verified claims:\n{claims_block}\n\n"
                f"Question: {question}\nAnswer:"
            ),
        },
    ]


CLOSED_BOOK_SYSTEM = (
    "Answer the question with only a short answer, no explanation. If you do not know, reply exactly: unknown"
)


def closed_book_messages(question: str) -> list:
    """Messages for closed-book question answering without context."""
    return [
        {"role": "system", "content": CLOSED_BOOK_SYSTEM},
        {"role": "user", "content": f"Question: {question}\nAnswer:"},
    ]

