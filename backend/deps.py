"""FastAPI dependency injection. Block-by-block these return real objects.

- `get_adapter` is live as of Block 1.5 (see `services/adapters/__init__.py`).
- `get_anthropic_client` is live as of the anomaly-agent landing (2026-04-19);
  returns None when the key is unset so the rest of the app keeps working.
- `get_db`, `get_bus` remain stubbed until Block 1 / Block 2 land.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

from backend.config import settings
from backend.services.adapters import get_adapter as _get_adapter
from backend.services.adapters.base import NavProAdapter


async def get_db() -> Any:
    raise NotImplementedError("db/session.py lands in Block 1")


def get_adapter() -> NavProAdapter:
    return _get_adapter()


def get_bus() -> Any:
    raise NotImplementedError("bus/publisher.py lands in Block 2")


@lru_cache(maxsize=1)
def get_anthropic_client() -> Optional[Any]:
    """Memoized Anthropic client.

    Returns None when no API key is configured — the anomaly agent treats
    this as "disabled" and degrades gracefully without raising.
    """
    if not settings.anthropic_api_key:
        return None
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
