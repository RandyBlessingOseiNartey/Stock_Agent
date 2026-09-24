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

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/stockagent",
)

# pool_size/max_overflow are conservative starting points for a small
# deployment. Raise these once real concurrent-user load is observed —
# this is the one place connection-pool tuning happens, so scaling up
# later means changing two numbers here, not hunting through the codebase.
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,   # detects and replaces dead connections automatically
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,   # lets us use ORM objects after commit without a re-query
    class_=AsyncSession,
)


async def init_db():
    """
    Creates all tables defined in models.py if they don't already exist.
    Call this once at application startup. Safe to call repeatedly —
    CREATE TABLE IF NOT EXISTS semantics under the hood.
    """
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
