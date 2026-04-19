"""Alembic async env.

Reads DATABASE_URL from Pydantic settings (already normalized to asyncpg),
imports `Base.metadata` from `backend.models.db`, and runs migrations via
`connection.run_sync(do_migrations)`. No `sqlalchemy.url` in alembic.ini.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from backend.config import settings
from backend.models.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Render SQL without a live connection. Useful for `--sql` output."""
    url = settings.database_url_async or settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_migrations_online() -> None:
    # Reuse the same URL-encoding-tolerant parser as the runtime engine so
    # passwords with unescaped `@` work consistently.
    from backend.db.session import _rightmost_at_split

    raw = settings.database_url_async
    if not raw:
        raise RuntimeError(
            "DATABASE_URL is empty — set it in backend/.env before running alembic."
        )
    url = _rightmost_at_split(raw) or raw
    connectable = create_async_engine(
        url,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        },
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_migrations_online())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
