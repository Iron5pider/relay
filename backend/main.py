"""FastAPI app factory. CORS + request-ID middleware + /health. Block 1 skeleton.

As of 2026-04-19 the lifespan also starts the `checkin_scheduler` task when
`settings.anomaly_agent_enabled = True`. The scheduler runs the tiered
NavPro-poll + Claude reasoning loop per
`API_DOCS/Backend_phase_guide.md` Block 4 Feature 2.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings

logger = logging.getLogger("relay")

_scheduler_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _scheduler_task
    logger.info(
        "event=app_startup environment=%s adapter=%s demo_safe_mode=%s anomaly_agent=%s",
        settings.environment,
        settings.relay_adapter,
        settings.demo_safe_mode,
        settings.anomaly_agent_enabled,
    )

    # DB — ping + seed if empty (local/demo only). Both calls degrade gracefully
    # when DATABASE_URL is unset or Supabase is unreachable; the app still boots.
    from .db import session as db_session

    db_ok = await db_session.ping()
    logger.info("event=db_startup_ping ok=%s", db_ok)
    if (
        db_ok
        and settings.seed_on_startup
        and settings.environment in {"local", "demo"}
    ):
        try:
            db_session.get_engine()
            factory = db_session.AsyncSessionLocal
            assert factory is not None
            from .db.seed import seed_if_empty

            async with factory() as session:
                seeded = await seed_if_empty(session)
            logger.info("event=db_startup_seed seeded=%s", seeded)
        except Exception as exc:  # noqa: BLE001 — seed failure is non-fatal
            logger.warning(
                "event=db_startup_seed_failed err=%s", type(exc).__name__
            )

    if settings.anomaly_agent_enabled:
        from .services.checkin_scheduler import run_forever

        _scheduler_task = asyncio.create_task(run_forever(), name="checkin_scheduler")
        logger.info("event=scheduler_task_started")

    try:
        yield
    finally:
        if _scheduler_task is not None and not _scheduler_task.done():
            _scheduler_task.cancel()
            try:
                await _scheduler_task
            except asyncio.CancelledError:
                pass
            logger.info("event=scheduler_task_stopped")
        await db_session.dispose_engine()
        logger.info("event=app_shutdown")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.monotonic()
        response: Response = await call_next(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "event=request method=%s path=%s status=%d latency_ms=%d request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        return response


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    app = FastAPI(title="Relay Backend", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIDMiddleware)

    # Envelope-wrapped exception handler — unhandled errors become
    # `{ok: false, error: {...}}` 500s instead of raw HTML tracebacks.
    from .services.envelope import register_envelope_exception_handler

    register_envelope_exception_handler(app)

    # Tool endpoints, webhooks, internal automation, call initiator.
    from .routes import api_router

    app.include_router(api_router)

    @app.get("/health")
    async def health() -> dict:
        from .db.session import ping

        return {
            "status": "ok",
            "environment": settings.environment,
            "adapter": settings.relay_adapter,
            "db": await ping(),
            "pusher": False,
            "claude": bool(settings.anthropic_api_key)
            and settings.anomaly_agent_enabled,
            "navpro": settings.relay_adapter in {"navpro", "mock"},
        }

    return app


app = create_app()
