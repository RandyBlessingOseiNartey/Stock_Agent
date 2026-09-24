"""
main.py
-------
The single FastAPI application wrapping all three StockAgent feature
pipelines behind SSE streaming endpoints.

Run from the repo root:
    uvicorn backend.main:app --reload
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import chat, deep_research, terminal

load_dotenv()

# Only Chat touches Postgres. Deep Research and Terminal are stateless, so
# a missing or unreachable database degrades Chat alone rather than taking
# the whole app down at startup.
DATABASE_AVAILABLE = False

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global DATABASE_AVAILABLE
    try:
        from chat.database.db import init_db

        await init_db()
        DATABASE_AVAILABLE = True
        print("[startup] Database initialized — Chat is available.")
    except Exception as e:
        print(f"[startup] Could not initialize database — Chat will be unavailable: {e}")
    yield


app = FastAPI(title="StockAgent API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(deep_research.router)
app.include_router(terminal.router)
app.include_router(chat.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "database": DATABASE_AVAILABLE}


# In a deployed container the built frontend is copied to backend/static and
# served from this same app, so the whole demo lives on one origin and CORS
# never applies. In local development this folder doesn't exist — the Vite dev
# server serves the UI and proxies /api to here — so the mount is skipped.
# Mounted last: "/" would otherwise shadow the /api routes above.
_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
    print(f"[startup] Serving the built frontend from {_STATIC_DIR}")
