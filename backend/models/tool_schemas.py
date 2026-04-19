"""Agent-facing request/response shapes for the ElevenLabs tools + webhooks.

Mirrors `API_DOCS/tools_contract.md` §2-§8 verbatim. These are the wire-level
contracts ElevenLabs depends on. Distinct from `schemas.py` (canonical domain
types) so the agent-boundary reader can find everything in one file.

All handlers wrap responses in `{ok, data, error}` via
`backend/services/envelope.py` — the `Data` models here are what goes into
the `data` field.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.models.schemas import (
    DriverCallTrigger,
    FatigueLevel,
    IssueType,
    Language,
    Urgency,
)


class _Flex(BaseModel):
    model_config = ConfigDict(extra="ignore")


# =============================================================================
# driver_agent tools (§2)
# =============================================================================


# §2.1 get_driver_context
class DriverContextLastGps(_Flex):
    lat: float
    lng: float
    city: str
    updated_at: str


class DriverContextData(_Flex):
    driver_id: str
    name: str
    first_name: str
    truck_number: str
    current_load_id: Optional[str] = None
    last_gps: Optional[DriverContextLastGps] = None
    hos_drive_remaining_min: int
    hos_shift_remaining_min: int
    fuel_last_known_pct: Optional[int] = None
    preferred_language: Language
    fatigue_level: FatigueLevel


# §2.2 update_hos
class UpdateHosRequest(_Flex):
    driver_id: str
    call_id: str
    hos_remaining_min: int
    status: str  # DriverStatus value (union of FMCSA + app-layer)


class UpdatedAtData(_Flex):
    updated_at: str


# §2.3 update_status
class UpdateStatusRequest(_Flex):
    driver_id: str
    call_id: str
    status: str
    note: Optional[str] = None


# §2.4 log_issue
class LogIssueRequest(_Flex):
    driver_id: str
    call_id: str
    type: IssueType
    severity: int = Field(default=3, ge=1, le=5)
    description: str


class LogIssueData(_Flex):
    incident_id: str


# §2.5 update_eta
class UpdateEtaRequest(_Flex):
    trip_id: str  # we accept load_id as trip_id alias for hackathon scope
    call_id: str
    new_eta_iso: str
    reason: str


class UpdateEtaData(_Flex):
    trip_id: str
    previous_eta: str
    new_eta: str
    delta_minutes: int


# §2.6 lookup_parking
class ParkingData(_Flex):
    name: str
    brand: str
    distance_mi: float
    direction: str
    address: str
    amenities: list[str]
    est_spots_available: Literal["likely", "limited", "full", "unknown"]


# §2.7 find_repair_shop
RepairService = Literal["mechanical", "tire", "electrical", "mobile_roadside", "towing"]


class RepairShopData(_Flex):
    name: str
    distance_mi: float
    phone: str
    services: list[str]
    hours: str
    address: str


# §2.8 notify_dispatcher
class NotifyDispatcherRequest(_Flex):
    urgency: Urgency
    summary: str
    driver_id: Optional[str] = None
    call_id: Optional[str] = None
    load_id: Optional[str] = None


class NotifyDispatcherData(_Flex):
    notification_id: str


# =============================================================================
# detention_agent tools (§3)
# =============================================================================


# §3.1 get_rate_con_terms
class RateConTermsData(_Flex):
    load_id: str
    load_number: str
    detention_free_minutes: int
    detention_rate_per_hour: float
    tonu_rate: float
    layover_rate: float
    receiver_name: str
    receiver_address: str
    appointment_dt: str
    broker_name: str
    rate_linehaul: float


# §3.2 confirm_detention
class ConfirmDetentionRequest(_Flex):
    load_id: str
    call_id: str
    ap_contact_name: str
    ap_contact_method: Literal["email", "phone", "portal", "unknown"]
    ap_contact_detail: str
    supervisor_name: Optional[str] = None
    committed_to_pay: bool
    detention_hours_confirmed: float
    notes: Optional[str] = None


class ConfirmDetentionData(_Flex):
    detention_event_id: str
    invoice_generation_queued: bool = True


# §3.3 mark_refused
class MarkRefusedRequest(_Flex):
    load_id: str
    call_id: str
    reason: str
    escalation_step_reached: int
    contact_attempted: Optional[str] = None


class MarkRefusedData(_Flex):
    detention_event_id: str


# §3.4 transcript_snapshot (shared with §4.4)
class TranscriptSnapshotRequest(_Flex):
    call_id: str
    key_quote: str
    quote_type: Literal["commitment", "refusal", "escalation"]


class TranscriptSnapshotData(_Flex):
    snapshot_id: str


# =============================================================================
# broker_update_agent tools (§4)
# =============================================================================


# §4.1 get_load_status_for_broker
class LoadStatusForBrokerData(_Flex):
    load_id: str
    load_number: str
    driver_first_name: str
    last_gps_city: Optional[str] = None
    miles_remaining: Optional[int] = None
    eta_iso: str
    eta_time_pst: Optional[str] = None
    appointment_time_pst: Optional[str] = None
    on_schedule: bool
    schedule_delta_minutes: int
    status: str


# §4.2 mark_broker_updated
class MarkBrokerUpdatedRequest(_Flex):
    load_id: str
    call_id: str
    broker_rep_name: Optional[str] = None
    voicemail: bool = False
    broker_ack_received: bool = False
    notes: Optional[str] = None


class MarkBrokerUpdatedData(_Flex):
    update_id: str


# §4.3 request_dispatcher_callback
class RequestDispatcherCallbackRequest(_Flex):
    load_id: str
    call_id: str
    broker_rep_name: Optional[str] = None
    reason: str


class RequestDispatcherCallbackData(_Flex):
    callback_request_id: str


# =============================================================================
# Outbound call initiator (§5.1 + §9.2 entrypoint)
# =============================================================================


AgentKind = Literal["driver_agent", "detention_agent", "broker_update_agent"]


class CallInitiateRequest(_Flex):
    agent_kind: AgentKind
    driver_id: Optional[str] = None
    load_id: Optional[str] = None
    to_number: Optional[str] = None
    trigger_reason: DriverCallTrigger = DriverCallTrigger.scheduled_checkin
    # Free-form extras merged into the ElevenLabs dynamic_variables block.
    # Unknown keys are forwarded; the agent only reads what it's configured for.
    extra_dynamic_variables: dict[str, Any] = Field(default_factory=dict)
    first_message_override: Optional[str] = None


class CallInitiateData(_Flex):
    conversation_id: str
    call_sid: Optional[str] = None
    voice_call_id: str


# =============================================================================
# Webhooks (§6, §7)
# =============================================================================


# §6.2 post_call (what ElevenLabs sends us)
class ElevenLabsPostCallData(_Flex):
    agent_id: str
    conversation_id: str
    status: str
    call_duration_secs: int = 0
    transcript: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    analysis: dict[str, Any] = Field(default_factory=dict)


class ElevenLabsPostCallEvent(_Flex):
    type: str
    event_timestamp: int
    data: ElevenLabsPostCallData


# §7 personalization
class PersonalizationRequest(_Flex):
    caller_id: str
    agent_id: str
    called_number: Optional[str] = None
    call_sid: Optional[str] = None


class PersonalizationResponse(_Flex):
    """Returned RAW (no envelope) — ElevenLabs expects this shape at top level."""

    dynamic_variables: dict[str, Any]
    first_message_override: Optional[str] = None


# =============================================================================
# Internal automation (§8)
# =============================================================================


class CallIdBody(_Flex):
    call_id: str


class InvoiceGeneratedData(_Flex):
    invoice_id: str
    pdf_url: str
    amount: float
    status: str


class UrgentTaskData(_Flex):
    task_id: str


__all__ = [
    "AgentKind",
    "CallIdBody",
    "CallInitiateData",
    "CallInitiateRequest",
    "ConfirmDetentionData",
    "ConfirmDetentionRequest",
    "DriverContextData",
    "DriverContextLastGps",
    "ElevenLabsPostCallData",
    "ElevenLabsPostCallEvent",
    "InvoiceGeneratedData",
    "LoadStatusForBrokerData",
    "LogIssueData",
    "LogIssueRequest",
    "MarkBrokerUpdatedData",
    "MarkBrokerUpdatedRequest",
    "MarkRefusedData",
    "MarkRefusedRequest",
    "NotifyDispatcherData",
    "NotifyDispatcherRequest",
    "ParkingData",
    "PersonalizationRequest",
    "PersonalizationResponse",
    "RateConTermsData",
    "RepairService",
    "RepairShopData",
    "RequestDispatcherCallbackData",
    "RequestDispatcherCallbackRequest",
    "TranscriptSnapshotData",
    "TranscriptSnapshotRequest",
    "UpdateEtaData",
    "UpdateEtaRequest",
    "UpdateHosRequest",
    "UpdateStatusRequest",
    "UpdatedAtData",
    "UrgentTaskData",
]
