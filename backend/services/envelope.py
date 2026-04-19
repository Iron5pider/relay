"""Response envelope helpers.

Every tool endpoint returns `{ok, data, error}` per `API_DOCS/tools_contract.md` §0.
Webhook responses use the same envelope so callers can uniformly ignore `data`
on `ok=false` and show the LLM-speakable error message.

Public surface:
- `ok(data)` — success envelope.
- `err(code, message, *, http_status=...)` — failure envelope (plain dict; route
  handlers can return this or raise `EnvelopeError` for the exception handler).
- `EnvelopeError` — raise this inside a service/handler to short-circuit with
  a typed error envelope.
- `register_envelope_exception_handler(app)` — wires the FastAPI handler so
  unhandled exceptions become `{ok: false, error: {…}}` 500 responses instead
  of raw HTML tracebacks (which the LLM would speak aloud).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("relay.envelope")


def ok(data: Any = None) -> dict[str, Any]:
    return {"ok": True, "data": data, "error": None}


def err(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "data": None, "error": {"code": code, "message": message}}


class EnvelopeError(Exception):
    """Raise inside a handler to short-circuit with a typed envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def register_envelope_exception_handler(app: FastAPI) -> None:
    @app.exception_handler(EnvelopeError)
    async def _envelope_error_handler(request: Request, exc: EnvelopeError) -> JSONResponse:
        logger.info(
            "event=envelope_error code=%s http_status=%d path=%s",
            exc.code,
            exc.http_status,
            request.url.path,
        )
        return JSONResponse(status_code=exc.http_status, content=err(exc.code, exc.message))

    @app.exception_handler(Exception)
    async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Let FastAPI's own HTTPException handler continue to 404/422 etc.
        # This handler only fires for truly unhandled exceptions.
        logger.exception(
            "event=envelope_unhandled_error path=%s err=%s",
            request.url.path,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content=err("internal_error", "An internal error occurred."),
        )


__all__ = [
    "EnvelopeError",
    "err",
    "ok",
    "register_envelope_exception_handler",
]
