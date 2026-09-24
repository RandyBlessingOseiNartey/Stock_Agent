"""
db.py
-----
Async SQLAlchemy engine + session factory.

No PostgreSQL instance exists yet in this environment — this module is
written to be correct and ready to point at a real database the moment
one is provisioned, via the DATABASE_URL environment variable. Nothing
here has been run against a live database; treat first use as an
integration test of this file specifically.

Expected DATABASE_URL format (asyncpg driver):
    postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from dotenv import load_dotenv

from .models import Base

load_dotenv()

# Surrounding quotes are stripped: python-dotenv removes them when reading a
# .env file, but a value pasted into a hosting platform's environment-variable
# form (or passed via `docker --env-file`) keeps them, and SQLAlchemy then
# rejects the URL outright.
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip().strip('"').strip("'") or (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/stockagent"
)


def _build_engine():
    """
    Builds the async engine, or returns None if the URL is missing/malformed.

    Deliberately non-fatal: only Chat needs a database. Raising here would
    happen at *import* time and take down Deep Research and Terminal too —
    they'd never even start — which is exactly the failure the guarded startup
    in backend/main.py exists to prevent.

    pool_size/max_overflow are conservative starting points for a small
    deployment. Raise them once real concurrent-user load is observed — this
    is the one place connection-pool tuning happens.
    """
    try:
        return create_async_engine(
            DATABASE_URL,
            echo=False,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,   # detects and replaces dead connections automatically
        )
    except Exception as e:
        print(f"[database] DATABASE_URL is unusable — Chat will be disabled: {e}")
        return None


engine = _build_engine()

if engine is not None:
    AsyncSessionLocal = async_sessionmaker(
        engine,
        expire_on_commit=False,   # lets us use ORM objects after commit without a re-query
        class_=AsyncSession,
    )
else:
    def AsyncSessionLocal(*_args, **_kwargs):
        """Placeholder so callers fail with a clear, catchable error."""
        raise RuntimeError(
            "Chat is unavailable: DATABASE_URL is missing or malformed. "
            "Deep Research and Terminal do not need a database and keep working."
        )


async def init_db():
    """
    Creates all tables defined in models.py if they don't already exist.
    Call this once at application startup. Safe to call repeatedly —
    CREATE TABLE IF NOT EXISTS semantics under the hood.

    Raises if no usable DATABASE_URL was configured; backend/main.py catches
    that and marks Chat unavailable while the other two modes carry on.
    """
    if engine is None:
        raise RuntimeError("No usable DATABASE_URL — cannot initialize the database.")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session():
    """
    Async generator session provider — FastAPI-dependency-friendly.

    Usage inside FastAPI:
        @app.get("/some-route")
        async def route(session: AsyncSession = Depends(get_session)):
            ...

    Usage outside FastAPI (e.g. in memory.py, chat_agent.py):
        async with AsyncSessionLocal() as session:
            ...
    (Use AsyncSessionLocal directly, imported from this module, for
    plain async-with usage — get_session() specifically follows the
    generator-dependency shape FastAPI expects.)
    """
    async with AsyncSessionLocal() as session:
        yield session
