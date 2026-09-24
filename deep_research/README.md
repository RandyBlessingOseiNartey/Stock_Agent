# deep_research — the investment brief pipeline

One query in, one 13-section investment brief out. **Fully deterministic:**
every run calls all 10 tools.

```
deep_research/
├── agent.py                    entry point — run_pipeline_stream()
├── response_style.py           precise / balanced / exploratory → temperature
├── risk_appetite.py            conservative / moderate / aggressive
├── chart_data.py               raw tool output → Plotly-ready JSON (pure)
├── system_prompts/
│   ├── retriever_agent.txt
│   └── investment_brief_agent.txt
└── tool_set/                   10 tools + peers sub-agent + web search
```

## The two stages

**Stage 1 — Retriever.** Gathers everything through the toolset and returns
structured JSON. Its prose is never shown; only its *tool activity* is streamed,
because its job is data collection, not narration. Chart artifacts are captured
here and emitted as one batch when the stage completes — always before stage 2
writes a single token.

**Stage 2 — Investment Brief.** No tools. Pure reasoning and writing over stage
1's JSON, streamed token by token. This is the only stage that knows about
**risk appetite**: `_build_investment_brief_prompt()` appends a directive
naming which of the three frameworks (already written out in Section 7 of
`investment_brief_agent.txt`) to apply.

If the retriever fails after all retries, the pipeline **stops** — it does not
hand an error string to the brief agent, which would otherwise write a report
with no data behind it.

## Run it standalone

```bash
# from the repo root
uv run python -m deep_research.agent
```

`run_pipeline_stream(query, response_style, risk_appetite)` is an async
generator of event dicts; `main()` at the bottom of `agent.py` is just one
example consumer that prints to stdout. The FastAPI layer consumes the same
generator. Event table: [`../backend/README.md`](../backend/README.md).

## Notes

- `get_model()` is `@lru_cache(maxsize=3)`d — at most one model instance per
  response style per process, so concurrent requests reuse a warm HTTP
  connection pool instead of rebuilding one per call.
- Retries re-emit the **full** tool-call trace; a retry is never silent.
- `get_stock_peers` runs its own nested agent internally. That sub-agent's tool
  calls do **not** appear in the stream — from outside it's one tool call.
- This package has no `get_price_history`, so `build_chart_batch()` simply
  skips that chart type.
