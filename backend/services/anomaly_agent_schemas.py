"""Pydantic shapes for the Claude anomaly-agent layer.

Three models power the split between NavPro-supplied signals and Relay-owned
context, plus the Claude output contract:

- `NavProSnapshot` — what the poller produces (NavPro side of the seam).
  Shape follows `API_DOCS/NavPro_integration.md` §8 translation tables.
- `DriverContext` — what Relay owns (HOS self-report, fatigue, call history,
  rate-con context). Split from the snapshot per the `project_positioning`
  memory — Relay is a command center on top of NavPro, not a wrapper.
- `AnomalyDecision` — Claude's structured output, forced via tool-choice.
  Mirrors the `decide_proactive_call` tool schema.

Hard-rule outputs travel as `HardRuleHit` directly to the scheduler — Claude
only runs when the hard path doesn't fire.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.models.schemas import (
    CallOutcome,
    CallPurpose,
    CheckinTriggerReason,
    Driver,
    FatigueLevel,
    ISODateTime,
    Language,
    Load,
    UUID,
)


class _Flex(BaseModel):
    """Permissive base — NavPro response shapes evolve; pass-through is safer
    than hard validation at the seam."""

    model_config = ConfigDict(extra="ignore")


# ---------- NavProSnapshot ---------------------------------------------------


class NavProSnapshot(_Flex):
    """One tick's worth of NavPro-supplied state for a single driver.

    Per-endpoint failure flags (`driver_query_ok`, `tracking_ok`,
    `performance_ok`) let the Claude prompt reason about partial data instead
    of raising. Scheduler never crashes on a single NavPro 5xx.
    """

    driver_id: UUID
    fetched_at_utc: ISODateTime

    # From /api/driver/query — identity + work_status + last-known location
    work_status: Optional[str] = None  # "IN_TRANSIT" + unknown values pass through
    last_known_location_text: Optional[str] = None
    last_known_lat: Optional[float] = None
    last_known_lng: Optional[float] = None
    latest_update_utc: Optional[ISODateTime] = None
    tracking_stale_minutes: Optional[int] = None
    driver_activities_recent: list[dict] = Field(default_factory=list)

    # From /api/tracking/get/driver-dispatch — GPS trail + active trip ETA
    trail_last_1h_points: int = 0
    last_trail_point: Optional[dict] = None
    active_trip_id: Optional[str] = None
    active_trip_eta_utc: Optional[ISODateTime] = None

    # From /api/driver/performance/query — off-route + schedule drift
    oor_miles_last_24h: Optional[float] = None
    schedule_miles: Optional[float] = None
    actual_miles: Optional[float] = None
    schedule_actual_time_ratio: Optional[float] = None

    # Per-endpoint health
    driver_query_ok: bool = True
    tracking_ok: bool = True
    performance_ok: bool = True
    degraded_reason: Optional[str] = None


# ---------- DriverContext ----------------------------------------------------


class CallSummary(_Flex):
    """Compressed call row for the 'recent calls' context block."""

    id: UUID
    purpose: CallPurpose
    outcome: CallOutcome
    ended_at: Optional[ISODateTime] = None
    voicemail: bool = False


class DriverContext(_Flex):
    """Relay-owned state the LLM needs to reason about the driver.

    Separate from the snapshot because these fields don't come from NavPro —
    they come from Relay DB (last_checkin_at, fatigue), seeds (cadence), or
    the F6b post-call writeback (hos_self_reported). The prompt makes the
    provenance split visible so Claude doesn't over-weight stale beliefs.
    """

    driver: Driver
    active_load: Optional[Load] = None
    recent_calls: list[CallSummary] = Field(default_factory=list)
    now_utc: ISODateTime
    checkin_cadence_minutes: int = 180

    # HOS self-report freshness — how stale is our belief?
    last_hos_self_report_minutes: Optional[int] = None
    last_hos_self_report_age_minutes: Optional[int] = None

    # Fatigue history (last reported)
    last_fatigue_level: FatigueLevel = FatigueLevel.unknown


# ---------- AnomalyDecision --------------------------------------------------


class AnomalyDecision(_Flex):
    """Claude's structured output. Forced via `tool_choice`.

    `reasoning` is shown verbatim to the dispatcher in the `AnomalyBadge`
    tooltip — keep it plain English, reference specific signal values.
    """

    should_call: bool
    trigger_reason: CheckinTriggerReason
    urgency: Literal["routine", "elevated", "urgent"] = "routine"
    reasoning: str = Field(default="", max_length=400)
    suggested_language: Language = Language.en
    context_hints: dict = Field(default_factory=dict)


# ---------- HardRuleHit ------------------------------------------------------


class HardRuleHit(_Flex):
    """Output of `exceptions_engine.evaluate_hard`.

    When a rule fires, the scheduler triggers the check-in directly and
    skips the LLM call. `rule_name` goes into the tooltip fallback label
    ("HOS self-report ≤ 30 min") so the UI still explains itself.
    """

    rule_name: str
    trigger_reason: CheckinTriggerReason
    urgency: Literal["routine", "elevated", "urgent"] = "elevated"
    reasoning: str


# ---------- SoftSignal -------------------------------------------------------


class SoftSignal(_Flex):
    """A signal that didn't cross a hard threshold but is interesting enough
    to include in the LLM prompt. Rendered as a compact bullet."""

    name: str  # e.g. "tracking_stale", "missing_active_trip"
    value: str  # human-readable value
    severity: Literal["info", "warn", "critical"] = "info"


__all__ = [
    "AnomalyDecision",
    "CallSummary",
    "DriverContext",
    "HardRuleHit",
    "NavProSnapshot",
    "SoftSignal",
]
