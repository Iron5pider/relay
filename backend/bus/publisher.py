"""Pusher HTTP REST publish — fire-and-forget.

If Pusher creds are empty (dev mode), logs a warning and returns.
Never raises — dashboard reconciles via poll on reconnect.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.config import settings

logger = logging.getLogger("relay.bus")

_client: Any = None


def _get_client() -> Any:
    global _client
    if _client is not None:
        return _client

    if not settings.pusher_app_id or not settings.pusher_key or not settings.pusher_secret:
        logger.warning("event=pusher_not_configured reason=missing_credentials")
        return None

    try:
        import pusher  # type: ignore
    except ImportError:
        logger.warning("event=pusher_import_failed reason=pusher_package_not_installed")
        return None

    _client = pusher.Pusher(
        app_id=settings.pusher_app_id,
        key=settings.pusher_key,
        secret=settings.pusher_secret,
        cluster=settings.pusher_cluster,
        ssl=True,
    )
    logger.info("event=pusher_client_ready cluster=%s", settings.pusher_cluster)
    return _client


def publish(channel: str, event: str, payload: dict[str, Any]) -> None:
    """Publish an event to a Pusher channel. Fire-and-forget."""
    client = _get_client()
    if client is None:
        logger.debug("event=publish_skipped channel=%s event=%s reason=no_client", channel, event)
        return

    try:
        client.trigger(channel, event, payload)
        logger.info("event=publish_ok channel=%s event=%s", channel, event)
    except Exception:
        logger.exception("event=publish_failed channel=%s event=%s", channel, event)


__all__ = ["publish"]
