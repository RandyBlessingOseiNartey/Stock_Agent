# backend — FastAPI + SSE

A thin transport layer over the three feature packages. It contains **no
business logic**: each router forwards the events a feature's async generator
already yields, verbatim, as Server-Sent Events.

```
backend/
├── main.py              FastAPI app, CORS, guarded DB startup, health
├── deps.py              dev-only auth stub (get_current_user_id)
├── sse.py               one shared EventSourceResponse wrapper
└── routers/
    ├── deep_research.py
    ├── terminal.py
    └── chat.py
```

Run from the **repo root** so the feature packages import correctly:

```bash
uv run uvicorn backend.main:app --reload
```

## Design notes

**`sse.py` is the only place transport concerns live.** It sets
`Cache-Control: no-cache` and `X-Accel-Buffering: no` (without which nginx and
friends buffer the whole stream and the client sees nothing until the end), and
wraps every generator in a try/except so a stream always ends on a clean
terminal event rather than a dangling connection or a raw traceback.

**Startup is guarded.** `init_db()` failing only disables Chat; Deep Research
and Terminal are stateless and keep working. `GET /api/health` reports
`{"status": "ok", "database": true|false}`.

**Validation is minimal by design.** Invalid `response_style` / `risk_appetite`
values are already handled by each feature's own `resolve_*()` fallbacks, so
Pydantic type-checking is enough. The one input rejected up front is
`analysis_type`, which returns **400** with the valid keys — otherwise a typo
would surface as an in-stream "failed" event that reads like a pipeline crash.
Chat's database reads return **503** with a clean JSON message when Postgres is
unreachable.

## Endpoints and event vocabularies

Every event is one SSE `data:` line containing a JSON object with a `type`.

### `POST /api/deep-research/stream`
`{ query, response_style = "balanced", risk_appetite = "moderate" }`

Every event also carries `stage`: `"retriever"` or `"investment_brief"`.

| `type` | Fields | Meaning |
|---|---|---|
| `stage` | `stage`, `status` | A pipeline stage started/ended |
| `tool_start` / `tool_end` | `tool` | Data tool boundary |
| `retry` | `attempt`, `max_retries` | Empty model response, retrying |
| `chart` | `tool` + (`chart` \| `error`) | Chart ready, or that one chart failed |
| `retriever_done` | `content` | Internal JSON — **do not render raw** |
| `retriever_failed` | `content` | Terminal; stage 2 is skipped |
| `token` | `content` | One chunk of brief text |
| `brief_done` | `content` | Full brief, complete |

### `GET /api/terminal/analyses`
Returns `[{ key, description, tools }]` for the 12-card grid.

### `POST /api/terminal/stream`
`{ analysis_type, company_input, response_style = "balanced" }`

| `type` | Fields |
|---|---|
| `tool_start` / `tool_end` | `tool` |
| `retry` | `attempt`, `max_retries` |
| `chart` | `tool` + (`chart` \| `error`) — fires once, at the tool→writing boundary |
| `token` | `content` |
| `done` / `failed` | `content` |

### Chat
`GET /api/chat/conversations` · `GET /api/chat/conversations/{id}/messages` ·
`POST /api/chat/stream` with `{ conversation_id, message, response_style }`.
All take `X-User-Id`.

| `type` | Fields |
|---|---|
| `conversation_created` | `conversation_id` — only when starting with `null` |
| `tool_start` / `tool_end` | `tool` |
| `retry` | `attempt`, `max_retries` |
| `chart` | `chart` \| `error` — immediate, not batched |
| `token` | `content` |
| `title_generated` | `conversation_id`, `title` |
| `done` / `failed` | `conversation_id`, `content` |

## Authentication

`deps.py` is a **stub, not authentication**: it reads `X-User-Id` if present
and valid, else falls back to a fixed development UUID. Anyone can claim any
user. Deep Research and Terminal don't use identity at all. Replace before
deploying, and add ownership checks to the chat-history endpoints.

## Step limits

Each feature passes an explicit `recursion_limit` to `astream_events`
(LangGraph's default of 25 is too low — the Deep Research retriever alone needs
~21 steps for its 10 tools). Hitting the ceiling yields a readable `failed`
event instead of a raw `GraphRecursionError`, and is **not** retried: a stuck
tool-calling loop would stick again.
