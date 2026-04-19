"""checkin_scheduler — tiered asyncio cron for proactive check-ins.

Composes the three layers:

1. `navpro_poller.collect_snapshot(driver_id)` — NavPro side of the seam.
2. `assemble_driver_context(driver_id)` — Relay-owned state.
3. `exceptions_engine.evaluate(snap, ctx)` — hard rule or soft signals.
4. If hard hit → fire `/actions/driver-checkin/` directly.
5. Else → `anomaly_agent.judge(snap, ctx)` → fire on `should_call=True`.

Cadence per `API_DOCS/NavPro_integration.md` §7:
- **Hero-adjacent drivers** (exception load assigned, or within 30 min of
  delivery appointment) → poll every `poll_interval_hero_seconds` (default 30).
- **All other active drivers** → `poll_interval_default_seconds` (default 60).
- Identity refresh (`list_drivers`) is implicit — each snapshot collection
  already calls `list_drivers` via the poller.

The loop is cancelable (FastAPI lifespan stops it cleanly on shutdown).
On any per-driver exception, log + continue — never crash the tick.

The trigger fan-out is modeled as a callback (`trigger_checkin`) so this
module can be exercised in tests without the real HTTP route. Once the
`routes/actions.py` landing lands, the default callback POSTs to
`/api/v1/actions/driver-checkin/`.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from backend.config import settings
from backend.models.schemas import (
    CheckinTriggerReason,
    Driver,
    Load,
    UUID,
)

from . import anomaly_agent, exceptions_engine, navpro_poller
from .adapters import get_adapter
from .anomaly_agent_schemas import (
    AnomalyDecision,
    CallSummary,
    DriverContext,
    HardRuleHit,
    NavProSnapshot,
)

logger = logging.getLogger("relay.checkin_scheduler")


TriggerCheckin = Callable[
    [UUID, CheckinTriggerReason, Optional[str]], Awaitable[None]
]
ContextLoader = Callable[[UUID], Awaitable[DriverContext]]


async def _default_context_loader(driver_id: UUID) -> DriverContext:
    """Fallback context loader for local dev / tests when Relay DB isn't up.

    Pulls the driver from the adapter's seed + synthesizes empty call
    history. Production replacement lives in `routes/actions.py` (or a
    `services/context.py` helper) once Block 2 lands.
    """
    adapter = get_adapter()
    drivers = await adapter.list_drivers()
    driver = next((d for d in drivers if d.id == driver_id), None)
    if driver is None:
        raise ValueError(f"driver {driver_id} not found in adapter")

    active_load = await _find_active_load(driver_id)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return DriverContext(
        driver=driver,
        active_load=active_load,
        recent_calls=[],
        now_utc=now,
        checkin_cadence_minutes=180,
        last_hos_self_report_minutes=driver.hos_drive_remaining_minutes,
        last_hos_self_report_age_minutes=None,
        last_fatigue_level=driver.fatigue_level,
    )


async def _find_active_load(driver_id: UUID) -> Optional[Load]:
    """Loads live in Relay DB in production; until then, scan the mock adapter."""
    from .adapters.mock_tp import MockTPAdapter

    adapter = get_adapter()
    if not isinstance(adapter, MockTPAdapter):
        return None
    raw_loads = adapter._load("loads.json")  # type: ignore[attr-defined]
    for raw in raw_loads:
        if raw.get("driver", {}).get("id") == driver_id:
            try:
                return Load.model_validate(raw)
            except Exception:
                return None
    return None


async def _default_trigger(
    driver_id: UUID,
    trigger_reason: CheckinTriggerReason,
    reasoning: Optional[str],
) -> None:
    """Default trigger — logs only until `routes/actions.py` is wired.

    Block 2 implementation calls
    `POST /api/v1/actions/driver-checkin/` with this payload."""
    logger.info(
        "event=trigger_checkin_stub driver_id=%s trigger=%s reasoning=%s",
        driver_id,
        trigger_reason,
        (reasoning or "")[:200],
    )


def is_hero_adjacent(driver: Driver, active_load: Optional[Load]) -> bool:
    """Hero-adjacent drivers get faster polling (30s vs 60s).

    Matches NavPro_integration.md §7: exception loads OR within 30 min of a
    delivery appointment.
    """
    if active_load is None:
        return False
    if active_load.status.value == "exception":
        return True
    # Within 30 minutes of delivery?
    try:
        dt = datetime.fromisoformat(
            active_load.delivery.appointment.replace("Z", "+00:00")
        )
    except Exception:
        return False
    delta_min = abs((dt - datetime.now(timezone.utc)).total_seconds()) / 60
    return delta_min <= 30


async def tick_driver(
    driver_id: UUID,
    context_loader: ContextLoader,
    trigger_checkin: TriggerCheckin,
) -> None:
    """One scheduler pass for one driver. Never raises."""
    try:
        snap = await navpro_poller.collect_snapshot(driver_id)
        ctx = await context_loader(driver_id)
        await _run_decision(snap, ctx, trigger_checkin)
    except Exception as exc:  # noqa: BLE001 — defensive catch-all
        logger.warning(
            "event=scheduler_tick_driver_error driver_id=%s err=%s",
            driver_id,
            type(exc).__name__,
        )


async def _run_decision(
    snap: NavProSnapshot,
    ctx: DriverContext,
    trigger_checkin: TriggerCheckin,
) -> None:
    hard, signals = exceptions_engine.evaluate(snap, ctx)
    if hard is not None:
        await trigger_checkin(snap.driver_id, hard.trigger_reason, hard.reasoning)
        return

    # Soft signals → Claude
    if not signals:
        # Everything quiet. Nothing to escalate to the LLM.
        logger.debug(
            "event=scheduler_quiet driver_id=%s",
            snap.driver_id,
        )
        return

    decision: AnomalyDecision = await anomaly_agent.judge(snap, ctx)
    if decision.should_call:
        await trigger_checkin(
            snap.driver_id,
            decision.trigger_reason,
            decision.reasoning,
        )


async def run_forever(
    context_loader: ContextLoader = _default_context_loader,
    trigger_checkin: TriggerCheckin = _default_trigger,
) -> None:
    """Top-level cron. Runs until cancelled by the FastAPI lifespan."""
    hero_interval = settings.anomaly_agent_poll_interval_hero_seconds
    default_interval = settings.anomaly_agent_poll_interval_default_seconds

    # We use a coarse tick: every `hero_interval` seconds, poll hero-adjacent
    # drivers; every N-th tick (= default_interval / hero_interval), poll
    # everyone else. Simpler than per-driver asyncio tasks for 6 drivers.
    ratio = max(int(default_interval / max(hero_interval, 1)), 1)
    iteration = 0

    logger.info(
        "event=scheduler_start hero_interval=%ds default_interval=%ds ratio=%d",
        hero_interval,
        default_interval,
        ratio,
    )

    while True:
        try:
            adapter = get_adapter()
            drivers = await adapter.list_drivers()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "event=scheduler_list_drivers_failed err=%s",
                type(exc).__name__,
            )
            await asyncio.sleep(hero_interval)
            continue

        hero: list[UUID] = []
        default: list[UUID] = []
        for d in drivers:
            active = await _find_active_load(d.id)
            if is_hero_adjacent(d, active):
                hero.append(d.id)
            else:
                default.append(d.id)

        # Hero-adjacent every iteration.
        for driver_id in hero:
            await tick_driver(driver_id, context_loader, trigger_checkin)

        # Default cadence: every `ratio` iterations.
        if iteration % ratio == 0:
            for driver_id in default:
                await tick_driver(driver_id, context_loader, trigger_checkin)

        iteration += 1
        try:
            await asyncio.sleep(hero_interval)
        except asyncio.CancelledError:
            logger.info("event=scheduler_cancelled")
            raise


__all__ = [
    "ContextLoader",
    "TriggerCheckin",
    "is_hero_adjacent",
    "run_forever",
    "tick_driver",
]
