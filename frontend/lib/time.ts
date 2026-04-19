export function minutesBetween(isoStart: string, nowMs = Date.now()): number {
  const started = new Date(isoStart).getTime();
  if (Number.isNaN(started)) return 0;
  return Math.max(0, Math.floor((nowMs - started) / 60_000));
}

export function secondsBetween(isoStart: string, nowMs = Date.now()): number {
  const started = new Date(isoStart).getTime();
  if (Number.isNaN(started)) return 0;
  return Math.max(0, Math.floor((nowMs - started) / 1_000));
}

export function detentionBillable(
  arrivedAt: string | null,
  freeMinutes: number,
  nowMs = Date.now(),
): { total: number; billable: number; freeRemaining: number } {
  if (!arrivedAt) return { total: 0, billable: 0, freeRemaining: freeMinutes };
  const total = minutesBetween(arrivedAt, nowMs);
  const billable = Math.max(0, total - freeMinutes);
  const freeRemaining = Math.max(0, freeMinutes - total);
  return { total, billable, freeRemaining };
}

export function detentionAmount(
  arrivedAt: string | null,
  freeMinutes: number,
  ratePerHour: number,
  nowMs = Date.now(),
): number {
  const { billable } = detentionBillable(arrivedAt, freeMinutes, nowMs);
  return (billable / 60) * ratePerHour;
}

export function formatMinutes(m: number): string {
  const hh = Math.floor(m / 60);
  const mm = m % 60;
  return `${hh}h ${mm}m`;
}

export function formatTimer(m: number): string {
  const hh = Math.floor(m / 60).toString().padStart(2, "0");
  const mm = (m % 60).toString().padStart(2, "0");
  return `${hh}:${mm}`;
}

export function formatMoney(amount: number): string {
  return amount.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatRelative(iso: string | null, nowMs = Date.now()): string {
  if (!iso) return "—";
  const diff = Math.floor((nowMs - new Date(iso).getTime()) / 1000);
  if (diff < 30) return "just now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
