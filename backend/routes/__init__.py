"""Router composition. Every route module registers its own APIRouter at
module level; `api_router` glues them with the right prefixes per
`API_DOCS/tools_contract.md` §0 URL layout.
"""

from __future__ import annotations

from fastapi import APIRouter

from . import calls, internal, tools, webhooks_elevenlabs

api_router = APIRouter()
# Tool endpoints live at `/tools/{group}/{action}` — router defines full paths.
api_router.include_router(tools.router)
# Webhooks: `/webhooks/elevenlabs/{post_call,personalization}`.
api_router.include_router(webhooks_elevenlabs.router, prefix="/webhooks/elevenlabs")
# Internal automation: `/internal/invoice/…`, `/internal/dispatcher/…`.
api_router.include_router(internal.router, prefix="/internal")
# Call initiator: `/internal/call/initiate`.
api_router.include_router(calls.router, prefix="/internal")

__all__ = ["api_router"]
