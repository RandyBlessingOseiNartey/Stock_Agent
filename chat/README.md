# chat — open-ended research with memory

One agent, every tool, and a Postgres-backed conversation history. Chat handles
what the fixed pipelines can't: multi-company comparisons, portfolio
construction, "evaluate this using Peter Lynch's philosophy", and follow-up
questions. **Non-deterministic:** the model decides which tools a question
needs, if any.

```
chat/
├── chat_agent.py            entry point — chat_turn_stream()
├── database/
│   ├── models.py            Conversation, Message (SQLAlchemy async)
│   ├── db.py                async engine + session factory
│   ├── memory.py            sliding window + rolling summary
│   └── titles.py            auto-generated conversation titles
├── system_prompts/chat_agent.txt
├── response_style.py
├── chart_data.py
└── tool_set/                13 tools — 12 data/search + generate_chart
```

## One turn, end to end

1. Create the conversation if none was given, emitting `conversation_created`
2. Save the user's message immediately — durable even if everything below fails
3. Build context (rolling summary + recent messages)
4. Run the agent: tool events, charts and reply tokens stream out as they happen
5. Save the reply, bump `updated_at` (sidebar ordering)
6. If the conversation has no title yet, generate one and emit
   `title_generated` so the sidebar updates without a reload

## Memory: what's stored vs what's sent

These are deliberately separate concerns.

**Durable storage** — every message is saved and never deleted or rewritten.
That's the full history the UI shows when you reopen a conversation.

**LLM context** — `build_llm_context()` decides what actually goes to the model
this turn. Past `SLIDING_WINDOW_SIZE` (10) messages, everything older is folded
into a single rolling summary stored on the conversation row (not as a fake
message), regenerated as more messages age out. Tokens sent stay roughly
constant no matter how long the conversation runs — that's the real
scalability lever, not bigger servers.

The window starts smaller than the 20–30 you'd see for a generic chatbot
because these answers are dense with financial data. Easy to raise once real
usage is visible.

## Charts

Chat has its own LLM-callable `generate_chart(symbol, chart_type)` tool. The
model calls it when the user asks for a visual or when it judges one would
help. Its artifact is emitted **immediately** when that call completes, so
charts land inline where they belong — unlike Deep Research and Terminal, which
batch charts because their tool usage is predictable.

## Run it standalone

```bash
# from the repo root — requires a reachable DATABASE_URL
uv run python -m chat.chat_agent
```

`/new` starts a fresh conversation, `exit` quits. Without a database this is
the only feature that won't start; the API degrades Chat alone and keeps the
other two modes working.
