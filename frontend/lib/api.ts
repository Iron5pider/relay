import {
  API_BASE_URL,
  DISPATCHER_ID,
  RELAY_TOKEN,
} from "@/lib/constants";
import type {
  CallPurpose,
  CallOutcome,
  DriverStatus,
  FatigueLevel,
  Language,
  LoadStatus,
} from "@shared/types";

// ---------------------------------------------------------------------------
// Wire types — mirror what `backend/routes/dashboard.py` actually returns.
// These are denormalized snapshots, not the canonical schemas.py models.
// ---------------------------------------------------------------------------

export interface StopSnapshot {
  name: string;
  lat: number;
  lng: number;
  appointment: string | null;
}

export interface BrokerLite {
  id: string;
  name: string;
}

export interface PodInfo {
  url: string | null;
  signed_by: string | null;
  received_at: string | null;
}

export interface ActiveLoad {
  load_id: string;
  load_number: string;
  status: LoadStatus;
  pickup: StopSnapshot;
  delivery: StopSnapshot;
  rate_linehaul: number | null;
  detention_rate_per_hour: number | null;
  detention_free_minutes: number;
  detention_minutes_elapsed: number;
  arrived_at_stop_at: string | null;
  exception_flags: string[];
  broker: BrokerLite | null;
  pod: PodInfo;
}

export interface DriverRow {
  driver_id: string;
  name: string;
  truck_number: string;
  phone: string;
  preferred_language: Language;
  current_lat: number | null;
  current_lng: number | null;
  status: DriverStatus | string;
  fatigue_level: FatigueLevel | string;
  hos_drive_remaining_minutes: number;
  hos_shift_remaining_minutes: number;
  hos_cycle_remaining_minutes: number;
  last_checkin_at: string | null;
  next_scheduled_checkin_at: string | null;
  last_assigned_at: string | null;
  updated_at: string | null;
  active_load: ActiveLoad | null;
}

export interface FleetLive {
  adapter: string;
  fetched_at: string;
  count: number;
  drivers: DriverRow[];
}

export interface DriverTimelineEvent {
  event_id: string;
  kind: string;
  detected_at: string;
  payload: Record<string, unknown>;
}

export interface CallSummary {
  call_id: string;
  conversation_id: string | null;
  agent_id: string | null;
  direction: "outbound" | "inbound";
  purpose: CallPurpose | string;
  call_status: string;
  outcome: CallOutcome | string | null;
  trigger_reason: string | null;
  language: Language | string | null;
  duration_seconds: number | null;
  started_at: string | null;
  ended_at: string | null;
  load_id: string | null;
  driver_id: string | null;
}

export interface DetentionRow {
  load_id: string;
  load_number: string;
  driver: { id: string; name: string; truck_number: string } | null;
  broker: BrokerLite | null;
  stop_name: string;
  arrived_at_stop_at: string | null;
  detention_minutes_elapsed: number;
  detention_free_minutes: number;
  detention_rate_per_hour: number;
  billable_amount_usd: number;
  exception_flags: string[];
}

export interface InvoiceRow {
  invoice_id: string;
  load_id: string;
  call_id: string | null;
  detention_minutes: number;
  billable_minutes: number;
  rate_per_hour: number;
  amount_usd: number;
  status: "draft" | "sent" | "paid" | "disputed";
  created_at: string;
  sent_at: string | null;
  pdf_url: string | null;
}

export interface CallInitiateResponse {
  conversation_id: string;
  call_sid: string | null;
  voice_call_id: string;
}

export type AgentKind =
  | "detention_agent"
  | "driver_agent"
  | "broker_update_agent";

// Matches backend DriverCallTrigger enum (backend/models/schemas.py)
export type TriggerReason =
  | "scheduled_checkin"
  | "hos_near_cap"
  | "eta_slip_check"
  | "post_breakdown"
  | "stationary_too_long"
  | "inbound";

export interface CallInitiateRequest {
  agent_kind: AgentKind;
  driver_id?: string;
  load_id?: string;
  to_number?: string;
  trigger_reason?: TriggerReason;
  extra_dynamic_variables?: Record<string, unknown>;
  first_message_override?: string;
}

// ---------------------------------------------------------------------------
// Fetch core
// ---------------------------------------------------------------------------

interface Envelope<T> {
  ok: boolean;
  data: T | null;
  error: { code: string; message: string } | null;
}

function headers(extra: Record<string, string> = {}): HeadersInit {
  const h: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Relay-Dispatcher-Id": DISPATCHER_ID,
    ...extra,
  };
  if (RELAY_TOKEN) h["Authorization"] = `Bearer ${RELAY_TOKEN}`;
  return h;
}

async function unwrap<T>(res: Response): Promise<T> {
  const ct = res.headers.get("content-type") ?? "";
  const body: Envelope<T> | T = ct.includes("application/json")
    ? await res.json()
    : ((await res.text()) as unknown as T);
  if (
    body &&
    typeof body === "object" &&
    "ok" in body &&
    "data" in body
  ) {
    const env = body as Envelope<T>;
    if (!env.ok) {
      const code = env.error?.code ?? `http_${res.status}`;
      const msg = env.error?.message ?? res.statusText;
      throw new ApiError(code, msg, res.status);
    }
    return (env.data as T);
  }
  if (!res.ok) throw new ApiError(`http_${res.status}`, res.statusText, res.status);
  return body as T;
}

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function get<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    method: "GET",
    headers: headers(init?.headers as Record<string, string>),
    cache: "no-store",
  });
  return unwrap<T>(res);
}

async function post<T>(
  path: string,
  body?: unknown,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    method: "POST",
    headers: headers(init?.headers as Record<string, string>),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return unwrap<T>(res);
}

// ---------------------------------------------------------------------------
// Dashboard reads
// ---------------------------------------------------------------------------

export const api = {
  async fleetLive(): Promise<FleetLive> {
    return get<FleetLive>("/dispatcher/fleet/live");
  },

  async driverDetail(driverId: string): Promise<DriverRow & { recent_calls: CallSummary[] }> {
    return get(`/dispatcher/driver/${driverId}`);
  },

  async driverTimeline(driverId: string, limit = 25): Promise<{ events: DriverTimelineEvent[] }> {
    return get(`/dispatcher/driver/${driverId}/timeline?limit=${limit}`);
  },

  async activeDetentions(): Promise<{ rows: DetentionRow[] }> {
    return get("/dispatcher/detentions/active");
  },

  async invoices(): Promise<{ rows: InvoiceRow[] }> {
    return get("/dispatcher/invoices");
  },

  async invoice(invoiceId: string): Promise<InvoiceRow & { call: CallSummary | null }> {
    return get(`/dispatcher/invoices/${invoiceId}`);
  },

  async sendInvoice(invoiceId: string): Promise<InvoiceRow> {
    return post(`/dispatcher/invoices/${invoiceId}/send`);
  },

  // --- actions (call trigger) --------------------------------------------

  async callInitiate(body: CallInitiateRequest): Promise<CallInitiateResponse> {
    return post("/internal/call/initiate", body);
  },

  async triggerDetentionCall(loadId: string, toNumber?: string) {
    return api.callInitiate({
      agent_kind: "detention_agent",
      load_id: loadId,
      // trigger_reason omitted → backend default (scheduled_checkin)
      to_number: toNumber,
    });
  },

  async triggerDriverCheckin(driverId: string) {
    return api.callInitiate({
      agent_kind: "driver_agent",
      driver_id: driverId,
    });
  },

  async triggerBrokerUpdate(loadId: string) {
    return api.callInitiate({
      agent_kind: "broker_update_agent",
      load_id: loadId,
    });
  },

  // --- assignment -------------------------------------------------------

  async unassignedLoads(): Promise<{ count: number; loads: UnassignedLoad[] }> {
    return get("/dispatcher/loads/unassigned");
  },

  async loadCandidates(loadId: string): Promise<CandidatesResponse> {
    return get(`/dispatcher/load/${loadId}/candidates`);
  },

  async assignLoad(loadId: string, driverId: string): Promise<AssignResult> {
    return post(`/dispatcher/load/${loadId}/assign`, { driver_id: driverId });
  },
};

// ---------------------------------------------------------------------------
// Consignment / assignment
// ---------------------------------------------------------------------------

export interface UnassignedLoad {
  load_id: string;
  load_number: string;
  status: string;
  broker_name: string;
  pickup_name: string;
  pickup_appointment: string | null;
  delivery_name: string;
  delivery_appointment: string | null;
  rate_linehaul: number;
}

export interface CandidateScore {
  driver_id: string;
  driver_name: string;
  truck_number: string;
  preferred_language: string;
  status: string;
  fatigue_level: string;
  hos_drive_remaining_minutes: number;
  miles_to_pickup: number | null;
  haul_miles: number;
  hos_headroom_minutes: number;
  hours_since_last_assigned: number | null;
  qualified: boolean;
  disqualification_reason: string | null;
  score: number;
  components: Record<string, number>;
  flags: string[];
}

export interface AiRecommendation {
  recommended_driver_id: string;
  confidence: "low" | "medium" | "high";
  recommendation: string;
  risk_flags: string[];
  alternative_driver_id: string | null;
}

export interface CandidatesResponse {
  load_id: string;
  load_number: string;
  haul_miles: number;
  ranking: CandidateScore[];
  ai_recommendation: AiRecommendation;
}

export interface AssignResult {
  load_id: string;
  load_number: string;
  driver_id: string;
  driver_name: string;
  assigned_at: string;
  status: string;
}
