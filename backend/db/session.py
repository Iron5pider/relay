"""Async SQLAlchemy engine + session factory for Postgres (Supabase).

Single module-level engine, lazily instantiated so import-time failures don't
crash the app in mock-only tests. Compatible with Supabase's session pooler
(port 5432) and transaction pooler (port 6543) via `statement_cache_size=0`
+ `prepared_statement_cache_size=0` — asyncpg caches prepared statements per
connection, which pgbouncer's transaction mode rejects.

Public surface:
- `get_engine()` — singleton `AsyncEngine`.
- `AsyncSessionLocal` — `async_sessionmaker` bound to the engine.
- `get_session()` — FastAPI-ready async generator, yields one `AsyncSession`.
- `ping()` — `SELECT 1` with a short timeout; returns bool, never raises.
- `dispose_engine()` — shutdown hook; closes the pool cleanly.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import settings

logger = logging.getLogger("relay.db")

_engine: AsyncEngine | None = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def _rightmost_at_split(raw_url: str) -> "URL | None":
    """Parse a DATABASE_URL that may contain unescaped `@` in the password.

    Supabase and other hosted Postgres services sometimes hand out URLs with
    raw special chars in the password. SQLAlchemy's `make_url` splits on the
    leftmost `@`, which corrupts the host when that character also appears in
    the password. This helper uses the rightmost `@` as the creds/host
    boundary — correct whenever the host is a DNS name (no `@`) — and builds
    a proper `URL` object so the driver receives cleanly-encoded creds.

    Returns `None` if the URL doesn't fit the `postgresql[+asyncpg]://…`
    shape — fall back to the caller's default.
    """
    from sqlalchemy import URL  # local import keeps module import light

    for prefix in ("postgresql+asyncpg://", "postgresql://", "postgres://"):
        if raw_url.startswith(prefix):
            body = raw_url[len(prefix):]
            drivername = "postgresql+asyncpg"
            break
    else:
        return None

    at_idx = body.rfind("@")
    if at_idx == -1:
        return None
    creds, rest = body[:at_idx], body[at_idx + 1:]
    colon_idx = creds.find(":")
    if colon_idx == -1:
        return None
    username, password = creds[:colon_idx], creds[colon_idx + 1:]

    # rest is host[:port]/database[?query]
    path_idx = rest.find("/")
    if path_idx == -1:
        return None
    hostport, dbpath = rest[:path_idx], rest[path_idx + 1:]
    if ":" in hostport:
        host, port_str = hostport.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            return None
    else:
        host, port = hostport, 5432
    # Strip query params — we set asyncpg tuning via connect_args instead.
    database = dbpath.split("?", 1)[0]

    return URL.create(
        drivername=drivername,
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
    )


def _build_engine() -> AsyncEngine:
    raw_url = settings.database_url_async
    if not raw_url:
        raise RuntimeError(
            "DATABASE_URL is empty. Set it in backend/.env "
            "(postgresql://… — the module normalizes to asyncpg)."
        )
    url_obj = _rightmost_at_split(raw_url) or raw_url
    return create_async_engine(
        url_obj,
        pool_size=10,
        max_overflow=0,
        pool_pre_ping=True,
        # Supabase pgbouncer compatibility: disable prepared-statement cache.
        # Works for both the session pooler (:5432) and transaction pooler (:6543).
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        },
    )


def get_engine() -> AsyncEngine:
    global _engine, AsyncSessionLocal
    if _engine is None:
        _engine = _build_engine()
        AsyncSessionLocal = async_sessionmaker(
            _engine, expire_on_commit=False, class_=AsyncSession
        )
        logger.info("event=db_engine_ready url_driver=%s", _engine.url.drivername)
    return _engine


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — yields one AsyncSession per request."""
    get_engine()  # ensures AsyncSessionLocal is populated
    assert AsyncSessionLocal is not None
    async with AsyncSessionLocal() as session:
        yield session


async def ping(timeout_seconds: float = 5.0) -> bool:
    """Cheap DB liveness check for `/health` + startup. Never raises."""
    try:
        get_engine()
    except Exception as exc:  # noqa: BLE001 — engine build errors degrade to False
        logger.warning("event=db_ping_engine_error err=%s", type(exc).__name__)
        return False

    assert AsyncSessionLocal is not None
    try:

        async def _do_ping() -> bool:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
                return True

        return await asyncio.wait_for(_do_ping(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning("event=db_ping_timeout timeout=%s", timeout_seconds)
        return False
    except Exception as exc:  # noqa: BLE001 — any driver error → False
        logger.warning("event=db_ping_error err=%s", type(exc).__name__)
        return False


async def dispose_engine() -> None:
    global _engine, AsyncSessionLocal
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        AsyncSessionLocal = None
        logger.info("event=db_engine_disposed")


__all__ = [
    "AsyncSessionLocal",
    "dispose_engine",
    "get_engine",
    "get_session",
    "ping",
]
