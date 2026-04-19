"""FastAPI dependency injection.

- `get_db` yields an async SQLAlchemy session from the module-level pool.
- `get_adapter` returns the configured `NavProAdapter`.
- `get_anthropic_client` returns a memoized Anthropic async client
  (or None when the key is unset / SDK is missing).
- `get_bus` lands in Block 2 with the Pusher publisher.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, AsyncIterator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.session import get_session
from backend.services.adapters import get_adapter as _get_adapter
from backend.services.adapters.base import NavProAdapter


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


def get_adapter() -> NavProAdapter:
    return _get_adapter()


def get_bus() -> Any:
    raise NotImplementedError("bus/publisher.py lands in Block 2")


@lru_cache(maxsize=1)
def get_anthropic_client() -> Optional[Any]:
    if not settings.anthropic_api_key:
        return None
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
