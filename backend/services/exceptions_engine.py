"""exceptions_engine — hard-rule evaluator + soft-signal extractor.

**Hard-rule / soft-signal split (2026-04-19).** Per the anomaly-agent plan,
rules that have a single correct answer fire directly and skip the LLM. Rules
that require judgment (silence + context + staleness) become `SoftSignal`
objects for the Claude agent to weigh.

This module is pure — no DB, no HTTP, no asyncio. Takes a `NavProSnapshot` +
`DriverContext` and returns `(hit | None, signals)`. Scheduler composes.

Hard rules (unchanged from plan):
- `hos_drive_remaining_minutes ≤ 30` (Relay-tracked self-report) → hos_near_cap.
- active_trip.eta vs active_load.delivery.appointment drift ≥ 30 min → eta_drift.
- `oor_miles_last_24h ≥ 20` → extended_idle.

Soft signals (handed to Claude):
- `tracking_stale_minutes > 30` when an active trip is present.
- `now - last_checkin_at > 2 × cadence`.
- `active_trip_id is None` while `active_load is not None`.
- `schedule_actual_time_ratio > 1.2`.
- `degraded_reason != None` (NavPro partial failure).
- `fatigue_level in {moderate, high}` with recent activity.

Note: the hero detention-escalation flow (geofence breach → detention invoice)
lives in `services/detention.py` / `services/call_orchestrator.py` and is NOT
in this engine's scope.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

from backend.models.schemas import CheckinTriggerReason, FatigueLevel

from .anomaly_agent_schemas import DriverContext, HardRuleHit, NavProSnapshot, SoftSignal

logger = logging.getLogger("relay.exceptions_engine")


_HOS_NEAR_CAP_MINUTES = 30
_OOR_MILES_HARD_THRESHOLD = 20.0
_TRACKING_STALE_SOFT_MINUTES = 30
_ETA_DRIFT_HARD_MINUTES = 30
_SCHEDULE_RATIO_SOFT_THRESHOLD = 1.2


def _iso_to_dt(iso: Optional[str]) -> Optional[datetime]:
    if iso is None:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def _minutes_between(later_iso: Optional[str], earlier_iso: Optional[str]) -> Optional[int]:
    a, b = _iso_to_dt(later_iso), _iso_to_dt(earlier_iso)
    if a is None or b is None:
        return None
    return int((a - b).total_seconds() // 60)


def evaluate(
    snap: NavProSnapshot, ctx: DriverContext
) -> Tuple[Optional[HardRuleHit], list[SoftSignal]]:
    """Return `(hard_hit_or_none, soft_signals)`.

    Scheduler fires the check-in directly on `hard_hit`; otherwise passes
    `(snap, ctx, soft_signals)` to the Claude agent.
    """

    hard = _evaluate_hard(snap, ctx)
    signals = _extract_soft_signals(snap, ctx)
    if hard is not None:
        logger.info(
            "event=exception_hard_rule driver_id=%s rule=%s trigger=%s",
            snap.driver_id,
            hard.rule_name,
            hard.trigger_reason,
        )
    return hard, signals


def _evaluate_hard(
    snap: NavProSnapshot, ctx: DriverContext
) -> Optional[HardRuleHit]:
    driver = ctx.driver

    # HOS near cap (Relay-owned self-report).
    if driver.hos_drive_remaining_minutes <= _HOS_NEAR_CAP_MINUTES:
        return HardRuleHit(
            rule_name="hos_drive_remaining_minutes<=30",
            trigger_reason=CheckinTriggerReason.hos_near_cap,
            urgency="urgent",
            reasoning=(
                f"HOS drive remaining {driver.hos_drive_remaining_minutes}m "
                f"(self-reported). Urgent — offer parking, respect 90s cap."
            ),
        )

    # ETA drift vs active load delivery appointment.
    if ctx.active_load is not None and snap.active_trip_eta_utc is not None:
        drift = _minutes_between(
            snap.active_trip_eta_utc, ctx.active_load.delivery.appointment
        )
        if drift is not None and drift >= _ETA_DRIFT_HARD_MINUTES:
            return HardRuleHit(
                rule_name="eta_drift>=30min",
                trigger_reason=CheckinTriggerReason.eta_drift,
                urgency="elevated",
                reasoning=(
                    f"ETA drifted {drift}m past delivery appointment "
                    f"({ctx.active_load.delivery.appointment})."
                ),
            )

    # Off-route miles — new hard rule (2026-04-19).
    if (
        snap.performance_ok
        and snap.oor_miles_last_24h is not None
        and snap.oor_miles_last_24h >= _OOR_MILES_HARD_THRESHOLD
    ):
        return HardRuleHit(
            rule_name="oor_miles>=20",
            trigger_reason=CheckinTriggerReason.extended_idle,
            urgency="elevated",
            reasoning=(
                f"Off-route {snap.oor_miles_last_24h:.1f} miles in last 24h. "
                f"Check for detour, breakdown, or route change."
            ),
        )

    return None


def _extract_soft_signals(
    snap: NavProSnapshot, ctx: DriverContext
) -> list[SoftSignal]:
    signals: list[SoftSignal] = []

    # Tracking staleness (primary NavPro-seam signal).
    if (
        snap.tracking_stale_minutes is not None
        and snap.tracking_stale_minutes > _TRACKING_STALE_SOFT_MINUTES
    ):
        severity = (
            "critical"
            if snap.tracking_stale_minutes > 90
            else "warn"
        )
        signals.append(
            SoftSignal(
                name="tracking_stale",
                value=f"{snap.tracking_stale_minutes}m since latest_update",
                severity=severity,
            )
        )

    # Missed check-in (Relay-side silence).
    if ctx.driver.last_checkin_at is not None:
        minutes_since = _minutes_between(ctx.now_utc, ctx.driver.last_checkin_at)
        if (
            minutes_since is not None
            and minutes_since > 2 * ctx.checkin_cadence_minutes
        ):
            signals.append(
                SoftSignal(
                    name="missed_checkin",
                    value=f"{minutes_since}m since last check-in (cadence {ctx.checkin_cadence_minutes}m)",
                    severity="warn",
                )
            )

    # Load assigned but no active trip on NavPro side.
    if ctx.active_load is not None and not snap.active_trip_id:
        signals.append(
            SoftSignal(
                name="missing_active_trip",
                value=f"load {ctx.active_load.load_number} assigned but no active_trip on NavPro",
                severity="warn",
            )
        )

    # Schedule vs actual drift.
    if (
        snap.schedule_actual_time_ratio is not None
        and snap.schedule_actual_time_ratio > _SCHEDULE_RATIO_SOFT_THRESHOLD
    ):
        signals.append(
            SoftSignal(
                name="schedule_drift",
                value=f"actual/schedule ratio {snap.schedule_actual_time_ratio:.2f}",
                severity="info",
            )
        )

    # Mild off-route (under hard threshold).
    if (
        snap.performance_ok
        and snap.oor_miles_last_24h is not None
        and 5.0 <= snap.oor_miles_last_24h < _OOR_MILES_HARD_THRESHOLD
    ):
        signals.append(
            SoftSignal(
                name="mild_off_route",
                value=f"{snap.oor_miles_last_24h:.1f} miles off-route (under 20mi hard threshold)",
                severity="info",
            )
        )

    # NavPro degraded.
    if snap.degraded_reason:
        signals.append(
            SoftSignal(
                name="navpro_degraded",
                value=snap.degraded_reason,
                severity="warn",
            )
        )

    # Fatigue history hint.
    if ctx.last_fatigue_level in {FatigueLevel.moderate, FatigueLevel.high}:
        signals.append(
            SoftSignal(
                name="fatigue_history",
                value=f"last reported {ctx.last_fatigue_level.value}",
                severity="info" if ctx.last_fatigue_level == FatigueLevel.moderate else "warn",
            )
        )

    return signals


__all__ = ["evaluate"]
