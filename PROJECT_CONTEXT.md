# StockAgent — Project Context

**Read this file first.** It explains what StockAgent is, how the codebase is
organized, and what state the project is in. The other two files —
`BACKEND_FASTAPI.md` and `FRONTEND_REACT.md` — assume you've read this one.

---

## 1. What StockAgent Is

StockAgent is an AI-powered equity research platform. Its purpose: make
real financial due diligence — the kind hedge funds and equity analysts do —
fast and accessible enough that skipping it stops being the easy choice for
a retail investor.

It is **not** a stock-tip generator. Every number it states is retrieved
from a real data tool, not invented by the model. This is enforced
throughout the system prompts and is a non-negotiable product principle:
never let the LLM state a financial figure it didn't actually fetch.

All financial data comes from **100% free data sources** — no paid
providers (no FMP, no Alpha Vantage, no Bloomberg). Everything routes
through [OpenBB](https://openbb.co)'s Python SDK, pinned to free providers
(`yfinance`, `sec`) via each feature's `tool_set/config.py`. This is a
deliberate constraint, not a limitation to work around — it's central to
what makes the product viable to offer cheaply.

---

## 2. The Three Features

StockAgent has three independent product surfaces:

| Feature | What it does | Determinism |
|---|---|---|
| **Deep Research** | One query in → one full 13-section investment brief report out. Fixed 2-stage pipeline: a Retriever agent gathers everything, an Investment Brief agent writes the report. | Fully deterministic — every run calls all 10 of its tools, every time. |
| **Terminal** | 12 specialized single-purpose analysis agents (DCF, Liquidity, Solvency, Valuation, Growth, Volatility, Sentiment, etc.). User picks one agent, gives it a company, gets a focused report on just that dimension. | Deterministic per agent — each agent always calls its own fixed toolset. |
| **Chat** | Open-ended, ChatGPT-style conversational research. One agent with access to every tool, that decides for itself which tools a given question needs. Has persistent multi-turn memory (Postgres). Handles things the other two can't: multi-company comparisons, portfolio construction, "evaluate X using Peter Lynch's philosophy," etc. | Non-deterministic — the LLM chooses which tools to call, if any. |

**Why three separate features instead of one:** Deep Research and Terminal
need predictable, always-the-same-tools behavior because their whole value
is *comprehensive, repeatable* analysis. Chat needs the opposite —
flexibility for questions nobody anticipated. Forcing one architecture to
do both jobs would compromise both.

---

## 3. Current Folder Structure

```
stockAgent1/                     ← repo root
├── deep_research/
│   ├── agent.py                 ← entry point (2-stage pipeline)
│   ├── response_style.py
│   ├── risk_appetite.py
│   ├── chart_data.py
│   ├── system_prompts/
│   │   ├── retriever_agent.txt
│   │   └── investment_brief_agent.txt
│   └── tool_set/
│       ├── config.py
│       ├── deep_research_agent_tools.py   (10 tools)
│       ├── peers_agent.py
│       └── tavily_search_tool.py
│
├── terminal/
│   ├── registry.py              ← entry point (catalogue + demo)
│   ├── response_style.py
│   ├── chart_data.py
│   ├── system_prompts/          ← 12 .txt files, one per agent
│   ├── agents/
│   │   ├── _shared.py           ← model factory + streaming/retry engine
│   │   └── (12 agent .py files, one per analysis type)
│   └── tool_set/
│       ├── config.py
│       ├── terminal_tools.py    (11 tools — same 10 as Deep Research + get_price_history)
│       ├── peers_agent.py
│       └── tavily_search_tool.py
│
└── chat/
    ├── chat_agent.py            ← entry point (1 agent, open toolset, memory)
    ├── response_style.py
    ├── chart_data.py
    ├── system_prompts/
    │   └── chat_agent.txt
    ├── database/
    │   ├── models.py            ← Conversation, Message (SQLAlchemy async)
    │   ├── db.py                ← async engine/session factory
    │   ├── memory.py            ← sliding-window + rolling-summary memory
    │   └── titles.py            ← auto-generated conversation titles
    └── tool_set/
        ├── config.py
        ├── chat_tools.py        (13 tools — 12 data/search tools + generate_chart)
        ├── peers_agent.py
        └── tavily_search_tool.py
```

**Important architectural fact:** `tool_set/`, `response_style.py`, and
`chart_data.py` are **deliberately duplicated** across all three feature
folders — not shared via a common package. This was a conscious choice:
each feature is meant to be fully self-contained and independently
debuggable/deployable, with zero cross-feature import dependencies. When
you touch shared-sounding logic, check whether the same fix needs applying
in all three copies.

Each feature is currently designed to be **run directly from inside its
own folder** (`cd deep_research && uv run agent.py`, etc.) — every
internal import assumes that feature's own folder is the Python path root.
**This has direct consequences for how the FastAPI backend must import
these modules — see "Step 0" at the top of `BACKEND_FASTAPI.md` before
writing any backend code.**

---

## 4. Cross-Cutting Concepts

### Response Style (all three features)
A three-way choice exposed to the end user, mapped internally to LLM
temperature — never exposing raw temperature to the user (see rationale
in each `response_style.py`):

| Style | Temperature | Use case |
|---|---|---|
| `precise` | 0.1 | Numeric-heavy reports where consistency matters most |
| `balanced` | 0.4 | Default |
| `exploratory` | 0.7 | Open-ended strategy questions |

The model instance for each style is built via a `get_model(response_style)`
factory decorated with `@lru_cache(maxsize=3)` — at most 3 model instances
exist per process (one per style), reused across every request, rather
than rebuilt per call. This matters for connection-pool reuse under
concurrent load.

### Risk Appetite (Deep Research only)
A second, independent selector — **only the Investment Brief stage of
Deep Research** uses this; the retriever and Terminal/Chat don't have a
notion of investor risk tolerance.

| Value | Meaning |
|---|---|
| `conservative` | Capital preservation priority |
| `moderate` | **Default.** Balanced growth/preservation |
| `aggressive` | Maximum growth priority |

Defined in `deep_research/risk_appetite.py`. The three frameworks
themselves (what "conservative" actually means in the report) are fully
written out in `investment_brief_agent.txt`'s Section 7 — the code just
tells the model which one to apply for a given run.

### Streaming Architecture
Every feature streams via LangChain's `agent.astream_events(agent_input,
version="v2")` — never a single blocking request/response. Every
entry-point function (`run_pipeline_stream`, `run_analysis_stream`,
`chat_turn_stream`) is an **async generator** yielding small,
JSON-serializable event dicts. This is the format the FastAPI layer needs
to forward over Server-Sent Events, and what the frontend needs to parse.
The exact event vocabulary for each feature is documented in
`BACKEND_FASTAPI.md`.

All three features implement the same retry pattern: if the model returns
empty content, the entire run is retried (up to 4-5 attempts), **re-emitting
the full tool-call trace each time** — a retry is not silent.

### Charts
Charts are never sent into any LLM's context. Each feature's
`chart_data.py` contains pure, synchronous shaping functions (no I/O) that
convert a tool's raw output into Plotly-ready JSON. How the raw data is
captured differs by feature, matching each feature's determinism:

- **Deep Research & Terminal** (deterministic tool usage): chartable tools
  use LangChain's `response_format="content_and_artifact"` — the LLM sees
  the normal stringified data (`content`), while the exact same raw object
  is separately captured as `artifact` during the tool-call's `on_tool_end`
  event, without ever re-entering the model's context. All artifacts
  collected during one run are shaped into a batch of chart events via
  `chart_data.build_chart_batch()`, emitted **once, after all tool calls
  finish, strictly before any report-text token streaming begins.**
  - *Deep Research specifically*: batch fires right when the Retriever
    stage completes (`retriever_done`), before the Investment Brief stage's
    token stream starts.
  - *Terminal specifically*: since each analysis agent interleaves
    tool-calling and writing in one continuous run, the batch fires at the
    exact moment the model's first non-empty text chunk appears (pure
    tool-call turns always produce empty content chunks — this is the
    reliable signal that tool-calling has ended and writing has begun).
- **Chat** (non-deterministic tool usage): has its own explicit,
  LLM-callable tool, `generate_chart(symbol, chart_type)`, using the same
  `content_and_artifact` pattern. The model decides if/when to call it —
  either because the user explicitly asked for a chart, or because the
  model judges one would help. Its artifact is captured and emitted
  **immediately** the moment that specific tool call completes —
  interleaved naturally with the rest of the turn, not batched.

`chart_type` values currently supported (see any `chart_data.py`):
`income_statement`, `balance_sheet`, `cash_flow`, `key_metrics`,
`stock_quote`, `price_history`, `share_statistics`, `stock_peers`,
`dividend_history`. Not every feature can produce every chart type (e.g.
Deep Research has no `price_history` tool) — `build_chart_batch()` simply
skips chart types whose source tool wasn't called.

### Data Tool Error Handling
Every tool wraps its fetch in try/except and returns a human-readable
error string on failure rather than raising — this must never crash an
agent run. A 2-second delay is being added before each tool's actual
external API call (see the rate-limit fix already applied to all three
`tool_set/*_tools.py` files) specifically to avoid tripping Yahoo
Finance's rate limits — the single biggest operational risk this project
has hit repeatedly during development.

---

## 5. Known Gaps, Unverified Assumptions, and Things to Watch

Be honest about these — do not assume they're solved just because code
exists for them:

- **No FastAPI backend exists yet.** This is the task these three docs
  are guiding you toward.
- **No frontend exists yet.**
- **No real authentication exists.** A minimal stub is specified in
  `BACKEND_FASTAPI.md` — a placeholder `user_id`, not a real account
  system. Do not build billing/Stripe/real auth as part of this task.
- **No live PostgreSQL instance has ever been connected.** All of
  `chat/database/` is written to be correct, but has only been
  syntax-checked, never integration-tested against a real database.
  Provision one and test this thoroughly before trusting it.
- **`get_dividend_history`'s exact field names are unverified.** It was
  written against OpenBB's documented schema but never exercised against
  a live call. Test it directly before trusting `shape_dividend_history()`
  in `chart_data.py`.
- **`get_price_history`'s x-axis is intentionally positional, not
  calendar dates** — `1, 2, 3, ...` per trading day, not real dates. This
  was a deliberate decision (the tool has no reliable per-row date field),
  not an oversight — do not "fix" it back to dates without new tooling.
- **Deep Research's model name (`"gemma4"` in `deep_research/agent.py`'s
  `get_model()`) differs from Terminal and Chat's (`"glm-4.7-flash"`).**
  This inconsistency has existed since early in the project and was never
  explicitly confirmed as intentional. Flag this to the project owner
  rather than silently "fixing" it either direction.
- **The Ollama Cloud base URL (`https://ollama.com`) is hardcoded** in
  every `get_model()` factory across all three features, not read from an
  environment variable. Fine for now; worth moving to `.env` eventually.
- **`peers_agent.py` (all three copies) uses `ChatGoogleGenerativeAI`
  (Gemini)**, not the Ollama-hosted model the rest of the project uses —
  this was an earlier design choice for that one nested sub-agent
  specifically and is not a bug, but it does mean a `GOOGLE_API_KEY` (or
  equivalent) environment variable is required for peer-lookup to
  function, separate from whatever credentials Ollama Cloud needs.

---

## 6. Brand Identity

A complete brand system already exists (colors, wordmark, symbol, animated
loader) — fully specified in `FRONTEND_REACT.md`, Section 2. Do not
invent alternate colors, fonts, or loading indicators.

---

## 7. What "Done" Looks Like For This Task

By the end of implementing `BACKEND_FASTAPI.md` and `FRONTEND_REACT.md`,
a user should be able to: open the app (lands on Chat by default), switch
modes via a tab (Chat / Terminal / Deep Research), run any of the three
features end-to-end with live streaming (tool trace → charts → typed-out
report), see the StockAgent brand loader during any pending request, and
have Chat conversations persist and reload correctly. Real auth and
billing are explicitly out of scope for this pass.
