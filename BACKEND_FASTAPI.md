# StockAgent — Backend (FastAPI) Implementation Guide

Read `PROJECT_CONTEXT.md` first. This document tells you exactly how to
wrap the three existing feature pipelines (`deep_research/`, `terminal/`,
`chat/`) behind a single FastAPI application with Server-Sent Events (SSE)
streaming.

---

## Step 0 — Required Import Refactor (do this BEFORE writing any FastAPI code)

### The problem

Every feature folder was designed to be run **directly from inside
itself** (`cd deep_research && uv run agent.py`). Every internal import in
every feature assumes that feature's own folder is the Python path root —
for example, `deep_research/agent.py` does `from response_style import ...`
and `from tool_set.deep_research_agent_tools import ...`, which only
resolve correctly when `deep_research/` itself is on `sys.path`.

A FastAPI backend needs to **import these as Python packages** from one
level up — e.g. `from deep_research.agent import run_pipeline_stream`.
This breaks the existing imports, and the obvious-looking fixes are both
wrong:

- **Do NOT** just insert each feature's folder into `sys.path` at startup.
  All three features have same-named sibling modules —
  `response_style.py`, `chart_data.py`, `config.py`, `peers_agent.py`,
  `tavily_search_tool.py` all exist in all three folders, and Terminal's
  and Chat's `tool_set` subpackage share the literal package name
  `tool_set` too. Python caches imports by module name in `sys.modules`.
  If you put all three folders on `sys.path`, the **second and third
  feature's imports of these same-named modules will silently resolve to
  the first feature's already-cached version instead of their own** —
  a correctness bug that will not throw an error, it will just quietly
  use the wrong file.
- **Do NOT** run each feature as a fully separate microservice/subprocess
  unless you have a specific reason to — it solves the collision problem
  but adds real deployment complexity that isn't needed here.

### The correct fix

Turn each feature folder into a proper Python **package** and convert its
internal sibling imports from absolute to relative. This makes each
feature's modules resolve as `deep_research.response_style`,
`terminal.response_style`, `chat.response_style` — three distinct,
non-colliding fully-qualified names — while still working correctly.

**1. Add an empty `__init__.py` to each of these three folders** (their
subfolders already have one from earlier work):
```
deep_research/__init__.py
terminal/__init__.py
chat/__init__.py
```

**2. Apply this exact import conversion, file by file:**

| File | Change |
|---|---|
| `deep_research/agent.py` | `from response_style import ...` → `from .response_style import ...`<br>`from risk_appetite import ...` → `from .risk_appetite import ...`<br>`from chart_data import ...` → `from .chart_data import ...`<br>`from tool_set.deep_research_agent_tools import (...)` → `from .tool_set.deep_research_agent_tools import (...)` |
| `terminal/registry.py` | `from response_style import ...` → `from .response_style import ...`<br>Each of the 12 `from agents.X_agent import ...` lines → `from .agents.X_agent import ...` |
| `terminal/agents/_shared.py` | `from response_style import ...` → `from ..response_style import ...`<br>`from chart_data import build_chart_batch` → `from ..chart_data import build_chart_batch` |
| `terminal/agents/*.py` (all 12) | `from tool_set.terminal_tools import ...` → `from ..tool_set.terminal_tools import ...`<br>(`from ._shared import ...` is already correct — leave it) |
| `chat/chat_agent.py` | `from response_style import ...` → `from .response_style import ...`<br>`from database.memory import (...)` → `from .database.memory import (...)`<br>`from database.titles import generate_title` → `from .database.titles import generate_title`<br>`from tool_set.chat_tools import (...)` → `from .tool_set.chat_tools import (...)` |
| `chat/database/memory.py` | `from response_style import resolve_temperature` (inside `_summarize_messages`) → `from ..response_style import resolve_temperature` |
| `chat/database/titles.py` | `from response_style import resolve_temperature` → `from ..response_style import resolve_temperature` |
| `chat/tool_set/chat_tools.py` | `from chart_data import (...)` → `from ..chart_data import (...)` |

Everything inside each `tool_set/` package (`config.py`, `peers_agent.py`,
`tavily_search_tool.py`, and each feature's own `*_tools.py`) already uses
correct single-dot relative imports — **do not touch those.**

**3. Consequence for standalone testing:** each feature's own terminal
demo now must be run as a module, from the **repo root**, not from inside
the feature folder:
```bash
# Old (no longer works after this refactor):
cd deep_research && uv run agent.py

# New:
python -m deep_research.agent
python -m terminal.registry
python -m chat.chat_agent
```
Update any local run instructions/scripts accordingly.

**Do this refactor completely before writing a single line of FastAPI
code.** Verify each feature's own standalone demo still runs correctly
(via the `python -m` form above) before moving on — this proves the
refactor didn't break anything.

---

## 1. Recommended Backend Structure

```
stockAgent1/
├── deep_research/          (existing, now with __init__.py + relative imports)
├── terminal/               (existing, now with __init__.py + relative imports)
├── chat/                   (existing, now with __init__.py + relative imports)
└── backend/
    ├── main.py             ← FastAPI app, CORS, startup, router mounting
    ├── deps.py             ← auth stub dependency (see Section 2)
    └── routers/
        ├── deep_research.py
        ├── terminal.py
        └── chat.py
```

Run the backend from the **repo root**: `uvicorn backend.main:app --reload`.

---

## 2. Auth — Minimal Stub Only

**Do not build real authentication, sessions, or billing in this pass.**
Implement exactly this and nothing more, with a clearly marked TODO:

```python
# backend/deps.py
import uuid
from fastapi import Header

# TODO: replace with real authentication (JWT / session cookie / OAuth)
# before any production launch. This stub exists only so every downstream
# feature (especially Chat, which requires a user_id for its database
# schema) has something to key off of during development.
_DEV_FALLBACK_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

async def get_current_user_id(x_user_id: str | None = Header(default=None)) -> uuid.UUID:
    """
    Reads a client-supplied X-User-Id header if present and valid;
    otherwise falls back to one fixed placeholder UUID for local
    development. This is NOT authentication — anyone can claim any
    user_id by setting the header. Replace before production.
    """
    if x_user_id:
        try:
            return uuid.UUID(x_user_id)
        except ValueError:
            pass
    return _DEV_FALLBACK_USER_ID
```

Use `Depends(get_current_user_id)` on every Chat endpoint that needs a
`user_id`. Deep Research and Terminal don't need user identity at all —
they have no persistent state.

---

## 3. Dependencies to Add

```bash
uv add fastapi "uvicorn[standard]" sse-starlette python-multipart
# sqlalchemy, asyncpg, python-dotenv, langchain*, openbb, yfinance should
# already be present from earlier work — confirm, don't reinstall blindly.
```

`sse-starlette` provides `EventSourceResponse`, which is cleaner than
hand-rolling `StreamingResponse` with manual `data: ...\n\n` formatting,
and handles client-disconnect cleanup correctly.

---

## 4. Endpoint Design

### 4.1 Deep Research

```
POST /api/deep-research/stream
Body: { "query": str, "response_style": str = "balanced", "risk_appetite": str = "moderate" }
```
Streams every event from `deep_research.agent.run_pipeline_stream(query, response_style, risk_appetite)`, forwarded verbatim as SSE.

**Event vocabulary** (every event also carries a `"stage"` key: `"retriever"` or `"investment_brief"`):

| `type` | Fields | Meaning |
|---|---|---|
| `stage` | `stage`, `status` (`"start"`/`"end"`) | A pipeline stage started or ended |
| `tool_start` | `tool` | A data tool began executing |
| `tool_end` | `tool` | A data tool finished |
| `retry` | `attempt`, `max_retries` | Model returned empty content, retrying |
| `chart` | `tool`, then either `chart` (dict) or `error` (str) | A chart is ready, or failed to build |
| `retriever_done` | `content` | Retriever finished (internal JSON — do not render raw to the user) |
| `retriever_failed` | `content` | Retriever failed after all retries |
| `token` | `content` | One chunk of the investment brief's streamed text |
| `brief_done` | `content` | Full investment brief text, complete |

### 4.2 Terminal

```
GET  /api/terminal/analyses
```
Returns the 12-agent catalogue for rendering the mode's cards. Build this
from `terminal.registry.ANALYSIS_CATALOGUE`:
```python
[
  {"key": k, "description": v["description"], "tools": v["tools"]}
  for k, v in ANALYSIS_CATALOGUE.items()
]
```

```
POST /api/terminal/stream
Body: { "analysis_type": str, "company_input": str, "response_style": str = "balanced" }
```
Streams `terminal.registry.run_analysis_stream(analysis_type, company_input, response_style)`.

**Event vocabulary:**

| `type` | Fields | Meaning |
|---|---|---|
| `tool_start` | `tool` | Data tool began |
| `tool_end` | `tool` | Data tool finished |
| `retry` | `attempt`, `max_retries` | Retrying after empty response |
| `chart` | `tool`, then `chart` or `error` | Chart ready or failed (fires once, at the tool-calling→writing boundary) |
| `token` | `content` | One chunk of the report's streamed text |
| `done` | `content` | Full report text, complete |
| `failed` | `content` | Failed after all retries |

Validate `analysis_type` against `ANALYSIS_CATALOGUE.keys()` before
calling — return a `400` if it's not one of the 12 valid keys, rather than
letting the stream emit its own internal "unknown analysis type" string.

### 4.3 Chat

```
GET  /api/chat/conversations
```
`Depends(get_current_user_id)` → `chat.database.memory.get_user_conversations(user_id)`. Return id, title, updated_at for the sidebar.

```
GET  /api/chat/conversations/{conversation_id}/messages
```
→ `chat.database.memory.get_all_messages(conversation_id)`. Full message history for opening a past conversation.

```
POST /api/chat/stream
Body: { "conversation_id": str | null, "message": str, "response_style": str = "balanced" }
```
`Depends(get_current_user_id)` → streams `chat.chat_agent.chat_turn_stream(user_id, conversation_id, message, response_style)`.

**Event vocabulary:**

| `type` | Fields | Meaning |
|---|---|---|
| `conversation_created` | `conversation_id` | Only fires if the request started with `conversation_id: null` — capture and use for subsequent turns |
| `tool_start` | `tool` | Data tool began |
| `tool_end` | `tool` | Data tool finished |
| `retry` | `attempt`, `max_retries` | Retrying after empty response |
| `chart` | either `chart` or `error` | Fires immediately whenever `generate_chart` is called — not batched |
| `token` | `content` | One chunk of the reply's streamed text |
| `title_generated` | `conversation_id`, `title` | Fires once, after the first exchange in a new conversation completes |
| `done` | `conversation_id`, `content` | Full reply text, complete |
| `failed` | `conversation_id`, `content` | Failed after all retries |

---

## 5. SSE Implementation Pattern

```python
# backend/routers/deep_research.py
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
import json

from deep_research.agent import run_pipeline_stream

router = APIRouter(prefix="/api/deep-research")

class DeepResearchRequest(BaseModel):
    query: str
    response_style: str = "balanced"
    risk_appetite: str = "moderate"

@router.post("/stream")
async def stream_deep_research(payload: DeepResearchRequest):
    async def event_generator():
        try:
            async for event in run_pipeline_stream(
                payload.query, payload.response_style, payload.risk_appetite
            ):
                yield {"data": json.dumps(event)}
        except Exception as e:
            # Defense in depth: the pipeline itself already handles its
            # own errors internally and yields a "failed" event on
            # exhausted retries — this catches anything truly unexpected
            # (e.g. a bug, an OOM, an unhandled provider exception) so
            # the SSE connection always ends with a clean event instead
            # of just dying silently.
            yield {"data": json.dumps({"type": "failed", "content": f"Unexpected server error: {e}"})}

    return EventSourceResponse(event_generator())
```

Apply the identical pattern (try/except around the generator, one final
`failed` event on any uncaught exception) to the Terminal and Chat stream
endpoints.

**Headers/config to set on the FastAPI app** (needed for SSE to work
correctly behind common reverse proxies):
```python
# in main.py, when adding CORS/middleware
# Ensure responses aren't buffered by a proxy — set on EventSourceResponse
# or via middleware: Cache-Control: no-cache, X-Accel-Buffering: no
```

---

## 6. CORS

Frontend will run on a different port/origin during development:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # adjust to your Vite dev port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 7. Startup — Database Initialization

Only Chat needs a database. Guard startup so Deep Research and Terminal
work with zero Postgres dependency:

```python
# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from chat.database.db import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
    except Exception as e:
        print(f"[startup] Could not initialize database — Chat will be unavailable: {e}")
    yield

app = FastAPI(lifespan=lifespan)
```

---

## 8. Required Environment Variables

```
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>
TAVILY_API_KEY=...
GOOGLE_API_KEY=...          # required by peers_agent.py's Gemini model (all 3 copies)
```

Confirm exact env var names already expected by `tavily_search_tool.py`
and `peers_agent.py` in each feature — do not guess new names if a
convention already exists in the code.

---

## 9. Error Handling Philosophy

- Every stream generator wraps its `async for` loop in try/except (Section 5) — an SSE stream should always end with a clean terminal event, never a dangling connection or a raw traceback sent to the client.
- Validate request bodies with Pydantic models (shown above) — invalid `response_style`/`risk_appetite` values are already handled gracefully by each feature's own `resolve_*()` functions (falling back to the default), so you do not need to re-validate those specific fields beyond normal Pydantic type checking.
- For Terminal, do validate `analysis_type` against the known catalogue before invoking the stream (400 on invalid key) — this is the one input the backend should reject early rather than letting the pipeline handle it.
- For Chat, wrap the database calls (`get_user_conversations`, `get_all_messages`) in try/except and return a `503`-style clean JSON error if Postgres is unreachable, rather than a raw SQLAlchemy exception.
- Rate-limit defense is primarily handled inside the tools themselves (2-second pacing before each external API call — see `PROJECT_CONTEXT.md` Section 4). No additional request throttling is required at the FastAPI layer for this pass.

---

## 10. Testing

```bash
# Start the server
uvicorn backend.main:app --reload

# Test Deep Research streaming
curl -N -X POST http://localhost:8000/api/deep-research/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Tesla", "response_style": "balanced", "risk_appetite": "moderate"}'

# Test Terminal catalogue
curl http://localhost:8000/api/terminal/analyses

# Test Chat (first turn — no conversation_id)
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-User-Id: 00000000-0000-0000-0000-000000000001" \
  -d '{"conversation_id": null, "message": "Research Apple", "response_style": "balanced"}'
```
`-N` disables curl's output buffering so you see SSE events arrive live
rather than all at once at the end.
