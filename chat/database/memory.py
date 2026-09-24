"""
memory.py
---------
Everything related to reading/writing conversation state in Postgres.

Two responsibilities kept deliberately separate:

  1. DURABLE STORAGE — every user/assistant message is saved via
     save_message() and NEVER deleted or rewritten. This is the full
     audit trail a UI uses to render "scroll up and see everything."

  2. LLM CONTEXT — build_llm_context() decides what actually gets sent
     to the model on a given turn. Once a conversation exceeds
     SLIDING_WINDOW_SIZE messages, everything older than the most
     recent window gets folded into a single rolling summary (stored
     on the conversations row, not as a fake message), which is
     regenerated to include yesterday's summary + newly-aged-out
     messages each time the threshold is crossed again. This keeps
     the tokens sent to the model roughly constant no matter how long
     the conversation has been running — the actual scalability lever,
     not just "add more servers."

SLIDING_WINDOW_SIZE = 10 messages (5 user+assistant turns) is a starting
point, not a hard law — this product's answers run dense (financial
data, multi-company comparisons), so we start smaller than the 20-30
message windows you'd see recommended for a generic chatbot. Easy to
raise once real usage patterns are visible.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from .db import AsyncSessionLocal
from .models import Conversation, Message

SLIDING_WINDOW_SIZE = 10


# ─────────────────────────────────────────────────────────────────
# CONVERSATION LIFECYCLE
# ─────────────────────────────────────────────────────────────────

async def create_conversation(user_id: uuid.UUID) -> uuid.UUID:
    """Creates a new, empty conversation ("New Chat") and returns its id."""
    async with AsyncSessionLocal() as session:
        convo = Conversation(user_id=user_id)
        session.add(convo)
        await session.commit()
        await session.refresh(convo)
        return convo.id


async def get_conversation(conversation_id: uuid.UUID) -> Conversation | None:
    """Fetches a single conversation row (used to check title/summary state)."""
    async with AsyncSessionLocal() as session:
        return await session.get(Conversation, conversation_id)


async def get_user_conversations(user_id: uuid.UUID, limit: int = 50) -> list[Conversation]:
    """
    Returns a user's conversations, most recently updated first — this
    is exactly the query that powers a ChatGPT/Claude-style sidebar.
    """
    async with AsyncSessionLocal() as session:
        query = (
            select(Conversation)
            .where(Conversation.user_id == user_id, Conversation.is_archived == False)  # noqa: E712
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        result = await session.execute(query)
        return list(result.scalars().all())


async def touch_conversation(conversation_id: uuid.UUID) -> None:
    """
    Bumps updated_at to now. Called after every assistant turn so the
    sidebar's "most recent first" ordering stays correct. Done as an
    explicit UPDATE rather than relying on the model's onupdate=func.now(),
    since onupdate only fires when the ORM detects a changed column on
    that specific instance — an explicit statement is unambiguous.
    """
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now())
        )
        await session.commit()


async def set_conversation_title(conversation_id: uuid.UUID, title: str) -> None:
    """Sets the auto-generated (or user-edited) title for a conversation."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(title=title)
        )
        await session.commit()


# ─────────────────────────────────────────────────────────────────
# MESSAGE STORAGE (durable — never deleted or rewritten)
# ─────────────────────────────────────────────────────────────────

async def save_message(conversation_id: uuid.UUID, role: str, content: str,
                        tool_calls: list | None = None) -> Message:
    """
    Persists one message. `role` is "user" or "assistant". `tool_calls`
    is an optional audit record of what the agent called this turn —
    stored for debugging/analytics, never replayed back as context.
    """
    async with AsyncSessionLocal() as session:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg


async def get_all_messages(conversation_id: uuid.UUID) -> list[Message]:
    """
    Returns every message in a conversation, in order — this is what a
    UI calls when a user clicks a conversation in the sidebar to open
    it, so they see the complete history regardless of what's been
    folded into the summary for LLM purposes.
    """
    async with AsyncSessionLocal() as session:
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        result = await session.execute(query)
        return list(result.scalars().all())


# ─────────────────────────────────────────────────────────────────
# SUMMARIZATION
# ─────────────────────────────────────────────────────────────────

_SUMMARIZATION_PROMPT_TEMPLATE = """You are compressing an ongoing conversation's older history into a concise running summary for an equity research assistant's memory.

{existing_summary_block}
New messages to fold into the summary:
{new_messages_text}

Write an updated summary that preserves:
- Any companies, tickers, or portfolios discussed
- Any specific numbers, conclusions, or recommendations already given
- Any stated user preferences (risk tolerance, investment goals, style)

Keep it under 150 words. Output ONLY the updated summary text, nothing else."""


async def _summarize_messages(existing_summary: str | None, messages_to_fold: list[Message]) -> str:
    """
    Calls a cheap, low-temperature model to fold a batch of aging-out
    messages (plus the prior summary, if any) into one updated summary.
    Kept as its own function so the model call is easy to swap/mock.
    """
    # Imported lazily rather than at module scope so this module stays
    # importable without pulling in langchain_ollama.
    from ..response_style import resolve_temperature
    from langchain_ollama import ChatOllama

    model = ChatOllama(
        model="gpt-oss:120b",
        temperature=resolve_temperature("precise"),
        base_url="https://ollama.com",
    )

    existing_summary_block = (
        f"Existing summary so far:\n{existing_summary}\n" if existing_summary else ""
    )
    new_messages_text = "\n".join(f"{m.role}: {m.content}" for m in messages_to_fold)

    prompt = _SUMMARIZATION_PROMPT_TEMPLATE.format(
        existing_summary_block=existing_summary_block,
        new_messages_text=new_messages_text,
    )

    response = await model.ainvoke([{"role": "user", "content": prompt}])
    return response.content.strip()


# ─────────────────────────────────────────────────────────────────
# LLM CONTEXT BUILDING — the sliding-window + summarization logic
# ─────────────────────────────────────────────────────────────────

async def build_llm_context(conversation_id: uuid.UUID) -> dict:
    """
    Builds what gets sent to the model this turn.

    Returns:
        {
            "summary": str | None,          # folded-in older history, or None
            "messages": [{"role": .., "content": ..}, ...]   # recent raw turns
        }

    The caller (chat_agent.py) is responsible for combining `summary`
    into the system prompt for this turn and passing `messages` as the
    conversation history — kept as two separate pieces here rather than
    one merged list, since a summary reads more naturally folded into
    system instructions than pretending it was itself a chat turn.
    """
    async with AsyncSessionLocal() as session:
        convo = await session.get(Conversation, conversation_id)

        query = select(Message).where(Message.conversation_id == conversation_id)
        if convo.summarized_through is not None:
            query = query.where(Message.created_at > convo.summarized_through)
        query = query.order_by(Message.created_at)

        result = await session.execute(query)
        unsummarized = list(result.scalars().all())

        if len(unsummarized) > SLIDING_WINDOW_SIZE:
            to_fold = unsummarized[:-SLIDING_WINDOW_SIZE]
            remaining = unsummarized[-SLIDING_WINDOW_SIZE:]

            new_summary = await _summarize_messages(convo.summary, to_fold)

            convo.summary = new_summary
            convo.summarized_through = to_fold[-1].created_at
            await session.commit()

            unsummarized = remaining

        return {
            "summary": convo.summary,
            "messages": [{"role": m.role, "content": m.content} for m in unsummarized],
        }
