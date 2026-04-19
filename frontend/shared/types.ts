// ============================================================
// Relay — Shared Types (canonical)
// ============================================================
//
// Mirrors `backend/models/schemas.py` field-for-field. Same casing
// (`snake_case`), same enum string values, same nullability. Drift between
// this file and the Pydantic side breaks the demo on stage — per
// `backend/CLAUDE.md` §1 golden rule #2 + `project_canonical_spec` memory.
// Change one, change both + the Notion **API Models** page in the same PR.
//
// Additive (2026-04-19):
// - `CheckinTriggerReason` gains `missed_checkin` + `tracking_stale`.
// - `Call.trigger_reasoning` — Claude anomaly-agent rationale; null for
//   hard-rule-fired calls. Rendered verbatim in the AnomalyBadge tooltip.

export type UUID = string;
export type ISODateTime = string;
export type E164 = string;

export type Language = 'en' | 'es' | 'pa';

export interface Coordinates {
  lat: number;
  lng: number;
}

// ---------- Driver ----------
// FMCSA statuses coexist with the tools-contract app-layer statuses
// (ready/resting/blocked/rolling — 2026-04-19).
export type DriverStatus =
  | 'driving'
  | 'on_duty'
  | 'off_duty'
  | 'sleeper'
  | 'ready'
  | 'resting'
  | 'blocked'
  | 'rolling';
export type FatigueLevel = 'low' | 'moderate' | 'high' | 'unknown';

export interface Driver {
  id: UUID;
  name: string;
  phone: E164;
  preferred_language: Language;
  truck_number: string;
  current_lat: number | null;
  current_lng: number | null;
  // FMCSA three-clock model (minutes). Relay-tracked — NavPro v1.0 doesn't
  // expose HOS clocks (see API_DOCS/NavPro_integration.md §9 gaps).
  hos_drive_remaining_minutes: number;
  hos_shift_remaining_minutes: number;
  hos_cycle_remaining_minutes: number;
  hos_remaining_minutes: number; // alias of hos_drive_remaining_minutes
  status: DriverStatus;
  // F6b Proactive Check-In state.
  fatigue_level: FatigueLevel;
  last_checkin_at: ISODateTime | null;
  next_scheduled_checkin_at: ISODateTime | null;
  updated_at: ISODateTime;
}

// ---------- Broker ----------
export type UpdateChannel = 'call' | 'sms' | 'email';

export interface Broker {
  id: UUID;
  name: string;
  contact_name: string;
  phone: E164;
  email: string;
  preferred_update_channel: UpdateChannel;
}

// ---------- Load ----------
export type LoadStatus =
  | 'planned'
  | 'in_transit'
  | 'at_pickup'
  | 'at_delivery'
  | 'delivered'
  | 'exception';

export type ExceptionType =
  | 'detention_threshold_breached'
  | 'hos_warning'
  | 'missed_appointment'
  | 'breakdown'
  | 'late_eta';

export interface Stop {
  name: string;
  lat: number;
  lng: number;
  phone: E164 | null;
  appointment: ISODateTime;
}

export interface DriverLite {
  id: UUID;
  name: string;
  truck_number: string;
}

export interface BrokerLite {
  id: UUID;
  name: string;
}

export interface Load {
  id: UUID;
  load_number: string;
  driver: DriverLite;
  broker: BrokerLite;
  pickup: Stop;
  delivery: Stop;
  rate_linehaul: number;
  detention_rate_per_hour: number;
  detention_free_minutes: number;
  status: LoadStatus;
  arrived_at_stop_at: ISODateTime | null;
  detention_minutes_elapsed: number;
  exception_flags: ExceptionType[];
  created_at: ISODateTime;
}

// ---------- Call ----------
export type CallDirection = 'outbound' | 'inbound';

export type CallPurpose =
  | 'detention_escalation'
  | 'broker_check_call'
  | 'driver_checkin' // inbound IVR (deferred per Build Scope)
  | 'driver_proactive_checkin' // outbound F6b
  | 'other';

export type CallOutcome =
  | 'resolved'
  | 'escalated'
  | 'voicemail'
  | 'no_answer'
  | 'failed'
  | 'in_progress';

export type Speaker = 'agent' | 'human';

export type EtaConfidence = 'on_time' | 'at_risk' | 'late';

export type CheckinStatus =
  | 'on_route'
  | 'at_pickup'
  | 'at_delivery'
  | 'delivered'
  | 'exception';

export type CheckinTriggerReason =
  | 'scheduled'
  | 'hos_near_cap'
  | 'eta_drift'
  | 'extended_idle'
  | 'missed_checkin' // 2026-04-19 — Build Scope Feature 2
  | 'tracking_stale' // 2026-04-19 — NavPro freshness signal
  | 'manual';

// Tools-contract enums (2026-04-19). Source: API_DOCS/tools_contract.md §1.
// Coexist with CheckinTriggerReason during naming transition.
export type DriverCallTrigger =
  | 'scheduled_checkin'
  | 'hos_near_cap'
  | 'eta_slip_check'
  | 'post_breakdown'
  | 'stationary_too_long'
  | 'inbound';

export type Urgency = 'low' | 'med' | 'high';

export type IssueType =
  | 'mechanical'
  | 'personal'
  | 'load'
  | 'route'
  | 'weather'
  | 'other'
  | 'none';

export interface TranscriptTurn {
  id: UUID;
  speaker: Speaker;
  text: string;
  language: Language;
  started_at: ISODateTime;
  confidence: number;
}

export interface Call {
  id: UUID;
  load_id: UUID | null;
  direction: CallDirection;
  purpose: CallPurpose;
  from_number: E164;
  to_number: E164;
  language: Language;
  started_at: ISODateTime;
  ended_at: ISODateTime | null;
  duration_seconds: number | null;
  outcome: CallOutcome;
  audio_url: string | null;
  twilio_call_sid: string;
  transcript: TranscriptTurn[];
  // Claude anomaly-agent rationale when the call was fired by the reasoning
  // layer. Null when a hard rule fired. Rendered verbatim in the dashboard
  // AnomalyBadge tooltip on hover.
  trigger_reasoning: string | null;
}

// ---------- Calls section (dashboard-facing shapes, extra of the canonical Call) ----------
// These mirror the output of `/dispatcher/calls` and `/dispatcher/calls/{id}`
// and are distinct from `Call` above because the dispatcher view surfaces
// ElevenLabs analysis output that the canonical domain model doesn't carry.

export interface CallListRow {
  call_id: UUID;
  conversation_id: string | null;
  agent_id: string | null;
  direction: CallDirection;
  purpose: CallPurpose;
  call_status: string;
  outcome: CallOutcome;
  trigger_reason: string | null;
  language: Language;
  duration_seconds: number | null;
  started_at: ISODateTime;
  ended_at: ISODateTime | null;
  load_id: UUID | null;
  driver_id: UUID | null;
  termination_reason: string | null;
  call_summary_title: string | null;
  transcript_summary: string | null;
  has_audio: boolean | null;
  cost: number | null;
}

export interface EvaluationCriterion {
  criteria_id: string;
  result: 'success' | 'failure' | 'unknown' | string;
  rationale: string | null;
}

export interface DataCollectionField {
  data_collection_id: string;
  value: string | number | boolean | null;
  rationale: string | null;
  description: string | null;
  type: string | null;
}

export interface CallTranscriptTurn {
  role: 'agent' | 'user' | string;
  message: string | null;
  time_in_call_secs: number | null;
  tool_calls: unknown[];
  interrupted: boolean | null;
}

export interface CallPhoneMeta {
  type: string | null;
  direction: string | null;
  from_number: string | null;
  to_number: string | null;
  phone_number_id: string | null;
  call_sid: string | null;
  agent_number: string | null;
  external_number: string | null;
}

export interface CallDetail extends CallListRow {
  trigger_reasoning: string | null;
  audio_url: string | null;
  call_successful: string | null;
  phone_call: CallPhoneMeta;
  transcript: CallTranscriptTurn[];
  evaluation_criteria_results: EvaluationCriterion[];
  data_collection_results: DataCollectionField[];
  driver: DriverLite | null;
  load: unknown | null;
  broker: BrokerLite | null;
}

// ---------- Detention invoice ----------
export type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'disputed';

export interface DetentionInvoice {
  id: UUID;
  load_id: UUID;
  call_id: UUID;
  detention_minutes: number;
  rate_per_hour: number;
  amount_usd: number;
  pdf_url: string;
  status: InvoiceStatus;
  created_at: ISODateTime;
}

// ---------- Exception event ----------
export type Severity = 'info' | 'warn' | 'critical';

export interface ExceptionEvent {
  id: UUID;
  load_id: UUID;
  driver_id: UUID;
  event_type: ExceptionType;
  severity: Severity;
  payload: Record<string, unknown>;
  triggered_call_id: UUID | null;
  detected_at: ISODateTime;
}

// ---------- Parking POI (static snapshot; NavPro /poi is company-custom only) ----------
export interface ParkingSpot {
  name: string;
  lat: number;
  lng: number;
  available_spots: number;
  distance_miles: number;
  exit: string;
}

// ---------- Request / response envelopes ----------

export interface EscalateDetentionRequest {
  load_id: UUID;
  receiver_phone_override?: E164;
  auto_invoice?: boolean;
}

export interface EscalateDetentionResponse {
  call_id: UUID;
  twilio_call_sid: string;
  status: 'initiated';
  expected_detention_amount: number;
}

export interface DriverCheckinRequest {
  driver_id: UUID;
  trigger_reason?: CheckinTriggerReason;
  phone_override?: E164;
  // Optional rationale the Claude anomaly agent attaches when it's the caller.
  trigger_reasoning?: string;
}

export interface DriverCheckinResponse {
  call_id: UUID;
  twilio_call_sid: string;
  status: 'initiated';
  trigger_reason: CheckinTriggerReason;
}

export interface BatchBrokerUpdatesRequest {
  broker_ids?: UUID[];
  update_type?: 'end_of_day' | 'pre_delivery' | 'custom';
  custom_message?: string;
}

export interface BatchBrokerUpdatesResponse {
  batch_id: UUID;
  call_ids: UUID[];
  count: number;
}
