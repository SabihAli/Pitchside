"""User-facing response helpers for the RAG pipeline."""

REFUSAL_PHRASES = (
    "cannot help you with that",
    "can't help you with that",
    "do not have information",
    "don't have information",
    "do not have any information",
    "don't have any information",
    "does not have information",
    "doesn't have information",
    "no relevant information",
    "no information",
    "could not find information",
    "couldn't find information",
    "could not find any information",
    "couldn't find any information",
    # The draft-generator prompt always tells the model to point users at web
    # search when context is empty, regardless of whether web search was
    # already enabled/attempted. Any draft containing this instruction is a
    # signal to hand off to the flag-aware kb_miss_message() below, rather
    # than let the model's state-unaware wording reach the user verbatim.
    "enable web search",
    "enable **web search**",
)


def kb_miss_message(*, web_search_enabled: bool) -> str:
    base = (
        "I couldn't find information to answer that in your knowledge base "
        "(indexed articles and uploads, mainly covering 2022–2024)."
    )
    if web_search_enabled:
        return (
            f"{base}\n\n"
            "Web search was enabled but still did not return enough to answer this query. "
            "Try rephrasing your question or asking about a specific player, club, or season."
        )
    return (
        f"{base}\n\n"
        "Enable **web search** using the globe icon next to the message box and send "
        "your question again — I can search the web for a more current or broader answer."
    )


def is_kb_refusal(text: str) -> bool:
    lowered = (text or "").lower().strip()
    return any(phrase in lowered for phrase in REFUSAL_PHRASES)


def normalize_kb_miss_response(
    draft: str,
    *,
    web_search_enabled: bool,
    chunks: list,
    tool_results: list | None = None,
) -> str:
    """Replace generic refusals with an explicit KB-gap message and web-search offer."""
    has_tool_context = bool(tool_results)
    if not chunks and not has_tool_context:
        return kb_miss_message(web_search_enabled=web_search_enabled)
    if is_kb_refusal(draft):
        return kb_miss_message(web_search_enabled=web_search_enabled)
    return draft
