"""
chat_agent.py
-------------
The Chat feature's entry point. Unlike Deep Research (fixed 2-stage
pipeline) and Terminal (12 fixed single-purpose agents), Chat is ONE
agent with access to every available tool, that decides for itself
which tools are relevant to a given open-ended question — comparisons,
philosophy-based evaluations, portfolio construction, and anything else
that doesn't fit a predetermined research template.

Every turn:
    1. Create a new conversation if none was given ("New Chat")
    2. Save the user's message to Postgres immediately (durable, even
       if everything downstream fails)
    3. Load this conversation's memory (rolling summary + recent
       messages) via database/memory.py's sliding-window logic
    4. Run the agent — tool-call events streamed first, then the
       response tokens, with full retry-and-restream on empty output
    5. Save the assistant's reply to Postgres
    6. Bump the conversation's updated_at (sidebar ordering)
    7. If this conversation has no title yet, generate one now and
       emit it as its own event so a frontend can update the sidebar
       immediately without a page reload

Model instantiation follows the same per-request factory pattern as
Deep Research and Terminal: get_model(response_style) builds a fresh
ChatOllama with the resolved temperature, rather than one fixed
module-level instance.
"""

import asyncio
import os
import uuid
from functools import lru_cache
from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langgraph.errors import GraphRecursionError
from dotenv import load_dotenv

from .response_style import resolve_temperature, RESPONSE_STYLES, DEFAULT_RESPONSE_STYLE
from .database.memory import (
    create_conversation,
    get_conversation,
    save_message,
    build_llm_context,
    touch_conversation,
    set_conversation_title,
    get_user_conversations,
)
from .database.titles import generate_title

from .tool_set.chat_tools import (
    resolve_ticker_symbol,
    get_income_statement,
    get_balance_sheet,
    get_cash_flow,
    get_company_overview,
    get_key_metrics,
    get_stock_quote,
    get_price_history,
    get_share_statistics,
    get_stock_peers,
    get_dividend_history,
    tavily,
    generate_chart,
)

load_dotenv()


@lru_cache(maxsize=3)
def get_model(response_style: str = DEFAULT_RESPONSE_STYLE) -> ChatOllama:
    """
    Builds a ChatOllama instance for the requested Response Style.

    Cached via lru_cache: only 3 possible response_style values exist,
    so each of the 3 instances is built at most once per process and
    reused by every subsequent chat turn asking for that same style —
    across all users and all conversations. Avoids rebuilding the
    underlying HTTP client's connection pool on every single turn, so
    concurrent chat requests reuse a warm, already-connected client.
    Temperature is passed per-call, not mutated on the shared instance,
    so this is safe under concurrent async use.
    """
    temperature = resolve_temperature(response_style)
    return ChatOllama(
        model="gpt-oss:120b",
        temperature=temperature,
        base_url="https://ollama.com",
        num_ctx=32000,
    )


# LangGraph counts one "step" per node visit, so a tool round costs two
# (model → tool). Chat is the most open-ended surface — a multi-company
# comparison can legitimately call a dozen-plus tools in one turn, well past
# LangGraph's default limit of 25. High enough never to interrupt real work;
# low enough to stop a genuine loop.
RECURSION_LIMIT = 60


CHAT_TOOLSET = [
    resolve_ticker_symbol,
    get_income_statement,
    get_balance_sheet,
    get_cash_flow,
    get_company_overview,
    get_key_metrics,
    get_stock_quote,
    get_price_history,
    get_share_statistics,
    get_stock_peers,
    get_dividend_history,
    tavily,
    generate_chart,
]


def _load_prompt(file_name: str) -> str:
    base_path = os.path.join(os.path.dirname(__file__), "system_prompts")
    file_path = os.path.join(base_path, file_name)
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


CHAT_BASE_PROMPT = _load_prompt("chat_agent.txt")


def _build_system_prompt(summary: str | None) -> str:
    """
    Combines the base chat system prompt with this conversation's rolling
    summary (if one exists yet). Done per-turn rather than once, since
    the summary text changes as the conversation grows.
    """
    if not summary:
        return CHAT_BASE_PROMPT
    return (
        f"{CHAT_BASE_PROMPT}\n\n"
        f"════════════════════════════════════════\n"
        f"SUMMARY OF EARLIER CONVERSATION\n"
        f"════════════════════════════════════════\n"
        f"{summary}"
    )


# ═══════════════════════════════════════════════════════════════════
# MAIN STREAMING ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

async def chat_turn_stream(user_id: uuid.UUID, conversation_id: uuid.UUID | None,
                            user_message: str, response_style: str = DEFAULT_RESPONSE_STYLE,
                            max_retries: int = 4):
    """
    Runs one full chat turn, streaming events the entire way.

    Args:
        user_id: whichever user_id the caller's auth layer supplies.
            No auth system exists yet in this project — this parameter
            is accepted as-is and simply stored on the conversation row.
        conversation_id: None to start a new conversation, or an
            existing conversation's id to continue it.
        response_style: "precise" | "balanced" | "exploratory".

    Yields:
        {"type": "conversation_created", "conversation_id": <uuid str>}
        {"type": "tool_start", "tool": <name>}
        {"type": "tool_end",   "tool": <name>}
        {"type": "retry", "attempt": n, "max_retries": max_retries}
        {"type": "token", "content": <chunk of text>}
        {"type": "title_generated", "conversation_id": <uuid str>, "title": <str>}
        {"type": "done", "conversation_id": <uuid str>, "content": <full reply text>}
        {"type": "failed", "conversation_id": <uuid str>, "content": <error message>}
    """
    is_new_conversation = conversation_id is None
    if is_new_conversation:
        conversation_id = await create_conversation(user_id)
        yield {"type": "conversation_created", "conversation_id": str(conversation_id)}

    # Saved immediately and durably — this survives even if everything
    # below fails (network error, model outage, etc.).
    await save_message(conversation_id, "user", user_message)

    context = await build_llm_context(conversation_id)
    system_prompt = _build_system_prompt(context["summary"])

    model = get_model(response_style)
    agent = create_agent(model=model, tools=CHAT_TOOLSET, system_prompt=system_prompt)
    agent_input = {"messages": context["messages"]}

    final_content = ""
    succeeded = False

    for attempt in range(1, max_retries + 1):

        if attempt > 1:
            print(f"[chat_agent] Empty content, retrying... (attempt: {attempt}/{max_retries})")
            yield {"type": "retry", "attempt": attempt, "max_retries": max_retries}

        final_content = ""
        hit_step_limit = False

        try:
            async for event in agent.astream_events(
                agent_input,
                version="v2",
                config={"recursion_limit": RECURSION_LIMIT},
            ):
                kind = event["event"]

                if kind == "on_tool_start":
                    yield {"type": "tool_start", "tool": event["name"]}

                elif kind == "on_tool_end":
                    yield {"type": "tool_end", "tool": event["name"]}

                    # Unlike Deep Research and Terminal (which batch charts
                    # from whichever data tools happened to run), Chat's
                    # chart tool is explicitly LLM-driven — the moment the
                    # model calls generate_chart, its artifact is captured
                    # and streamed immediately as its own event, interleaved
                    # naturally with the rest of the turn, rather than held
                    # until the end. Wrapped defensively so an unexpected
                    # event shape here can never break the chat turn.
                    if event["name"] == "generate_chart":
                        try:
                            output = event["data"].get("output")
                            artifact = getattr(output, "artifact", None)
                            if artifact is not None:
                                yield {"type": "chart", "chart": artifact}
                            else:
                                content = getattr(output, "content", None)
                                yield {
                                    "type": "chart",
                                    "error": str(content) if content else "Chart generation failed.",
                                }
                        except Exception as e:
                            print(f"[chat_agent] Could not capture chart artifact: {e}")

                elif kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        final_content += chunk.content
                        yield {"type": "token", "content": chunk.content}

        except GraphRecursionError:
            # A stuck tool-calling loop, not a transient empty response —
            # retrying the identical turn would stick the same way.
            print(f"[chat_agent] Hit the {RECURSION_LIMIT}-step limit.")
            hit_step_limit = True

        if hit_step_limit:
            message = (
                "I kept calling data tools without reaching an answer and stopped after "
                f"{RECURSION_LIMIT} steps. This usually means a data source kept returning "
                "unusable results. Try asking again, or narrow the question to fewer companies."
            )
            # Saved like any other reply so the conversation stays coherent
            # on reload, rather than showing a user message with nothing after it.
            await save_message(conversation_id, "assistant", message)
            await touch_conversation(conversation_id)
            yield {"type": "failed", "conversation_id": str(conversation_id), "content": message}
            return

        if final_content.strip():
            succeeded = True
            break

    if not succeeded:
        error_message = f"Error: chat_agent failed to produce a response after {max_retries} attempts."
        print(f"[chat_agent] All {max_retries} attempts failed.")
        yield {"type": "failed", "conversation_id": str(conversation_id), "content": error_message}
        return

    await save_message(conversation_id, "assistant", final_content)
    await touch_conversation(conversation_id)

    # Generate a title the first time this conversation completes a
    # full exchange — checked via the DB row rather than only
    # `is_new_conversation`, so a conversation that somehow still has
    # no title (e.g. earlier title generation failed) gets another
    # chance on a later turn too.
    convo = await get_conversation(conversation_id)
    if convo and not convo.title:
        title = await generate_title(user_message)
        await set_conversation_title(conversation_id, title)
        yield {"type": "title_generated", "conversation_id": str(conversation_id), "title": title}

    yield {"type": "done", "conversation_id": str(conversation_id), "content": final_content}


# ═══════════════════════════════════════════════════════════════════
# TERMINAL DEMO
# Multi-turn: stays in one conversation across messages, "/new" starts
# a fresh one, "exit"/"quit" stops. NOTE: this requires a live
# PostgreSQL instance reachable via DATABASE_URL — none is provisioned
# in this environment, so this demo is ready to run but untested here.
# ═══════════════════════════════════════════════════════════════════

async def main():
    from .database.db import init_db

    print("Initializing database connection...")
    await init_db()

    # No auth layer exists yet — using a fixed placeholder user_id for
    # local testing. Replace with a real authenticated user_id once an
    # auth layer exists.
    user_id = uuid.uuid4()
    conversation_id = None

    print(f"\nHi, I'm StockAgent Chat. (test user_id: {user_id})")
    print("Type '/new' to start a new conversation, 'exit' or 'quit' to stop.\n")

    response_style = input(
        f"Response style [{'/'.join(RESPONSE_STYLES.keys())}] "
        f"(Enter for {DEFAULT_RESPONSE_STYLE}): "
    ).strip().lower() or DEFAULT_RESPONSE_STYLE

    while True:
        user_message = input("\nYou: ").strip()

        if user_message.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        if user_message.lower() == "/new":
            conversation_id = None
            print("Started a new conversation.")
            continue

        print()
        async for event in chat_turn_stream(user_id, conversation_id, user_message, response_style):
            etype = event["type"]

            if etype == "conversation_created":
                conversation_id = uuid.UUID(event["conversation_id"])

            elif etype == "tool_start":
                print(f"🔧 Calling {event['tool']}...")

            elif etype == "tool_end":
                print(f"✓ {event['tool']} completed.")

            elif etype == "retry":
                print(f"🔁 Retrying... (attempt {event['attempt']}/{event['max_retries']})")

            elif etype == "chart":
                if "chart" in event:
                    print(f"\n📊 Chart ready: {event['chart'].get('chart_type', 'unknown')}\n")
                else:
                    print(f"\n⚠ Chart error: {event.get('error')}\n")

            elif etype == "token":
                print(event["content"], end="", flush=True)

            elif etype == "title_generated":
                print(f"\n\n[Conversation titled: \"{event['title']}\"]")

            elif etype == "failed":
                print(f"\n⚠ {event['content']}")

            elif etype == "done":
                print()  # final newline once the streamed reply finishes


if __name__ == "__main__":
    asyncio.run(main())
