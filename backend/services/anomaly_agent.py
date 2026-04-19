"""Claude Sonnet 4.6 anomaly-agent layer.

Sits at the Relay ↔ NavPro seam: takes a `NavProSnapshot` (NavPro-supplied
freshness) + `DriverContext` (Relay-owned state) and returns an
`AnomalyDecision` via forced tool use. The scheduler runs this only when the
hard rules in `exceptions_engine` don't fire — Claude handles the ambiguous
middle (silence, tracking staleness, multi-signal borderlines).

Caching + latency:
- System prompt (~900 tokens) is wrapped with `cache_control: ephemeral`.
  At 60s × 6 drivers, ~83% cache hit against the 5-min TTL; effective input
  cost drops to ~20% of nominal.
- `asyncio.wait_for(..., timeout=3)` hard ceiling. On timeout or API failure
  → `should_call=False` — hard rules still fire; scheduler tick never blocks.

Anthropic SDK: the client + tool schema are module-level to avoid per-call
allocation. Model id comes from `settings.anomaly_agent_model`
(`claude-sonnet-4-6` default).
"""

from __future__ import annotations

import asyncio
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from backend.config import settings

from .anomaly_agent_schemas import AnomalyDecision, DriverContext, NavProSnapshot

logger = logging.getLogger("relay.anomaly_agent")


_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "anomaly_agent_system.md"


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text()


# Tool schema — mirrors `AnomalyDecision`. Forced via `tool_choice` so the
# model must call it; no free-text JSON parsing.
ANOMALY_DECISION_TOOL: dict[str, Any] = {
    "name": "decide_proactive_call",
    "description": (
        "Decide whether to fire a proactive outbound check-in call to the driver. "
        "Always call this tool. Never answer in free text."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "should_call": {
                "type": "boolean",
                "description": "True if Relay should place a proactive voice call right now.",
            },
            "trigger_reason": {
                "type": "string",
                "enum": [
                    "scheduled",
                    "hos_near_cap",
                    "eta_drift",
                    "extended_idle",
                    "missed_checkin",
                    "tracking_stale",
                    "manual",
                ],
                "description": "Must match CheckinTriggerReason enum in the API.",
            },
            "urgency": {
                "type": "string",
                "enum": ["routine", "elevated", "urgent"],
                "description": "How soon the call should fire.",
            },
            "reasoning": {
                "type": "string",
                "description": (
                    "1-3 sentences in plain English, referencing specific signal values. "
                    "Shown verbatim in the dashboard tooltip. <=400 chars."
                ),
                "maxLength": 400,
            },
            "suggested_language": {
                "type": "string",
                "enum": ["en", "es", "pa"],
            },
            "context_hints": {
                "type": "object",
                "description": "Optional pass-through hints for personalization (e.g. prefetch_parking).",
            },
        },
        "required": ["should_call", "trigger_reason", "urgency", "reasoning"],
    },
}


def render_for_prompt(snap: NavProSnapshot, ctx: DriverContext) -> str:
    """Render the two blocks as a compact structured user message.

    Deliberately labels NavPro-supplied vs Relay-owned sections so Claude
    can reason about provenance (per the positioning memory + §1 of the
    NavPro integration guide)."""
    driver = ctx.driver
    load_block = "none"
    if ctx.active_load is not None:
        al = ctx.active_load
        load_block = (
            f"load_number={al.load_number} "
            f"pickup={al.pickup.name}@{al.pickup.appointment} "
            f"delivery={al.delivery.name}@{al.delivery.appointment} "
            f"status={al.status}"
        )

    recent = "\n".join(
        f"  - {c.purpose} outcome={c.outcome} ended_at={c.ended_at} voicemail={c.voicemail}"
        for c in ctx.recent_calls[:5]
    ) or "  (none in last 24h)"

    return (
        "## NavProSnapshot (NavPro-supplied, pull-only)\n"
        f"driver_id={snap.driver_id}\n"
        f"fetched_at_utc={snap.fetched_at_utc}\n"
        f"work_status={snap.work_status}\n"
        f"last_known_location={snap.last_known_location_text} "
        f"lat={snap.last_known_lat} lng={snap.last_known_lng}\n"
        f"latest_update_utc={snap.latest_update_utc}\n"
        f"tracking_stale_minutes={snap.tracking_stale_minutes}\n"
        f"trail_last_1h_points={snap.trail_last_1h_points}\n"
        f"active_trip_id={snap.active_trip_id}\n"
        f"active_trip_eta_utc={snap.active_trip_eta_utc}\n"
        f"oor_miles_last_24h={snap.oor_miles_last_24h}\n"
        f"schedule_miles={snap.schedule_miles} actual_miles={snap.actual_miles}\n"
        f"schedule_actual_time_ratio={snap.schedule_actual_time_ratio}\n"
        f"driver_query_ok={snap.driver_query_ok} "
        f"tracking_ok={snap.tracking_ok} performance_ok={snap.performance_ok}\n"
        f"degraded_reason={snap.degraded_reason}\n"
        "\n"
        "## DriverContext (Relay-owned)\n"
        f"now_utc={ctx.now_utc}\n"
        f"checkin_cadence_minutes={ctx.checkin_cadence_minutes}\n"
        f"driver: id={driver.id} name={driver.name} "
        f"status={driver.status} preferred_language={driver.preferred_language}\n"
        f"driver.hos (Relay-tracked, from last self-report): "
        f"drive={driver.hos_drive_remaining_minutes}m "
        f"shift={driver.hos_shift_remaining_minutes}m "
        f"cycle={driver.hos_cycle_remaining_minutes}m\n"
        f"driver.fatigue_level={driver.fatigue_level}\n"
        f"driver.last_checkin_at={driver.last_checkin_at}\n"
        f"driver.next_scheduled_checkin_at={driver.next_scheduled_checkin_at}\n"
        f"last_hos_self_report_minutes={ctx.last_hos_self_report_minutes} "
        f"age_minutes={ctx.last_hos_self_report_age_minutes}\n"
        f"active_load: {load_block}\n"
        f"recent_calls_last_24h:\n{recent}\n"
    )


def _default_hold(reason: str) -> AnomalyDecision:
    return AnomalyDecision(
        should_call=False,
        trigger_reason="manual",
        urgency="routine",
        reasoning=reason[:400],
    )


async def judge(snap: NavProSnapshot, ctx: DriverContext) -> AnomalyDecision:
    """Ask Claude whether to fire a proactive check-in.

    Returns a safe `should_call=False` decision on any failure — never raises.
    """
    if not settings.anomaly_agent_enabled:
        return _default_hold("Anomaly agent disabled via config.")
    if not settings.anthropic_api_key:
        return _default_hold("No Anthropic API key configured.")

    try:
        # Lazy import so the module loads without anthropic installed (for CI
        # that runs without the dep) — this path only executes when enabled.
        import anthropic  # type: ignore
    except ImportError:
        logger.warning("event=anomaly_agent_skip reason=anthropic_import_failed")
        return _default_hold("Anthropic SDK not installed.")

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    user_content = render_for_prompt(snap, ctx)

    try:
        response = await asyncio.wait_for(
            client.messages.create(
                model=settings.anomaly_agent_model,
                max_tokens=settings.anomaly_agent_max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": _system_prompt(),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=[ANOMALY_DECISION_TOOL],
                tool_choice={"type": "tool", "name": "decide_proactive_call"},
                messages=[{"role": "user", "content": user_content}],
            ),
            timeout=3.0,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "event=anomaly_agent_timeout driver_id=%s", snap.driver_id
        )
        return _default_hold("Anomaly agent timed out; defaulting to hold.")
    except Exception as exc:  # noqa: BLE001 — defensive catch-all per plan
        logger.warning(
            "event=anomaly_agent_error driver_id=%s err=%s msg=%s",
            snap.driver_id,
            type(exc).__name__,
            str(exc)[:300].replace("\n", " "),
        )
        return _default_hold(f"Anomaly agent error: {type(exc).__name__}.")

    tool_use = _extract_tool_use(response)
    if tool_use is None:
        logger.info(
            "event=anomaly_agent_no_tool_call driver_id=%s stop_reason=%s",
            snap.driver_id,
            getattr(response, "stop_reason", "unknown"),
        )
        return _default_hold("LLM declined to decide; defaulting to hold.")

    try:
        decision = AnomalyDecision.model_validate(tool_use)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "event=anomaly_agent_invalid_output driver_id=%s err=%s payload=%s",
            snap.driver_id,
            type(exc).__name__,
            json.dumps(tool_use, default=str)[:500],
        )
        return _default_hold("LLM output failed validation; defaulting to hold.")

    logger.info(
        "event=anomaly_agent_decision driver_id=%s should_call=%s trigger=%s urgency=%s",
        snap.driver_id,
        decision.should_call,
        decision.trigger_reason,
        decision.urgency,
    )
    return decision


def _extract_tool_use(response: Any) -> Optional[dict]:
    """Pull the first tool_use block's `input` dict from an Anthropic message."""
    content = getattr(response, "content", None) or []
    for block in content:
        block_type = getattr(block, "type", None)
        if block_type == "tool_use":
            name = getattr(block, "name", None)
            if name != "decide_proactive_call":
                continue
            return getattr(block, "input", None)
    return None


__all__ = [
    "ANOMALY_DECISION_TOOL",
    "judge",
    "render_for_prompt",
]
