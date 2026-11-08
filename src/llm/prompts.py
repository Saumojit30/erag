"""Prompt definitions and message formatters for LLM generation."""

ANSWER_SYSTEM = (
    "Answer the question using only the context. Reply with only the short answer, "
    "no explanation. If the context does not contain the answer, reply exactly: unknown"
)

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


def answer_messages(question: str, paras: list) -> list:
    """Messages for context-grounded short-answer question answering."""
    return [
        {"role": "system", "content": ANSWER_SYSTEM},
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


CLOSED_BOOK_SYSTEM = (
    "Answer the question with only a short answer, no explanation. If you do not know, reply exactly: unknown"
)


def closed_book_messages(question: str) -> list:
    """Messages for closed-book question answering without context."""
    return [
        {"role": "system", "content": CLOSED_BOOK_SYSTEM},
        {"role": "user", "content": f"Question: {question}\nAnswer:"},
    ]

