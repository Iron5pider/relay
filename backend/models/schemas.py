"""Canonical Pydantic schemas.

Mirrors `frontend/shared/types.ts` field-for-field. Enum values, field names,
nullability must match — per `backend/CLAUDE.md` §1 golden rule #2 and the
`project_canonical_spec` memory. Change one, change both + Notion API Models
in the same PR.

Additive enum values (2026-04-19):
- `CheckinTriggerReason.missed_checkin` — Build Scope Feature 2 anomaly rule.
- `CheckinTriggerReason.tracking_stale` — NavPro `latest_update` freshness signal
  surfaced by the Claude anomaly agent. See `API_DOCS/NavPro_integration.md` §7.

Additive field (2026-04-19):
- `Call.trigger_reasoning` — Claude-generated rationale for why a proactive
  check-in fired. Surfaced verbatim in the dashboard `AnomalyBadge` tooltip.
  Null for hard-rule triggers (the human label carries the meaning).
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

UUID = str
ISODateTime = str
E164 = str


# --- enums -------------------------------------------------------------------


class Language(str, Enum):
    en = "en"
    es = "es"
    pa = "pa"


class DriverStatus(str, Enum):
    # Existing FMCSA statuses — Block 1.
    driving = "driving"
    on_duty = "on_duty"
    off_duty = "off_duty"
    sleeper = "sleeper"
    # Tools-contract additions (2026-04-19). Orthogonal application-layer
    # statuses for the agent's mental model: ready/resting/blocked/rolling.
    # Coexist with the FMCSA set; the DB stores whichever string is current.
    ready = "ready"
    resting = "resting"
    blocked = "blocked"
    rolling = "rolling"


class LoadStatus(str, Enum):
    planned = "planned"
    in_transit = "in_transit"
    at_pickup = "at_pickup"
    at_delivery = "at_delivery"
    delivered = "delivered"
    exception = "exception"


class CallDirection(str, Enum):
    outbound = "outbound"
    inbound = "inbound"


class CallPurpose(str, Enum):
    detention_escalation = "detention_escalation"
    broker_check_call = "broker_check_call"
    driver_checkin = "driver_checkin"
    driver_proactive_checkin = "driver_proactive_checkin"
    other = "other"


class CallOutcome(str, Enum):
    resolved = "resolved"
    escalated = "escalated"
    voicemail = "voicemail"
    no_answer = "no_answer"
    failed = "failed"
    in_progress = "in_progress"


class Speaker(str, Enum):
    agent = "agent"
    human = "human"


class ExceptionType(str, Enum):
    detention_threshold_breached = "detention_threshold_breached"
    hos_warning = "hos_warning"
    missed_appointment = "missed_appointment"
    breakdown = "breakdown"
    late_eta = "late_eta"


class Severity(str, Enum):
    info = "info"
    warn = "warn"
    critical = "critical"


class InvoiceStatus(str, Enum):
    draft = "draft"
    sent = "sent"
    paid = "paid"
    disputed = "disputed"


class UpdateChannel(str, Enum):
    call = "call"
    sms = "sms"
    email = "email"


class UpdateType(str, Enum):
    end_of_day = "end_of_day"
    pre_delivery = "pre_delivery"
    custom = "custom"


class CheckinStatus(str, Enum):
    on_route = "on_route"
    at_pickup = "at_pickup"
    at_delivery = "at_delivery"
    delivered = "delivered"
    exception = "exception"


class FatigueLevel(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"
    unknown = "unknown"


class EtaConfidence(str, Enum):
    on_time = "on_time"
    at_risk = "at_risk"
    late = "late"


class CheckinTriggerReason(str, Enum):
    scheduled = "scheduled"
    hos_near_cap = "hos_near_cap"
    eta_drift = "eta_drift"
    extended_idle = "extended_idle"
    missed_checkin = "missed_checkin"
    tracking_stale = "tracking_stale"
    manual = "manual"


# --- Tools-contract enums (2026-04-19) --------------------------------------
# Source: API_DOCS/tools_contract.md §1. Coexist with CheckinTriggerReason
# during the naming transition.


class DriverCallTrigger(str, Enum):
    scheduled_checkin = "scheduled_checkin"
    hos_near_cap = "hos_near_cap"
    eta_slip_check = "eta_slip_check"
    post_breakdown = "post_breakdown"
    stationary_too_long = "stationary_too_long"
    inbound = "inbound"


class Urgency(str, Enum):
    low = "low"
    med = "med"
    high = "high"


class IssueType(str, Enum):
    mechanical = "mechanical"
    personal = "personal"
    load = "load"
    route = "route"
    weather = "weather"
    other = "other"
    none = "none"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Coordinates(_Strict):
    lat: float
    lng: float


class Stop(_Strict):
    name: str
    lat: float
    lng: float
    phone: Optional[E164] = None
    appointment: ISODateTime


class Driver(_Strict):
    id: UUID
    name: str
    phone: E164
    preferred_language: Language
    truck_number: str
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    hos_drive_remaining_minutes: int
    hos_shift_remaining_minutes: int
    hos_cycle_remaining_minutes: int
    hos_remaining_minutes: int
    status: DriverStatus
    fatigue_level: FatigueLevel
    last_checkin_at: Optional[ISODateTime] = None
    next_scheduled_checkin_at: Optional[ISODateTime] = None
    updated_at: ISODateTime


class Broker(_Strict):
    id: UUID
    name: str
    contact_name: str
    phone: E164
    email: str
    preferred_update_channel: UpdateChannel


class DriverLite(_Strict):
    id: UUID
    name: str
    truck_number: str


class BrokerLite(_Strict):
    id: UUID
    name: str


class Load(_Strict):
    id: UUID
    load_number: str
    driver: DriverLite
    broker: BrokerLite
    pickup: Stop
    delivery: Stop
    rate_linehaul: float
    detention_rate_per_hour: float
    detention_free_minutes: int
    status: LoadStatus
    arrived_at_stop_at: Optional[ISODateTime] = None
    detention_minutes_elapsed: int
    exception_flags: list[ExceptionType]
    created_at: ISODateTime


class TranscriptTurn(_Strict):
    id: UUID
    speaker: Speaker
    text: str
    language: Language
    started_at: ISODateTime
    confidence: float


class Call(_Strict):
    id: UUID
    load_id: Optional[UUID] = None
    direction: CallDirection
    purpose: CallPurpose
    from_number: E164
    to_number: E164
    language: Language
    started_at: ISODateTime
    ended_at: Optional[ISODateTime] = None
    duration_seconds: Optional[int] = None
    outcome: CallOutcome
    audio_url: Optional[str] = None
    twilio_call_sid: str
    transcript: list[TranscriptTurn] = Field(default_factory=list)
    trigger_reasoning: Optional[str] = None


class DetentionInvoice(_Strict):
    id: UUID
    load_id: UUID
    call_id: UUID
    detention_minutes: int
    rate_per_hour: float
    amount_usd: float
    pdf_url: str
    status: InvoiceStatus
    created_at: ISODateTime


class ExceptionEvent(_Strict):
    id: UUID
    load_id: UUID
    driver_id: UUID
    event_type: ExceptionType
    severity: Severity
    payload: dict
    triggered_call_id: Optional[UUID] = None
    detected_at: ISODateTime


class ParkingSpot(_Strict):
    name: str
    lat: float
    lng: float
    available_spots: int
    distance_miles: float
    exit: str


# --- request / response envelopes (Block 2+ consumes) ------------------------


class EscalateDetentionRequest(_Strict):
    load_id: UUID
    receiver_phone_override: Optional[E164] = None
    auto_invoice: bool = True


class EscalateDetentionResponse(_Strict):
    call_id: UUID
    twilio_call_sid: str
    status: Literal["initiated"] = "initiated"
    expected_detention_amount: float


class DriverCheckinRequest(_Strict):
    driver_id: UUID
    trigger_reason: CheckinTriggerReason = CheckinTriggerReason.manual
    phone_override: Optional[E164] = None
    trigger_reasoning: Optional[str] = None


class DriverCheckinResponse(_Strict):
    call_id: UUID
    twilio_call_sid: str
    status: Literal["initiated"] = "initiated"
    trigger_reason: CheckinTriggerReason


class BatchBrokerUpdatesRequest(_Strict):
    broker_ids: Optional[list[UUID]] = None
    update_type: UpdateType = UpdateType.end_of_day
    custom_message: Optional[str] = None


class BatchBrokerUpdatesResponse(_Strict):
    batch_id: UUID
    call_ids: list[UUID]
    count: int
