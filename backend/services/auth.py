"""Bearer token auth for tool endpoints.

ElevenLabs passes our internal token as a `secret__relay_token` dynamic variable
which the agent configures into the `Authorization: Bearer …` header on every
tool call (`tools_contract.md` §0).
"""

from __future__ import annotations

import hmac
import logging

from fastapi import Header, HTTPException

from backend.config import settings

logger = logging.getLogger("relay.auth")


def require_relay_token(authorization: str | None = Header(default=None)) -> None:
    """FastAPI dep — validates Authorization: Bearer <RELAY_INTERNAL_TOKEN>.

    Constant-time compare. Raises 401 on any failure. Returns None on success
    (the dep is used as a side-effect; handlers don't need the value).
    """
    expected = settings.relay_internal_token
    if not expected:
        # Dev mode with no token configured — allow through with a loud log.
        logger.warning("event=auth_bypass_no_token_configured")
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    token = authorization[len("Bearer "):].strip()
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="invalid_bearer_token")


def require_service_token(x_service_token: str | None = Header(default=None)) -> None:
    """Legacy X-Service-Token dep — kept for callers from the older API_DOCS
    spec. Prefer `require_relay_token` for new endpoints."""
    expected = settings.elevenlabs_service_token
    if not expected:
        logger.warning("event=auth_bypass_no_service_token_configured")
        return
    if not x_service_token or not hmac.compare_digest(x_service_token, expected):
        raise HTTPException(status_code=401, detail="invalid_service_token")


__all__ = ["require_relay_token", "require_service_token"]
