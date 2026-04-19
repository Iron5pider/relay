"use client";

import { useSyncExternalStore } from "react";
import Pusher, { type Channel } from "pusher-js";
import { CHANNEL_NAME, PUSHER_CLUSTER, PUSHER_KEY } from "@/lib/constants";
import type {
  ActiveLoad,
  DriverRow,
  InvoiceRow,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Event payloads (backend publishes these six — see API_DOCS/build_scope.md §7)
// ---------------------------------------------------------------------------

export interface LoadUpdatedEvent {
  driver?: DriverRow;
  active_load?: ActiveLoad;
  // Backend publishes after DB commit with a partial driver + load payload.
  // We merge by driver_id / load_id.
}

export interface ExceptionEventPayload {
  id: string;
  load_id: string | null;
  driver_id: string | null;
  event_type: string;
  severity: "info" | "warn" | "critical";
  payload: Record<string, unknown>;
  detected_at: string;
}

export interface CallStartedEvent {
  call_id: string;
  conversation_id?: string | null;
  purpose: string;
  load_id: string | null;
  driver_id: string | null;
  started_at: string;
}

export interface TranscriptTurnEvent {
  call_id: string;
  turn_id: string;
  speaker: "agent" | "human";
  text: string;
  language: string;
  started_at: string;
  is_final: boolean;
}

export interface CallEndedEvent {
  call_id: string;
  outcome: string | null;
  duration_seconds: number;
  ended_at: string;
  audio_url?: string | null;
}

export interface InvoiceGeneratedEvent extends InvoiceRow {}

// ---------------------------------------------------------------------------
// External store — one bus for all components. useSyncExternalStore hooks
// below subscribe to specific slices.
// ---------------------------------------------------------------------------

type Listener = () => void;
const listeners = new Set<Listener>();

function emit() {
  for (const l of listeners) l();
}

function subscribe(l: Listener) {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}

interface BusState {
  driversById: Record<string, DriverRow>;
  loadsById: Record<string, ActiveLoad & { driver_id: string }>;
  driverOrder: string[];
  exceptions: ExceptionEventPayload[];
  activeCallId: string | null;
  callStatus: "idle" | "calling" | "connected" | "completed";
  callOutcome: string | null;
  callStartedAt: string | null;
  callEndedAt: string | null;
  transcriptByCall: Record<string, TranscriptTurnEvent[]>;
  latestInvoice: InvoiceRow | null;
  connectionState: "connecting" | "connected" | "disconnected";
}

const state: BusState = {
  driversById: {},
  loadsById: {},
  driverOrder: [],
  exceptions: [],
  activeCallId: null,
  callStatus: "idle",
  callOutcome: null,
  callStartedAt: null,
  callEndedAt: null,
  transcriptByCall: {},
  latestInvoice: null,
  connectionState: "connecting",
};

// Stable snapshots per slice — useSyncExternalStore requires reference stability.
const snapshots = {
  drivers: [] as DriverRow[],
  exceptions: [] as ExceptionEventPayload[],
  callMeta: {
    callId: null as string | null,
    status: "idle" as BusState["callStatus"],
    outcome: null as string | null,
    startedAt: null as string | null,
    endedAt: null as string | null,
  },
  transcriptByCall: {} as Record<string, TranscriptTurnEvent[]>,
  latestInvoice: null as InvoiceRow | null,
  connectionState: "connecting" as BusState["connectionState"],
};

function rebuildDriversSnapshot() {
  snapshots.drivers = state.driverOrder
    .map((id) => state.driversById[id])
    .filter(Boolean);
}

// ---------------------------------------------------------------------------
// Public mutators (used by page hydration + Pusher handlers)
// ---------------------------------------------------------------------------

export function hydrateFleet(drivers: DriverRow[]) {
  state.driversById = {};
  state.loadsById = {};
  state.driverOrder = [];
  for (const d of drivers) {
    state.driversById[d.driver_id] = d;
    state.driverOrder.push(d.driver_id);
    if (d.active_load) {
      state.loadsById[d.active_load.load_id] = {
        ...d.active_load,
        driver_id: d.driver_id,
      };
    }
  }
  rebuildDriversSnapshot();
  emit();
}

function applyLoadUpdated(ev: LoadUpdatedEvent) {
  if (ev.driver) {
    const existing = state.driversById[ev.driver.driver_id];
    state.driversById[ev.driver.driver_id] = { ...existing, ...ev.driver };
    if (!state.driverOrder.includes(ev.driver.driver_id)) {
      state.driverOrder.push(ev.driver.driver_id);
    }
  }
  if (ev.active_load) {
    // Figure out the driver_id from payload or from existing state.
    const driverId =
      ev.driver?.driver_id ??
      Object.values(state.driversById).find(
        (d) => d.active_load?.load_id === ev.active_load!.load_id,
      )?.driver_id;
    if (driverId) {
      const existingDriver = state.driversById[driverId];
      if (existingDriver) {
        state.driversById[driverId] = {
          ...existingDriver,
          active_load: ev.active_load,
        };
      }
      state.loadsById[ev.active_load.load_id] = {
        ...ev.active_load,
        driver_id: driverId,
      };
    }
  }
  rebuildDriversSnapshot();
  emit();
}

function applyExceptionRaised(ev: ExceptionEventPayload) {
  // keep most recent 30
  state.exceptions = [ev, ...state.exceptions].slice(0, 30);
  snapshots.exceptions = state.exceptions;
  emit();
}

function applyCallStarted(ev: CallStartedEvent) {
  state.activeCallId = ev.call_id;
  state.callStatus = "connected";
  state.callStartedAt = ev.started_at;
  state.callEndedAt = null;
  state.callOutcome = null;
  snapshots.callMeta = {
    callId: ev.call_id,
    status: "connected",
    outcome: null,
    startedAt: ev.started_at,
    endedAt: null,
  };
  emit();
}

export function markCallDialing(callId: string) {
  state.activeCallId = callId;
  state.callStatus = "calling";
  state.callStartedAt = new Date().toISOString();
  state.callEndedAt = null;
  state.callOutcome = null;
  snapshots.callMeta = {
    callId,
    status: "calling",
    outcome: null,
    startedAt: state.callStartedAt,
    endedAt: null,
  };
  emit();
}

function applyTranscriptTurn(ev: TranscriptTurnEvent) {
  const prev = state.transcriptByCall[ev.call_id] ?? [];
  // Replace partial with final if same turn_id
  const filtered = ev.is_final
    ? prev.filter((t) => t.turn_id !== ev.turn_id)
    : prev.filter((t) => !(t.turn_id === ev.turn_id && !t.is_final));
  state.transcriptByCall[ev.call_id] = [...filtered, ev];
  snapshots.transcriptByCall = { ...state.transcriptByCall };
  emit();
}

function applyCallEnded(ev: CallEndedEvent) {
  state.callStatus = "completed";
  state.callEndedAt = ev.ended_at;
  state.callOutcome = ev.outcome;
  snapshots.callMeta = {
    ...snapshots.callMeta,
    status: "completed",
    outcome: ev.outcome,
    endedAt: ev.ended_at,
  };
  emit();
}

function applyInvoiceGenerated(ev: InvoiceGeneratedEvent) {
  state.latestInvoice = ev;
  snapshots.latestInvoice = ev;
  emit();
}

export function appendSimulatedTranscript(callId: string, turn: TranscriptTurnEvent) {
  applyTranscriptTurn(turn);
}

// ---------------------------------------------------------------------------
// Pusher client (singleton)
// ---------------------------------------------------------------------------

let pusher: Pusher | null = null;
let channel: Channel | null = null;

export function connectPusher() {
  if (typeof window === "undefined") return;
  if (pusher) return;
  if (!PUSHER_KEY) {
    // No Pusher configured — stay in polling-only mode.
    state.connectionState = "disconnected";
    snapshots.connectionState = "disconnected";
    emit();
    return;
  }
  pusher = new Pusher(PUSHER_KEY, { cluster: PUSHER_CLUSTER, forceTLS: true });
  pusher.connection.bind("state_change", (states: { current: string }) => {
    const next =
      states.current === "connected"
        ? "connected"
        : states.current === "connecting" || states.current === "initialized"
          ? "connecting"
          : "disconnected";
    state.connectionState = next;
    snapshots.connectionState = next;
    emit();
  });
  channel = pusher.subscribe(CHANNEL_NAME);
  channel.bind("load.updated", applyLoadUpdated);
  channel.bind("exception.raised", applyExceptionRaised);
  channel.bind("call.started", applyCallStarted);
  channel.bind("call.transcript", applyTranscriptTurn);
  channel.bind("call.ended", applyCallEnded);
  channel.bind("invoice.generated", applyInvoiceGenerated);
}

export function disconnectPusher() {
  if (channel) channel.unsubscribe();
  if (pusher) pusher.disconnect();
  channel = null;
  pusher = null;
}

// ---------------------------------------------------------------------------
// React hooks
// ---------------------------------------------------------------------------

export function getDriversSnapshot(): DriverRow[] {
  return snapshots.drivers;
}

export function useDrivers(): DriverRow[] {
  return useSyncExternalStore(
    subscribe,
    () => snapshots.drivers,
    () => snapshots.drivers,
  );
}

export function useExceptionFeed(): ExceptionEventPayload[] {
  return useSyncExternalStore(
    subscribe,
    () => snapshots.exceptions,
    () => snapshots.exceptions,
  );
}

export function useCallMeta() {
  return useSyncExternalStore(
    subscribe,
    () => snapshots.callMeta,
    () => snapshots.callMeta,
  );
}

export function useTranscript(callId: string | null): TranscriptTurnEvent[] {
  return useSyncExternalStore(
    subscribe,
    () => (callId ? (snapshots.transcriptByCall[callId] ?? []) : []),
    () => [],
  );
}

export function useLatestInvoice(): InvoiceRow | null {
  return useSyncExternalStore(
    subscribe,
    () => snapshots.latestInvoice,
    () => snapshots.latestInvoice,
  );
}

export function useConnectionState(): BusState["connectionState"] {
  return useSyncExternalStore(
    subscribe,
    () => snapshots.connectionState,
    () => snapshots.connectionState,
  );
}
