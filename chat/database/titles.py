"""
titles.py
---------
Auto-generates a short conversation title from the user's first message
in a new conversation — the same UX pattern as ChatGPT/Claude/Gemini's
sidebar. Uses the same cheap model already powering the rest of this
stack (glm-4.7-flash) with a tiny dedicated prompt, rather than a second
provider — there's no cost/quality reason to introduce another model
just for a 5-word title.
"""

from langchain_ollama import ChatOllama

# Absolute import — see the note in memory.py for why this is not a
# relative import: response_style.py lives at chat/ (this module's
# sibling at the top level), not inside a nested package relative to
# titles.py's own location.
from ..response_style import resolve_temperature

_TITLE_PROMPT_TEMPLATE = """Summarize the following user message as a short chat conversation title.

Rules:
- 5 words or fewer
- No punctuation at the end
- No quotation marks around the title
- Output ONLY the title, nothing else

User message:
{message}"""

_FALLBACK_TITLE_MAX_LENGTH = 50


async def generate_title(first_user_message: str) -> str:
    """
    Generates a short title for a new conversation from its first
    message. Falls back to a truncated version of the message itself
    if the model call fails or returns something unusable — a missing
    or broken title should never block the conversation from being
    created or used.
    """
    try:
        model = ChatOllama(
            model="gpt-oss:120b",
            temperature=resolve_temperature("precise"),
            base_url="https://ollama.com",
        )
        prompt = _TITLE_PROMPT_TEMPLATE.format(message=first_user_message)
        response = await model.ainvoke([{"role": "user", "content": prompt}])
        title = response.content.strip().strip('"').strip("'")

        if title:
            return title

    except Exception as e:
        print(f"[titles] Title generation failed, using fallback: {e}")

    # Fallback: first N characters of the user's own message.
    fallback = first_user_message.strip()
    if len(fallback) > _FALLBACK_TITLE_MAX_LENGTH:
        fallback = fallback[:_FALLBACK_TITLE_MAX_LENGTH].rstrip() + "..."
    return fallback
