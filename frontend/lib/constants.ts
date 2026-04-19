// Leaflet uses [lat, lng] ordering (unlike Mapbox's [lng, lat]).
export const INITIAL_CENTER: [number, number] = [34.3, -112.5];
export const INITIAL_ZOOM = 5.5;

export const MARKER_COLOR = {
  driving: "#3b82f6",
  at_stop_ok: "#22c55e",
  exception: "#ef4444",
  idle: "#9ca3af",
} as const;

export const STATUS_COLOR = {
  planned: "#9ca3af",
  in_transit: "#3b82f6",
  at_pickup: "#22c55e",
  at_delivery: "#22c55e",
  delivered: "#6b7280",
  exception: "#ef4444",
} as const;

export const DISPATCHER_ID =
  process.env.NEXT_PUBLIC_DISPATCHER_ID ?? "demo";

export const PUSHER_KEY = process.env.NEXT_PUBLIC_PUSHER_KEY ?? "";
export const PUSHER_CLUSTER = process.env.NEXT_PUBLIC_PUSHER_CLUSTER ?? "us3";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const RELAY_TOKEN = process.env.NEXT_PUBLIC_RELAY_TOKEN ?? "";

export const CHANNEL_NAME = `dispatcher.${DISPATCHER_ID}`;
