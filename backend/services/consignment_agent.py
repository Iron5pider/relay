"""Claude Sonnet 4.6 consignment recommender.

Mirrors `anomaly_agent.py` structurally: forced tool use, cached system
prompt, 3s timeout, safe fallback so the dispatcher UI never blocks on the
LLM. Given the deterministic scorer's top-3 candidates, returns a short
plain-English recommendation plus a confidence label and risk flags the
dispatcher can read aloud.
"""

from __future__ import annotations

import asyncio
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from backend.config import settings
from backend.models.db import Load
from backend.services.consignment import ScoreBreakdown

logger = logging.getLogger("relay.consignment_agent")

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "consignment_agent_system.md"
)


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text()


RECOMMEND_TOOL: dict[str, Any] = {
    "name": "recommend_assignment",
    "description": (
        "Recommend which driver should take this load. Always call this tool. "
        "Never answer in free text."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "recommended_driver_id": {
                "type": "string",
                "description": "The driver_id from the top-ranked candidate.",
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
            "recommendation": {
                "type": "string",
                "description": "2-3 sentence plain-English explanation. <=400 chars.",
                "maxLength": 400,
            },
            "risk_flags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Flags the dispatcher should know about (echo scorer flags + your additions).",
            },
            "alternative_driver_id": {
                "type": ["string", "null"],
                "description": "The #2 candidate's driver_id, or null.",
            },
        },
        "required": [
            "recommended_driver_id",
            "confidence",
            "recommendation",
            "risk_flags",
            "alternative_driver_id",
        ],
    },
}


def _render_user_content(load: Load, top: list[ScoreBreakdown]) -> str:
    lines: list[str] = []
    lines.append("## Load")
    lines.append(f"load_number={load.load_number}")
    lines.append(f"pickup={load.pickup_name} lat={load.pickup_lat} lng={load.pickup_lng}")
    lines.append(f"pickup_appointment={load.pickup_appointment.isoformat()}")
    lines.append(f"delivery={load.delivery_name} lat={load.delivery_lat} lng={load.delivery_lng}")
    lines.append(f"delivery_appointment={load.delivery_appointment.isoformat()}")
    lines.append(f"rate_linehaul=${load.rate_linehaul}")
    lines.append("")
    lines.append("## Candidates (pre-ranked, highest score first)")
    for i, s in enumerate(top, start=1):
        lines.append(
            f"#{i} driver_id={s.driver_id} name={s.driver_name} truck={s.truck_number} "
            f"lang={s.preferred_language} status={s.status} "
            f"score={s.total} components={s.components} "
            f"miles_to_pickup={s.miles_to_pickup} "
            f"hos_headroom_min={s.hos_headroom_minutes} "
            f"hours_since_last_assigned={s.hours_since_last_assigned} "
            f"fatigue={s.fatigue_level} flags={s.flags}"
        )
    return "\n".join(lines)


def _fallback(top: list[ScoreBreakdown]) -> dict[str, Any]:
    """Deterministic recommendation when Claude is unavailable — never block the UI."""
    qualified = [s for s in top if s.qualified]
    if not qualified:
        return {
            "recommended_driver_id": "",
            "confidence": "low",
            "recommendation": "No qualified drivers. Re-check the roster or post this load to the load board.",
            "risk_flags": ["no_qualified_drivers"],
            "alternative_driver_id": None,
        }
    best = qualified[0]
    alt = qualified[1].driver_id if len(qualified) > 1 else None
    miles = f"{best.miles_to_pickup:.0f}mi" if best.miles_to_pickup is not None else "unknown distance"
    hours = int((best.hos_drive_remaining_minutes or 0) / 60)
    first_name = (best.driver_name or "Driver").split(" ", 1)[0]
    recommendation = (
        f"{first_name} ranks #1 at {best.total}/100 — {miles} from pickup with "
        f"{hours}h of drive time remaining."
    )
    return {
        "recommended_driver_id": best.driver_id,
        "confidence": "medium",
        "recommendation": recommendation,
        "risk_flags": best.flags,
        "alternative_driver_id": alt,
    }


async def recommend(load: Load, ranked: list[ScoreBreakdown]) -> dict[str, Any]:
    """Ask Claude for a recommendation. Always returns a dict matching the tool schema."""
    top = [s for s in ranked if s.qualified][:3]
    if not top:
        return _fallback(ranked)
    if not settings.anthropic_api_key:
        return _fallback(ranked)

    try:
        import anthropic  # type: ignore
    except ImportError:
        logger.warning("event=consignment_agent_skip reason=anthropic_import_failed")
        return _fallback(ranked)

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        response = await asyncio.wait_for(
            client.messages.create(
                model=settings.anomaly_agent_model,
                max_tokens=512,
                system=[
                    {
                        "type": "text",
                        "text": _system_prompt(),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=[RECOMMEND_TOOL],
                tool_choice={"type": "tool", "name": "recommend_assignment"},
                messages=[{"role": "user", "content": _render_user_content(load, top)}],
            ),
            timeout=3.5,
        )
    except asyncio.TimeoutError:
        logger.warning("event=consignment_agent_timeout load_id=%s", load.id)
        return _fallback(ranked)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "event=consignment_agent_error load_id=%s err=%s msg=%s",
            load.id,
            type(exc).__name__,
            str(exc)[:300].replace("\n", " "),
        )
        return _fallback(ranked)

    tool_use = _extract_tool_use(response)
    if tool_use is None:
        logger.info("event=consignment_agent_no_tool_call load_id=%s", load.id)
        return _fallback(ranked)

    # Defensive: make sure Claude didn't hallucinate a driver_id outside the candidate list.
    valid_ids = {s.driver_id for s in top}
    if tool_use.get("recommended_driver_id") not in valid_ids:
        logger.warning(
            "event=consignment_agent_invalid_driver_id returned=%s valid=%s",
            tool_use.get("recommended_driver_id"),
            valid_ids,
        )
        return _fallback(ranked)
    return tool_use


def _extract_tool_use(response: Any) -> Optional[dict]:
    content = getattr(response, "content", None) or []
    for block in content:
        if getattr(block, "type", None) == "tool_use":
            if getattr(block, "name", None) == "recommend_assignment":
                return getattr(block, "input", None)
    return None


__all__ = ["RECOMMEND_TOOL", "recommend"]
